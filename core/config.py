"""
Module: config.py
Mo ta: Tap trung hoa toan bo bien moi truong va cau hinh he thong tai mot noi duy nhat.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def configure_tf_env() -> None:
    """Thiet lap bien moi truong TensorFlow / Keras Legacy truoc khi nap mo hinh."""
    os.environ.setdefault("USE_TORCH", "0")
    os.environ.setdefault("USE_TF", "1")
    os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


@dataclass(frozen=True)
class Settings:
    """Cau hinh he thong nap tu .env voi gia tri mac dinh an toan."""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./hotel_analytics.db")

    # Gemini LLM
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    # Hotel & Branding defaults
    DEFAULT_HOTEL_NAME: str = os.getenv("DEFAULT_HOTEL_NAME", "Khach san chung toi")
    HOTEL_HOTLINE: str = os.getenv("HOTEL_HOTLINE", "Hotline Cham soc Khach hang")
    HOTEL_MANAGER_NAME: str = os.getenv("HOTEL_MANAGER_NAME", "Ban Quan ly Khach san")

    # Apify Data Ingestion
    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")
    TARGET_GOOGLE_MAPS_URL: str = os.getenv("TARGET_GOOGLE_MAPS_URL", "")

    # NLP & Model Paths
    VNCORENLP_DIR: str = os.getenv("VNCORENLP_DIR", "D:/VnCoreNLP")

    # JWT Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "hau_absa_hotel_secret_key_2026_dev")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


settings = Settings()
