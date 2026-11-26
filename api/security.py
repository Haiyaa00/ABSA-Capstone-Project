"""
Module: security.py
Mo ta: Cung cap cac ham bao mat: bam mat khau bang bcrypt va tao/xac thuc JWT Token.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from core.config import settings

JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def hash_password(plain_password: str) -> str:
    """Bam mat khau goc bang bcrypt kem salt ngau nhien."""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiem tra mat khau goc co khop voi chuoi hash da luu hay khong."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def create_access_token(subject: str, extra_claims: Optional[dict] = None, expires_delta: Optional[timedelta] = None) -> str:
    """Tao JWT access token co thoi han su dung."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Giai ma va xac thuc JWT access token. Tra ve None neu token khong hop le hoac het han."""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
