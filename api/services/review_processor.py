"""
Module: review_processor.py
Mo ta: Dich vu dung chung xu ly luu ket qua phan tich ABSA, Intent va sinh Task tu dong.
       Duoc tai su dung boi ca luong dong bo hang loat (sync_and_process.py) va API phan tich truc tiep.
"""

from typing import Optional
from sqlalchemy.orm import Session

from database.models import (
    AspectResult,
    Department,
    Review,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
)

# Bang quy tac dinh tuyen phong ban tu dong dua tren ma khia canh VLSP
DEPARTMENT_ROUTING_RULES = (
    ("CLEANLINESS", Department.HOUSEKEEPING),
    ("FOOD&DRINKS", Department.F_AND_B),
    ("SERVICE", Department.FRONT_DESK),
    ("FACILITIES", Department.MAINTENANCE),
    ("COMFORT", Department.MAINTENANCE),
)


def determine_department(aspect_category: str) -> Department:
    """Xac dinh phong ban phu trach dua tren khia canh tieu cuc phat hien duoc."""
    asp = aspect_category.upper()
    for keyword, department in DEPARTMENT_ROUTING_RULES:
        if keyword in asp:
            return department
    return Department.MANAGEMENT


def apply_analysis_to_review(db: Session, review: Review, analysis: dict) -> Optional[Task]:
    """
    Luu ket qua phan tich ABSA, cap nhat nhan Intent vao Review va tu dong tao Task neu can.
    Khong tu dong commit de caller chu dong quan ly transaction.
    """
    for aspect in analysis.get("aspects", []):
        db.add(
            AspectResult(
                review_id=review.id,
                aspect_category=aspect["aspect"],
                sentiment=aspect["sentiment"],
                confidence=aspect["confidence"],
            )
        )

    intent = analysis.get("intent", "GENERAL_FEEDBACK")
    review.intent = intent
    review.intent_reason = analysis.get("intent_reason", "")
    review.is_processed = True

    task_action = analysis.get("task_action", {})
    if not task_action.get("create_task"):
        return None

    neg_aspects = [a["aspect"] for a in analysis.get("aspects", []) if a.get("sentiment") == "negative"]
    target_dept = determine_department(neg_aspects[0]) if neg_aspects else Department.MANAGEMENT

    is_critical = intent == "CRITICAL_COMPLAINT"
    task_type_enum = TaskType.CRITICAL_TASK if is_critical else TaskType.IMPROVEMENT_TASK
    priority_enum = TaskPriority.HIGH if is_critical else TaskPriority.MEDIUM

    prefix = "KHAN CAP" if is_critical else "DE XUAT"
    author_label = review.author_name or "Khach hang"
    task_title = f"[{prefix}] {author_label} ({review.rating}*)"
    aspect_summary = ", ".join(neg_aspects) if neg_aspects else "Theo danh gia chung"
    task_desc = f"Noi dung: {review.text}\nKhia canh phan anh: {aspect_summary}"

    new_task = Task(
        hotel_id=review.hotel_id,
        review_id=review.id,
        title=task_title,
        description=task_desc,
        task_type=task_type_enum,
        priority=priority_enum,
        status=TaskStatus.PENDING,
        department=target_dept,
    )
    db.add(new_task)
    return new_task
