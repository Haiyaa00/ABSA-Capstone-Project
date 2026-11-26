"""
Module: task_service.py
Mo ta: Tang nghiep vu Quan ly Cong viec (Task Management) cho cac phong ban khach san.
"""

from typing import Optional, Type, TypeVar
from enum import Enum

from sqlalchemy import case
from sqlalchemy.orm import Session

from core.time_utils import utc_now

from api.schemas import PaginatedTasksResponse, TaskOut, TaskUpdateRequest
from database.models import Department, Task, TaskPriority, TaskStatus

EnumT = TypeVar("EnumT", bound=Enum)


def parse_enum_value(enum_cls: Type[EnumT], raw_value: str, field_name: str) -> EnumT:
    """Chuyen doi chuoi sang Enum tuong ung, nem ValueError ro rang neu khong hop le."""
    normalized = raw_value.strip().upper()
    try:
        return enum_cls(normalized)
    except ValueError as exc:
        allowed = [item.value for item in enum_cls]
        raise ValueError(f"Gia tri '{raw_value}' khong hop le cho {field_name}. Chap nhan: {allowed}") from exc


def list_tasks(
    db: Session,
    hotel_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    department: Optional[str] = None,
) -> PaginatedTasksResponse:
    """Lay danh sach cong viec, sap xep uu tien PENDING va HIGH len dau."""
    query = db.query(Task)

    if hotel_id is not None:
        query = query.filter(Task.hotel_id == hotel_id)
    if status:
        query = query.filter(Task.status == parse_enum_value(TaskStatus, status, "status"))
    if priority:
        query = query.filter(Task.priority == parse_enum_value(TaskPriority, priority, "priority"))
    if department:
        query = query.filter(Task.department == parse_enum_value(Department, department, "department"))

    status_order = case(
        (Task.status == TaskStatus.PENDING, 0),
        (Task.status == TaskStatus.IN_PROGRESS, 1),
        else_=2,
    )
    priority_order = case(
        (Task.priority == TaskPriority.HIGH, 0),
        (Task.priority == TaskPriority.MEDIUM, 1),
        else_=2,
    )

    tasks = (
        query.order_by(status_order, priority_order, Task.created_at.desc())
        .all()
    )

    return PaginatedTasksResponse(
        total=len(tasks),
        items=[TaskOut.model_validate(t) for t in tasks],
    )


def update_task(db: Session, task_id: int, payload: TaskUpdateRequest) -> Optional[TaskOut]:
    """Cap nhat linh hoat trang thai, phong ban, muc uu tien va ghi chu xu ly cua Task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    if payload.status is not None:
        new_status = parse_enum_value(TaskStatus, payload.status, "status")
        task.status = new_status
        task.resolved_at = utc_now() if new_status == TaskStatus.RESOLVED else None

    if payload.department is not None:
        task.department = parse_enum_value(Department, payload.department, "department")

    if payload.priority is not None:
        task.priority = parse_enum_value(TaskPriority, payload.priority, "priority")

    if payload.resolution_note is not None:
        task.resolution_note = payload.resolution_note.strip()

    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task)
