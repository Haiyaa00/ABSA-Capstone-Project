"""
Router: sync.py
Mo ta: API kich hoat dong bo danh gia tu Google Maps (Apify) chay ngam qua BackgroundTasks.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import get_acsa_pipeline, get_current_user
from api.schemas import SyncTriggerRequest, SyncTriggerResponse
from core.logger import get_logger
from database.connection import get_db
from database.models import Hotel, User

logger = get_logger(__name__)
router = APIRouter(prefix="/api/sync", tags=["Data Synchronization"])


def _run_sync_job(hotel_name: Optional[str], maps_url: Optional[str], address: Optional[str], max_reviews: int):
    """Tac vu chay ngam dong bo du lieu va chay PhoBERT ABSA ma khong chan HTTP request."""
    from sync_and_process import ReviewSyncEngine

    ai_pipeline = get_acsa_pipeline()
    engine = ReviewSyncEngine(ai_pipeline=ai_pipeline)
    try:
        if hotel_name:
            engine.sync_hotel_reviews(
                hotel_name=hotel_name,
                maps_url=maps_url,
                address=address,
                max_reviews=max_reviews,
            )
        else:
            engine.sync_hotel_chain(max_reviews_per_branch=max_reviews)
    except Exception as exc:
        logger.exception("Loi trong tac vu dong bo ngam: %s", exc)
    finally:
        engine.close()


@router.post("/trigger", response_model=SyncTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(
    background_tasks: BackgroundTasks,
    payload: Optional[SyncTriggerRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kich hoat dong bo danh gia moi cho mot chi nhanh cu the hoac toan chuoi khach san."""
    req = payload or SyncTriggerRequest()
    target_name = None
    target_url = None
    target_address = None

    if req.hotel_id is not None:
        hotel = db.query(Hotel).filter(Hotel.id == req.hotel_id).first()
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Khong tim thay khach san voi ID={req.hotel_id}.",
            )
        target_name = hotel.name
        target_url = hotel.google_maps_url
        target_address = hotel.address

    background_tasks.add_task(
        _run_sync_job,
        target_name,
        target_url,
        target_address,
        req.max_reviews,
    )

    scope_desc = f"chi nhanh '{target_name}'" if target_name else "toan bo chuoi khach san"
    return SyncTriggerResponse(
        status="accepted",
        message=f"Da tiep nhan yeu cau dong bo du lieu cho {scope_desc}.",
        target_hotel_id=req.hotel_id,
        max_reviews=req.max_reviews,
    )
