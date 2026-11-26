"""
Module: hotel_service.py
Mo ta: Tang nghiep vu truy van danh sach chi nhanh khach san kem chi so tong hop bang SQL aggregation.
"""

from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.schemas import HotelOut
from database.models import Hotel, Review, Task, TaskStatus


def list_hotels_with_stats(db: Session) -> List[HotelOut]:
    """Lay danh sach chi nhanh kem so review, sao trung binh va so task cho xu ly (tranh N+1 query)."""
    hotels = db.query(Hotel).order_by(Hotel.id.asc()).all()

    review_rows = (
        db.query(
            Review.hotel_id,
            func.count(Review.id),
            func.avg(Review.rating),
        )
        .group_by(Review.hotel_id)
        .all()
    )
    review_stats = {
        hotel_id: (count, round(float(avg), 2) if avg is not None else 0.0)
        for hotel_id, count, avg in review_rows
    }

    task_rows = (
        db.query(Task.hotel_id, func.count(Task.id))
        .filter(Task.status == TaskStatus.PENDING)
        .group_by(Task.hotel_id)
        .all()
    )
    pending_task_counts = {hotel_id: count for hotel_id, count in task_rows}

    results = []
    for hotel in hotels:
        total_reviews, avg_rating = review_stats.get(hotel.id, (0, 0.0))
        results.append(
            HotelOut(
                id=hotel.id,
                name=hotel.name,
                address=hotel.address,
                google_maps_url=hotel.google_maps_url,
                total_reviews=total_reviews,
                pending_tasks=pending_task_counts.get(hotel.id, 0),
                avg_rating=avg_rating,
            )
        )
    return results
