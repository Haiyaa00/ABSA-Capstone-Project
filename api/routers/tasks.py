"""
Router: tasks.py
Mo ta: Cac API Quan ly Cong viec xu ly su co (Task Management) cho Ban Quan ly.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from api.schemas import PaginatedTasksResponse, TaskOut, TaskUpdateRequest
from api.services.task_service import list_tasks, update_task
from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/api/tasks", tags=["Task Management"])


@router.get("", response_model=PaginatedTasksResponse)
def get_tasks(
    hotel_id: Optional[int] = Query(default=None, ge=1),
    status_filter: Optional[str] = Query(default=None, alias="status", description="PENDING | IN_PROGRESS | RESOLVED"),
    priority: Optional[str] = Query(default=None, description="HIGH | MEDIUM | LOW"),
    department: Optional[str] = Query(default=None, description="HOUSEKEEPING | FRONT_DESK | F_AND_B | MAINTENANCE | MANAGEMENT"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lay danh sach cong viec can xu ly theo chi nhanh, trang thai, muc uu tien va phong ban."""
    try:
        return list_tasks(
            db=db,
            hotel_id=hotel_id,
            status=status_filter,
            priority=priority,
            department=department,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{task_id}", response_model=TaskOut)
def patch_task(
    task_id: int,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cap nhat trang thai, chuyen phong ban, doi muc uu tien hoac bo sung ghi chu xu ly."""
    try:
        updated = update_task(db=db, task_id=task_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khong tim thay cong viec voi ID={task_id}.",
        )
    return updated
