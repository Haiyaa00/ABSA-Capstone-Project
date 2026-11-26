"""
Router: auth.py
Mo ta: Cac API xac thuc nguoi dung (Dang nhap, Dang ky, Thong tin tai khoan).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user
from api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from api.services.auth_service import AuthServiceError, authenticate_user, register_user
from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Xac thuc tai khoan quan ly va cap JWT access token."""
    try:
        return authenticate_user(db=db, payload=payload)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Dang ky tai khoan quan ly moi gan voi mot chi nhanh khach san."""
    try:
        return register_user(db=db, payload=payload)
    except AuthServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Lay thong tin tai khoan dang dang nhap."""
    return UserOut.model_validate(current_user)
