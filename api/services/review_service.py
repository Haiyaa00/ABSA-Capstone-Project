"""
Module: review_service.py
Mo ta: Tang nghiep vu xu ly Danh gia (Reviews Feed), Goi y Phan hoi Gemini va Phan tich Truc tiep.
"""

from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session, selectinload

from core.time_utils import utc_now

from api.schemas import (
    AspectResultOut,
    GenerateReplyResponse,
    ManualAnalyzeRequest,
    ManualAnalyzeResponse,
    PaginatedReviewsResponse,
    ReplyLogOut,
    ReviewDetailOut,
    ReviewOut,
    TaskOut,
)
from api.services.review_processor import apply_analysis_to_review
from database.models import AspectResult, Hotel, ReplyLog, Review, ReviewSource


def _to_review_out(review: Review) -> ReviewOut:
    """Chuyen doi ORM Review sang Pydantic ReviewOut kem khia canh va cau tra loi moi nhat."""
    sorted_replies = sorted(review.reply_logs, key=lambda r: r.created_at, reverse=True)
    latest_reply = ReplyLogOut.model_validate(sorted_replies[0]) if sorted_replies else None

    return ReviewOut(
        id=review.id,
        hotel_id=review.hotel_id,
        hotel_name=review.hotel.name if review.hotel else None,
        source=review.source.value,
        author_name=review.author_name,
        rating=review.rating,
        text=review.text,
        review_time=review.review_time,
        is_processed=review.is_processed,
        intent=review.intent or "GENERAL_FEEDBACK",
        intent_reason=review.intent_reason,
        is_replied=bool(review.is_replied),
        aspects=[AspectResultOut.model_validate(a) for a in review.aspect_results],
        latest_reply=latest_reply,
    )


def list_reviews(
    db: Session,
    hotel_id: Optional[int] = None,
    rating: Optional[int] = None,
    intent: Optional[str] = None,
    sentiment: Optional[str] = None,
    is_replied: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> PaginatedReviewsResponse:
    """Truy van danh sach danh gia co loc da dieu kien va phan trang."""
    query = db.query(Review).options(
        selectinload(Review.hotel),
        selectinload(Review.aspect_results),
        selectinload(Review.reply_logs),
    )

    if hotel_id is not None:
        query = query.filter(Review.hotel_id == hotel_id)
    if rating is not None:
        query = query.filter(Review.rating == rating)
    if intent:
        query = query.filter(Review.intent == intent.upper())
    if is_replied is not None:
        query = query.filter(Review.is_replied == is_replied)
    if search:
        query = query.filter(Review.text.ilike(f"%{search.strip()}%"))
    if sentiment:
        query = query.filter(
            Review.aspect_results.any(AspectResult.sentiment == sentiment.lower())
        )

    total = query.count()
    offset = (page - 1) * limit
    rows = (
        query.order_by(Review.review_time.desc(), Review.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PaginatedReviewsResponse(
        total=total,
        page=page,
        limit=limit,
        items=[_to_review_out(r) for r in rows],
    )


def get_review_detail(db: Session, review_id: int) -> Optional[ReviewDetailOut]:
    """Lay chi tiet mot danh gia kem toan bo khia canh, task lien quan va lich su reply."""
    review = (
        db.query(Review)
        .options(
            selectinload(Review.hotel),
            selectinload(Review.aspect_results),
            selectinload(Review.tasks),
            selectinload(Review.reply_logs),
        )
        .filter(Review.id == review_id)
        .first()
    )
    if not review:
        return None

    base_out = _to_review_out(review)
    sorted_replies = sorted(review.reply_logs, key=lambda r: r.created_at, reverse=True)

    return ReviewDetailOut(
        **base_out.model_dump(),
        tasks=[TaskOut.model_validate(t) for t in review.tasks],
        reply_logs=[ReplyLogOut.model_validate(r) for r in sorted_replies],
    )


def generate_review_reply(
    db: Session,
    review_id: int,
    reply_generator,
    force_regenerate: bool = False,
    hotel_name_override: Optional[str] = None,
) -> Optional[GenerateReplyResponse]:
    """Sinh cau tra loi mau bang Gemini LLM dua tren khia canh ABSA va luu vao reply_logs."""
    review = (
        db.query(Review)
        .options(
            selectinload(Review.hotel),
            selectinload(Review.aspect_results),
            selectinload(Review.reply_logs),
        )
        .filter(Review.id == review_id)
        .first()
    )
    if not review:
        return None

    if not force_regenerate and review.reply_logs:
        latest_existing = sorted(review.reply_logs, key=lambda r: r.created_at, reverse=True)[0]
        return GenerateReplyResponse(
            reply_log=ReplyLogOut.model_validate(latest_existing),
            cached=True,
        )

    absa_payload = [
        {
            "aspect": a.aspect_category,
            "sentiment": a.sentiment,
            "confidence": a.confidence,
        }
        for a in review.aspect_results
    ]
    hotel_name = hotel_name_override or (review.hotel.name if review.hotel else None)
    intent_label = review.intent or "GENERAL_FEEDBACK"

    result = reply_generator.generate_reply(
        review_text=review.text,
        rating=review.rating,
        absa_results=absa_payload,
        intent=intent_label,
        hotel_name=hotel_name,
    )

    new_log = ReplyLog(
        review_id=review.id,
        generated_reply=result["reply"],
        source=result.get("source", "gemini_llm"),
        is_used=False,
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    return GenerateReplyResponse(
        reply_log=ReplyLogOut.model_validate(new_log),
        cached=False,
    )


def update_reply_log(
    db: Session,
    reply_id: int,
    edited_reply: Optional[str] = None,
    mark_as_used: bool = True,
) -> Optional[ReplyLogOut]:
    """Cap nhat noi dung cau tra loi da chinh sua va danh dau danh gia la da phan hoi."""
    reply_log = db.query(ReplyLog).filter(ReplyLog.id == reply_id).first()
    if not reply_log:
        return None

    if edited_reply is not None:
        reply_log.generated_reply = edited_reply.strip()
    reply_log.is_used = mark_as_used
    reply_log.updated_at = utc_now()

    if mark_as_used:
        review = db.query(Review).filter(Review.id == reply_log.review_id).first()
        if review:
            review.is_replied = True

    db.commit()
    db.refresh(reply_log)
    return ReplyLogOut.model_validate(reply_log)


def analyze_manual_review(
    db: Session,
    payload: ManualAnalyzeRequest,
    ai_pipeline,
) -> Optional[ManualAnalyzeResponse]:
    """Chay phan tich truc tiep (ABSA + Intent) cho mot cau danh gia nhap tay tu Mobile App."""
    hotel = db.query(Hotel).filter(Hotel.id == payload.hotel_id).first()
    if not hotel:
        return None

    analysis = ai_pipeline.analyze_review(payload.text, payload.rating)
    saved_review_id = None
    created_task_id = None

    if payload.save_to_db:
        review = Review(
            hotel_id=hotel.id,
            source=ReviewSource.MANUAL,
            external_id=f"manual_{uuid4().hex[:12]}",
            author_name=payload.author_name or "Khach hang demo",
            rating=payload.rating,
            text=payload.text,
            review_time=utc_now(),
            is_processed=False,
        )
        db.add(review)
        db.flush()

        created_task = apply_analysis_to_review(db, review, analysis)
        db.commit()
        db.refresh(review)
        saved_review_id = review.id
        if created_task is not None:
            db.refresh(created_task)
            created_task_id = created_task.id

    return ManualAnalyzeResponse(
        saved_to_db=payload.save_to_db,
        review_id=saved_review_id,
        created_task_id=created_task_id,
        text=analysis["text"],
        rating=analysis["rating"],
        aspects_count=analysis["aspects_count"],
        aspects=analysis["aspects"],
        intent=analysis["intent"],
        intent_confidence=analysis["intent_confidence"],
        detection_method=analysis["detection_method"],
        intent_reason=analysis["intent_reason"],
        task_action=analysis["task_action"],
    )
