"""
Module: dashboard_service.py
Mo ta: Tong hop so lieu thong ke cho man hinh Dashboard Android:
       - Chi so tong quan & phan bo sao
       - 6 nhom khia canh lon (ve bieu do Radar / Bar Chart)
       - Top khia canh chi tiet bi che / duoc khen nhieu nhat (Drill-down 34 nhan VLSP)
       - Canh bao su co khan cap chua xu ly
"""

from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session

from api.schemas import (
    AspectDrilldown,
    CategoryGroupStat,
    CriticalAlertItem,
    DashboardStatsResponse,
    DetailedAspectStat,
    OverviewStats,
)
from database.models import AspectResult, Hotel, Review, Task, TaskStatus, TaskType

# Bang anh xa dong nhat tu 34 nhan VLSP ve 6 nhom truc quan tren Mobile Dashboard
ASPECT_GROUP_DEFINITIONS = (
    ("ROOMS", "Phong oc", ("ROOMS#",)),
    ("ROOM_AMENITIES", "Tien nghi phong", ("ROOM_AMENITIES#",)),
    ("FACILITIES", "Co so vat chat", ("FACILITIES#",)),
    ("SERVICE", "Dich vu & Le tan", ("SERVICE#",)),
    ("FOOD&DRINKS", "Am thuc", ("FOOD&DRINKS#",)),
    ("LOCATION_GENERAL", "Vi tri & Tong the", ("LOCATION#", "HOTEL#")),
)


def _resolve_aspect_group(aspect_category: str) -> str:
    upper_name = aspect_category.upper()
    for group_key, _, prefixes in ASPECT_GROUP_DEFINITIONS:
        if any(upper_name.startswith(prefix) for prefix in prefixes):
            return group_key
    return "LOCATION_GENERAL"


def get_dashboard_stats(db: Session, hotel_id: Optional[int] = None) -> Optional[DashboardStatsResponse]:
    """Tinh toan day du so lieu Dashboard cho mot chi nhanh hoac toan chuoi."""
    hotel_name = "Toan chuoi Khach san"
    if hotel_id is not None:
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if not hotel:
            return None
        hotel_name = hotel.name

    # 1. Truy van Reviews
    review_query = db.query(Review)
    if hotel_id is not None:
        review_query = review_query.filter(Review.hotel_id == hotel_id)
    reviews = review_query.all()

    total_reviews = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / total_reviews, 2) if total_reviews else 0.0
    unreplied_count = sum(1 for r in reviews if not r.is_replied)

    star_dist = {str(star): 0 for star in range(1, 6)}
    for r in reviews:
        star_key = str(min(max(int(r.rating), 1), 5))
        star_dist[star_key] += 1

    # 2. Truy van Tasks dang cho xu ly & Canh bao khan cap
    task_query = db.query(Task).filter(Task.status == TaskStatus.PENDING)
    if hotel_id is not None:
        task_query = task_query.filter(Task.hotel_id == hotel_id)
    pending_tasks = task_query.order_by(Task.created_at.desc()).all()

    critical_pending = [t for t in pending_tasks if t.task_type == TaskType.CRITICAL_TASK]

    hotel_map = {h.id: h.name for h in db.query(Hotel).all()}
    review_map = {r.id: r for r in reviews}

    critical_alerts = []
    for task in critical_pending[:5]:
        rev = review_map.get(task.review_id) or db.query(Review).filter(Review.id == task.review_id).first()
        if not rev:
            continue
        excerpt = rev.text[:120] + "..." if len(rev.text) > 120 else rev.text
        critical_alerts.append(
            CriticalAlertItem(
                task_id=task.id,
                review_id=rev.id,
                hotel_id=task.hotel_id,
                hotel_name=hotel_map.get(task.hotel_id, ""),
                author_name=rev.author_name,
                rating=rev.rating,
                title=task.title,
                excerpt=excerpt,
                department=task.department.value,
                created_at=task.created_at,
            )
        )

    overview = OverviewStats(
        total_reviews=total_reviews,
        avg_rating=avg_rating,
        unreplied_count=unreplied_count,
        pending_tasks_count=len(pending_tasks),
        critical_pending_count=len(critical_pending),
        star_distribution=star_dist,
    )

    # 3. Tong hop AspectResults thanh 6 nhom & Drill-down 34 khia canh chi tiet
    aspect_query = db.query(AspectResult).join(Review, AspectResult.review_id == Review.id)
    if hotel_id is not None:
        aspect_query = aspect_query.filter(Review.hotel_id == hotel_id)
    aspects = aspect_query.all()

    group_counts = {key: {"positive": 0, "negative": 0, "neutral": 0} for key, _, _ in ASPECT_GROUP_DEFINITIONS}
    detailed_counts = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0})

    for asp in aspects:
        sentiment = asp.sentiment.lower()
        if sentiment not in ("positive", "negative", "neutral"):
            sentiment = "neutral"
        grp_key = _resolve_aspect_group(asp.aspect_category)
        group_counts[grp_key][sentiment] += 1
        detailed_counts[asp.aspect_category][sentiment] += 1

    category_groups = []
    for key, label, _ in ASPECT_GROUP_DEFINITIONS:
        counts = group_counts[key]
        total_m = counts["positive"] + counts["negative"] + counts["neutral"]
        sat_rate = round((counts["positive"] / total_m) * 100, 1) if total_m else 0.0
        category_groups.append(
            CategoryGroupStat(
                group_key=key,
                group_label=label,
                positive_count=counts["positive"],
                negative_count=counts["negative"],
                neutral_count=counts["neutral"],
                total_mentions=total_m,
                satisfaction_rate=sat_rate,
            )
        )

    detailed_list = [
        DetailedAspectStat(
            aspect_category=name,
            positive_count=c["positive"],
            negative_count=c["negative"],
            neutral_count=c["neutral"],
            total_mentions=c["positive"] + c["negative"] + c["neutral"],
        )
        for name, c in detailed_counts.items()
    ]

    top_negative = sorted(
        [d for d in detailed_list if d.negative_count > 0],
        key=lambda x: (x.negative_count, x.total_mentions),
        reverse=True,
    )[:5]

    top_positive = sorted(
        [d for d in detailed_list if d.positive_count > 0],
        key=lambda x: (x.positive_count, x.total_mentions),
        reverse=True,
    )[:5]

    return DashboardStatsResponse(
        hotel_id=hotel_id,
        hotel_name=hotel_name,
        overview=overview,
        category_groups=category_groups,
        aspect_drilldown=AspectDrilldown(
            top_negative_aspects=top_negative,
            top_positive_aspects=top_positive,
        ),
        critical_alerts=critical_alerts,
    )
