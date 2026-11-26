"""
Module: dependencies.py
Mo ta: Cung cap cac FastAPI Dependencies dung chung:
       - Ket noi Database Session (get_db)
       - Xac thuc JWT nguoi dung (get_current_user)
       - Quan ly AI Engine theo mau Singleton / Lazy-load de toi uu RAM
"""

import threading
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.security import decode_access_token
from database.connection import get_db
from database.models import User
from processors.reply_generator import AIReplyGenerator

bearer_scheme = HTTPBearer(auto_error=False)

_pipeline_lock = threading.Lock()
_acsa_pipeline_instance = None

_reply_lock = threading.Lock()
_reply_generator_instance: Optional[AIReplyGenerator] = None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Xac thuc Bearer JWT Token va tra ve doi tuong User dang hoat dong."""
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Thong tin xac thuc khong hop le hoac da het han.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise auth_error

    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise auth_error

    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user or not user.is_active:
        raise auth_error

    return user


def get_reply_generator() -> AIReplyGenerator:
    """Tra ve Singleton AIReplyGenerator (nhe, khong nap TensorFlow/PhoBERT)."""
    global _reply_generator_instance
    if _reply_generator_instance is None:
        with _reply_lock:
            if _reply_generator_instance is None:
                _reply_generator_instance = AIReplyGenerator()
    return _reply_generator_instance


def get_acsa_pipeline():
    """
    Tra ve Singleton ACSAPipeline (PhoBERT + VnCoreNLP).
    Khoi tao luoi (Lazy-load) mot lan duy nhat khi co yeu cau phan tich hoac dong bo.
    """
    global _acsa_pipeline_instance
    if _acsa_pipeline_instance is None:
        with _pipeline_lock:
            if _acsa_pipeline_instance is None:
                from acsa_pipeline import ACSAPipeline
                _acsa_pipeline_instance = ACSAPipeline()
    return _acsa_pipeline_instance
