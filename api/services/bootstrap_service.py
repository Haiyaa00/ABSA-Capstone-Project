"""
Module: bootstrap_service.py
Mo ta: Khoi tao du lieu nen tang (backfill cot intent cho review cu, tao tai khoan mau).
"""

from sqlalchemy.orm import Session

from api.security import hash_password
from database.models import Hotel, Review, Task, TaskType, User, UserRole


DEFAULT_HOTELS = (
    {
        "name": "Khach san Muong Thanh Grand Ha Noi",
        "address": "KDT Linh Dam, Hoang Mai, Ha Noi",
        "google_maps_url": "https://maps.app.goo.gl/zaLutmJjLD8G98fu8",
    },
    {
        "name": "Khach san Muong Thanh Luxury Quang Ninh",
        "address": "Duong Ha Long, Bai Chay, TP. Ha Long, Quang Ninh",
        "google_maps_url": "https://maps.app.goo.gl/jtXXvZijC9RyoocbA",
    },
    {
        "name": "Khach san Muong Thanh Holiday Moc Chau",
        "address": "Hoang Quoc Viet, Phieng Luong, Moc Chau, Son La",
        "google_maps_url": "https://maps.app.goo.gl/drgHsEUBkmk6DG9z9",
    },
)


def _ensure_default_hotels(db: Session) -> Hotel:
    """Dam bao he thong co it nhat mot khach san de lien ket tai khoan quan ly."""
    first_hotel = db.query(Hotel).order_by(Hotel.id.asc()).first()
    if first_hotel:
        return first_hotel

    created = []
    for item in DEFAULT_HOTELS:
        hotel = Hotel(**item)
        db.add(hotel)
        created.append(hotel)
    db.commit()
    db.refresh(created[0])
    return created[0]


def _backfill_review_intents(db: Session) -> None:
    """Dong bo gia tri intent cho cac ban ghi review cu chua co thong tin intent."""
    reviews_missing_intent = db.query(Review).filter(
        (Review.intent == None) | (Review.intent == "")
    ).all()
    if not reviews_missing_intent:
        return

    for rev in reviews_missing_intent:
        linked_task = db.query(Task).filter(Task.review_id == rev.id).first()
        if linked_task:
            rev.intent = (
                "CRITICAL_COMPLAINT"
                if linked_task.task_type == TaskType.CRITICAL_TASK
                else "IMPROVEMENT_SUGGESTION"
            )
        else:
            rev.intent = "GENERAL_FEEDBACK"
    db.commit()


def _seed_default_users(db: Session, default_hotel_id: int) -> None:
    """Tao tai khoan quan ly mau neu chua ton tai trong bang users."""
    seed_accounts = (
        ("admin", "123456", "Quan tri vien Chuoi Muong Thanh", UserRole.ADMIN),
        ("manager_hn", "123456", "Quan ly Chi nhanh Ha Noi", UserRole.MANAGER),
    )

    for username, raw_pw, full_name, role in seed_accounts:
        exists = db.query(User).filter(User.username == username).first()
        if not exists:
            db.add(
                User(
                    hotel_id=default_hotel_id,
                    username=username,
                    hashed_password=hash_password(raw_pw),
                    full_name=full_name,
                    role=role,
                    is_active=True,
                )
            )
    db.commit()


def bootstrap_database(db: Session) -> None:
    """Chay toan bo quy trinh khoi tao du lieu mac dinh an toan khi khoi dong server."""
    primary_hotel = _ensure_default_hotels(db)
    _backfill_review_intents(db)
    _seed_default_users(db, primary_hotel.id)
