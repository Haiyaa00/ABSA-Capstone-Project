"""
Module: connection.py
Mo ta: Quan ly ket noi Co so Du lieu, phien lam viec (Session) va khoi tao bang.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import settings

DATABASE_URL = settings.DATABASE_URL

# Cau hinh engine cho SQLite hoac cac RDBMS khac
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Dependency cung cap Database Session cho cac tac vu hoac REST API.
    Dam bao dong session an toan sau khi thuc thi xong.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_schema_migrations():
    """
    Kiem tra va bo sung cac cot con thieu cho SQLite ma khong lam mat du lieu cu.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    migrations = {
        "reviews": {
            "intent": "VARCHAR(50) DEFAULT 'GENERAL_FEEDBACK'",
            "intent_reason": "TEXT",
            "is_replied": "BOOLEAN DEFAULT 0",
        },
        "tasks": {
            "resolution_note": "TEXT",
        },
        "reply_logs": {
            "updated_at": "DATETIME",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in migrations.items():
            existing_rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            existing_cols = {row[1] for row in existing_rows}
            for col_name, col_def in columns.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))

def init_db():
    """
    Khoi tao toan bo cac bang du lieu neu chua ton tai va chay migration an toan.
    """
    from . import models
    Base.metadata.create_all(bind=engine)
    ensure_schema_migrations()