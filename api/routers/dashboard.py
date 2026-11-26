"""
Router: dashboard.py
Mo ta: API thong ke chat luong dich vu theo khia canh ABSA cho man hinh Dashboard.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from api.schemas import DashboardStatsResponse
from api.services.dashboard_service import get_dashboard_stats
from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
def dashboard_stats(
    hotel_id: Optional[int] = Query(default=None, ge=1, description="ID chi nhanh (bo trong de xem toan chuoi)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lay so lieu thong ke tong quan, 6 nhom khia canh, Top khia canh chi tiet va canh bao khan cap."""
    stats = get_dashboard_stats(db, hotel_id=hotel_id)
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khong tim thay khach san voi ID={hotel_id}.",
        )
    return stats
