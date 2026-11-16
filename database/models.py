"""
Module: models.py
Mo ta: Dinh nghia cac thuc the du lieu (ORM Models) theo chuan quan he:
       - Hotel: Thong tin khach san quan ly
       - User: Tai khoan nguoi dung (Ban quan ly, Nhan vien)
       - Review: Danh gia thu thap tu Google Maps / OTA
       - AspectResult: Ket qua boc tach khia canh tu mo hinh PhoBERT
       - Task: Cong viec tu dong phan cong xu ly su co
       - ReplyLog: Nhat ky cau phan hoi goi y tu Gemini LLM
"""

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from .connection import Base

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    STAFF = "STAFF"

class ReviewSource(str, enum.Enum):
    GOOGLE_MAPS = "GOOGLE_MAPS"
    AGODA = "AGODA"
    BOOKING = "BOOKING"
    MANUAL = "MANUAL"

class TaskType(str, enum.Enum):
    CRITICAL_TASK = "CRITICAL_TASK"
    IMPROVEMENT_TASK = "IMPROVEMENT_TASK"

class TaskPriority(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"

class Department(str, enum.Enum):
    HOUSEKEEPING = "HOUSEKEEPING"       # Bo phan Buong phong
    FRONT_DESK = "FRONT_DESK"           # Bo phan Le tan
    F_AND_B = "F_AND_B"                 # Bo phan Nha hang / Am thuc
    MAINTENANCE = "MAINTENANCE"         # Bo phan Ky thuat / Bao tri
    MANAGEMENT = "MANAGEMENT"           # Ban Giam doc / Quan ly

# =====================================================================
# THUC THE CO SO DU LIEU
# =====================================================================

class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)
    google_place_id = Column(String(100), nullable=True, index=True)
    google_maps_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Quan he
    users = relationship("User", back_populates="hotel", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="hotel", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="hotel", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.MANAGER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Quan he
    hotel = relationship("Hotel", back_populates="users")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    source = Column(Enum(ReviewSource), default=ReviewSource.GOOGLE_MAPS, nullable=False)
    external_id = Column(String(150), nullable=True, index=True) # ID danh gia tren Google Maps de chong trung
    author_name = Column(String(255), nullable=True)
    rating = Column(Integer, nullable=False) # So sao: 1 - 5
    text = Column(Text, nullable=False)
    review_time = Column(DateTime, nullable=True)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    is_processed = Column(Boolean, default=False, index=True) # Danh dau da chay qua mo hinh AI

    # Quan he
    hotel = relationship("Hotel", back_populates="reviews")
    aspect_results = relationship("AspectResult", back_populates="review", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="review", cascade="all, delete-orphan")
    reply_logs = relationship("ReplyLog", back_populates="review", cascade="all, delete-orphan")


class AspectResult(Base):
    __tablename__ = "aspect_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    aspect_category = Column(String(100), nullable=False, index=True) # VD: ROOMS#CLEANLINESS
    sentiment = Column(String(20), nullable=False)                    # positive, negative, neutral
    confidence = Column(Float, nullable=False)                       # Xac suat du doan
    created_at = Column(DateTime, default=datetime.utcnow)

    # Quan he
    review = relationship("Review", back_populates="aspect_results")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    department = Column(Enum(Department), default=Department.MANAGEMENT, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Quan he
    hotel = relationship("Hotel", back_populates="tasks")
    review = relationship("Review", back_populates="tasks")


class ReplyLog(Base):
    __tablename__ = "reply_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    generated_reply = Column(Text, nullable=False)
    source = Column(String(50), default="gemini_llm") # gemini_llm hoac fallback
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Quan he
    review = relationship("Review", back_populates="reply_logs")