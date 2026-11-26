"""
Module: auth_service.py
Mo ta: Tang nghiep vu Xac thuc & Dang ky tai khoan quan ly khach san.
"""

from sqlalchemy.orm import Session

from api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from api.security import create_access_token, hash_password, verify_password
from api.services.task_service import parse_enum_value
from database.models import Hotel, User, UserRole


class AuthServiceError(Exception):
    """Ngoai le nghiep vu cho tang xac thuc kem ma trang thai HTTP tuong ung."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def authenticate_user(db: Session, payload: LoginRequest) -> TokenResponse:
    """Kiem tra thong tin dang nhap va cap JWT access token."""
    user = db.query(User).filter(User.username == payload.username.strip()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise AuthServiceError(401, "Ten dang nhap hoac mat khau khong chinh xac.")

    if not user.is_active:
        raise AuthServiceError(403, "Tai khoan da bi khoa.")

    token = create_access_token(
        subject=user.username,
        extra_claims={"user_id": user.id, "role": user.role.value, "hotel_id": user.hotel_id},
    )
    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


def register_user(db: Session, payload: RegisterRequest) -> UserOut:
    """Tao tai khoan quan ly moi gan voi mot chi nhanh khach san."""
    username = payload.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise AuthServiceError(409, "Ten dang nhap da ton tai.")

    hotel = db.query(Hotel).filter(Hotel.id == payload.hotel_id).first()
    if not hotel:
        raise AuthServiceError(404, "Khong tim thay chi nhanh khach san.")

    try:
        role_enum = parse_enum_value(UserRole, payload.role or "MANAGER", "role")
    except ValueError as exc:
        raise AuthServiceError(400, str(exc)) from exc

    new_user = User(
        hotel_id=hotel.id,
        username=username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=role_enum,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserOut.model_validate(new_user)
