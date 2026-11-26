"""
Router: hotels.py
Mo ta: Cung cap danh sach cac chi nhanh khach san trong chuoi de chuyen doi tren Mobile App.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from api.schemas import HotelOut
from api.services.hotel_service import list_hotels_with_stats
from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/api/hotels", tags=["Hotels"])


@router.get("", response_model=List[HotelOut])
def list_hotels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lay danh sach chi nhanh khach san kem thong ke nhanh ve danh gia va cong viec."""
    return list_hotels_with_stats(db)
