"""
Module: connection.py
Mo ta: Quan ly ket noi Co so Du lieu, phien lam viec (Session) va khoi tao bang.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hotel_analytics.db")

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

def init_db():
    """
    Khoi tao toan bo cac bang du lieu neu chua ton tai.
    """
    from . import models
    Base.metadata.create_all(bind=engine)