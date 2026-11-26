"""
Module: schemas.py
Mo ta: Dinh nghia cac Pydantic Schemas chuan hoa du lieu Request/Response JSON cho REST API.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# =====================================================================
# AUTHENTICATION & USERS
# =====================================================================

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    hotel_id: int = Field(..., ge=1)
    role: Optional[str] = Field(default="MANAGER")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# =====================================================================
# HOTELS
# =====================================================================

class HotelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: Optional[str] = None
    google_maps_url: Optional[str] = None
    total_reviews: int = 0
    pending_tasks: int = 0
    avg_rating: float = 0.0


# =====================================================================
# DASHBOARD ANALYTICS
# =====================================================================

class OverviewStats(BaseModel):
    total_reviews: int
    avg_rating: float
    unreplied_count: int
    pending_tasks_count: int
    critical_pending_count: int
    star_distribution: Dict[str, int]


class CategoryGroupStat(BaseModel):
    group_key: str
    group_label: str
    positive_count: int
    negative_count: int
    neutral_count: int
    total_mentions: int
    satisfaction_rate: float


class DetailedAspectStat(BaseModel):
    aspect_category: str
    positive_count: int
    negative_count: int
    neutral_count: int
    total_mentions: int


class AspectDrilldown(BaseModel):
    top_negative_aspects: List[DetailedAspectStat]
    top_positive_aspects: List[DetailedAspectStat]


class CriticalAlertItem(BaseModel):
    task_id: int
    review_id: int
    hotel_id: int
    hotel_name: str
    author_name: Optional[str] = None
    rating: int
    title: str
    excerpt: str
    department: str
    created_at: datetime


class DashboardStatsResponse(BaseModel):
    hotel_id: Optional[int] = None
    hotel_name: str
    overview: OverviewStats
    category_groups: List[CategoryGroupStat]
    aspect_drilldown: AspectDrilldown
    critical_alerts: List[CriticalAlertItem]


# =====================================================================
# REVIEWS, ASPECTS & AI REPLIES
# =====================================================================

class AspectResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    aspect_category: str
    sentiment: str
    confidence: float


class ReplyLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: int
    generated_reply: str
    source: str
    is_used: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    review_id: int
    title: str
    description: str
    task_type: str
    priority: str
    status: str
    department: str
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    hotel_name: Optional[str] = None
    source: str
    author_name: Optional[str] = None
    rating: int
    text: str
    review_time: Optional[datetime] = None
    is_processed: bool
    intent: Optional[str] = "GENERAL_FEEDBACK"
    intent_reason: Optional[str] = None
    is_replied: bool = False
    aspects: List[AspectResultOut] = []
    latest_reply: Optional[ReplyLogOut] = None


class ReviewDetailOut(ReviewOut):
    tasks: List[TaskOut] = []
    reply_logs: List[ReplyLogOut] = []


class PaginatedReviewsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[ReviewOut]


class GenerateReplyRequest(BaseModel):
    force_regenerate: bool = False
    hotel_name: Optional[str] = None


class GenerateReplyResponse(BaseModel):
    reply_log: ReplyLogOut
    cached: bool = False


class UpdateReplyRequest(BaseModel):
    edited_reply: Optional[str] = Field(default=None, min_length=5)
    mark_as_used: bool = True


class ManualAnalyzeRequest(BaseModel):
    hotel_id: int = Field(..., ge=1)
    text: str = Field(..., min_length=5, max_length=3000)
    rating: int = Field(..., ge=1, le=5)
    author_name: Optional[str] = Field(default="Khach hang demo", max_length=255)
    save_to_db: bool = True


class ManualAnalyzeResponse(BaseModel):
    saved_to_db: bool
    review_id: Optional[int] = None
    created_task_id: Optional[int] = None
    text: str
    rating: int
    aspects_count: int
    aspects: List[dict]
    intent: str
    intent_confidence: float
    detection_method: str
    intent_reason: str
    task_action: dict


# =====================================================================
# TASKS MANAGEMENT
# =====================================================================

class PaginatedTasksResponse(BaseModel):
    total: int
    items: List[TaskOut]


class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None
    department: Optional[str] = None
    priority: Optional[str] = None
    resolution_note: Optional[str] = Field(default=None, max_length=2000)


# =====================================================================
# DATA SYNC (APIFY)
# =====================================================================

class SyncTriggerRequest(BaseModel):
    hotel_id: Optional[int] = None
    max_reviews: int = Field(default=10, ge=1, le=50)


class SyncTriggerResponse(BaseModel):
    status: str
    message: str
    target_hotel_id: Optional[int] = None
    max_reviews: int
