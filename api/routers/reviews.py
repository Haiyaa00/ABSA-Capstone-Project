"""
Router: reviews.py
Mo ta: Cac API quan ly Hop thu Phan hoi (Feed), Chi tiet, Goi y phan hoi Gemini va Phan tich Live.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_acsa_pipeline, get_current_user, get_reply_generator
from api.schemas import (
    GenerateReplyRequest,
    GenerateReplyResponse,
    ManualAnalyzeRequest,
    ManualAnalyzeResponse,
    PaginatedReviewsResponse,
    ReplyLogOut,
    ReviewDetailOut,
    UpdateReplyRequest,
)
from api.services.review_service import (
    analyze_manual_review,
    generate_review_reply,
    get_review_detail,
    list_reviews,
    update_reply_log,
)
from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/api/reviews", tags=["Reviews & AI Reply"])


@router.get("", response_model=PaginatedReviewsResponse)
def get_reviews_feed(
    hotel_id: Optional[int] = Query(default=None, ge=1),
    rating: Optional[int] = Query(default=None, ge=1, le=5),
    intent: Optional[str] = Query(default=None, description="CRITICAL_COMPLAINT | IMPROVEMENT_SUGGESTION | GENERAL_FEEDBACK"),
    sentiment: Optional[str] = Query(default=None, description="positive | negative | neutral"),
    is_replied: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lay danh sach danh gia kem chip khia canh ABSA, ho tro bo loc va phan trang."""
    return list_reviews(
        db=db,
        hotel_id=hotel_id,
        rating=rating,
        intent=intent,
        sentiment=sentiment,
        is_replied=is_replied,
        search=search,
        page=page,
        limit=limit,
    )


@router.post("/analyze-manual", response_model=ManualAnalyzeResponse)
def analyze_manual(
    payload: ManualAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phan tich truc tiep mot cau danh gia nhap tay (PhoBERT ABSA + Hybrid Intent)."""
    ai_pipeline = get_acsa_pipeline()
    result = analyze_manual_review(db=db, payload=payload, ai_pipeline=ai_pipeline)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khong tim thay khach san voi ID={payload.hotel_id}.",
        )
    return result


@router.patch("/replies/{reply_id}", response_model=ReplyLogOut)
def confirm_or_edit_reply(
    reply_id: int,
    payload: UpdateReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chinh sua noi dung goi y tu AI va xac nhan da su dung phan hoi cho khach."""
    updated = update_reply_log(
        db=db,
        reply_id=reply_id,
        edited_reply=payload.edited_reply,
        mark_as_used=payload.mark_as_used,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khong tim thay ban ghi phan hoi ID={reply_id}.",
        )
    return updated


@router.get("/{review_id}", response_model=ReviewDetailOut)
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem chi tiet mot danh gia, cac khia canh ABSA, Task lien quan va lich su AI Reply."""
    detail = get_review_detail(db=db, review_id=review_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khong tim thay danh gia voi ID={review_id}.",
        )
    return detail


@router.post("/{review_id}/generate-reply", response_model=GenerateReplyResponse)
def generate_reply(
    review_id: int,
    payload: Optional[GenerateReplyRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Goi Gemini LLM sinh cau tra loi goi y bam sat cac khia canh ABSA da boc tach."""
    req = payload or GenerateReplyRequest()
    reply_generator = get_reply_generator()
    response = generate_review_reply(
        db=db,
        review_id=review_id,
        reply_generator=reply_generator,
        force_regenerate=req.force_regenerate,
        hotel_name_override=req.hotel_name,
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khong tim thay danh gia voi ID={review_id}.",
        )
    return response
