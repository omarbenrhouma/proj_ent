from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    education: str | None = None
    experience: str | None = None
    cv_name: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    availability: str | None = None
    summary: str | None = None


class CvResponse(BaseModel):
    id: str
    original_name: str
    mime_type: str
    size_bytes: int


class ProfileUpdateRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=40)
    education: str | None = Field(default=None, max_length=4000)
    experience: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=150)
    linkedin_url: str | None = Field(default=None, max_length=500)
    availability: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=2000)


class QuestionResponse(BaseModel):
    id: str
    position: int
    statement: str
    question_type: str
    options: list[dict[str, Any]]
    points: float
    skill: str
    category: str


class TestStateResponse(BaseModel):
    id: str
    status: str
    version: str
    duration_seconds: int
    started_at: datetime | None
    expires_at: datetime | None
    answered_count: int
    total_questions: int


class JobOfferResponse(BaseModel):
    id: str
    name: str
    job_title: str
    duration_seconds: int
    show_result_to_candidate: bool
    status: str = "AVAILABLE"


class AnswerRequest(BaseModel):
    answer: Any
    marked_for_review: bool = False


class ScoreResponse(BaseModel):
    earned_points: float
    maximum_points: float
    normalized_score: float
    level: str
    breakdown: dict[str, Any]


class CandidateListItem(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    status: str
    version: str
    score: float | None = None
    level: str | None = None
    submitted_at: datetime | None = None


class CandidateAnswerDetail(BaseModel):
    position: int
    statement: str
    category: str
    skill: str
    candidate_answer: Any = None
    correct_answer: list[str]
    earned_points: float
    maximum_points: float


class CandidateDetailResponse(CandidateListItem):
    phone: str | None = None
    education: str | None = None
    experience: str | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    answers: list[CandidateAnswerDetail] = Field(default_factory=list)
    location: str | None = None
    linkedin_url: str | None = None
    availability: str | None = None
    summary: str | None = None


class CandidateManageRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    education: str | None = Field(default=None, max_length=4000)
    experience: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=150)
    linkedin_url: str | None = Field(default=None, max_length=500)
    availability: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=150)
    linkedin_url: str | None = Field(default=None, max_length=500)
    availability: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=150)
    linkedin_url: str | None = Field(default=None, max_length=500)
    availability: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=2000)


class QuestionOptionPayload(BaseModel):
    key: str = Field(min_length=1, max_length=20)
    label: str = Field(min_length=1, max_length=500)
    correct: bool = False


class AdminQuestionItem(BaseModel):
    id: str
    statement: str
    category_id: str
    skill_id: str
    category: str
    skill: str
    difficulty: str
    question_type: str
    points: float
    status: str
    options: list[QuestionOptionPayload] = Field(default_factory=list)


class QuestionCreateRequest(BaseModel):
    category_id: str
    skill_id: str
    statement: str = Field(min_length=5, max_length=5000)
    difficulty: str = "MEDIUM"
    question_type: str = "SINGLE_CHOICE"
    points: float = Field(gt=0, le=100)
    options: list[QuestionOptionPayload] = Field(min_length=2)


class QuestionUpdateRequest(QuestionCreateRequest):
    status: str = "DRAFT"


class QuestionArchiveRequest(BaseModel):
    question_ids: list[str] = Field(min_length=1)


class TestVersionItem(BaseModel):
    id: str
    campaign_id: str
    code: str
    duration_seconds: int
    published: bool
    question_count: int
    max_points: float


class TestVersionQuestionsRequest(BaseModel):
    question_ids: list[str] = Field(min_length=1)


class TestVersionCreateRequest(BaseModel):
    campaign_id: str
    code: str = Field(min_length=1, max_length=10)
    duration_seconds: int = Field(gt=0, le=86400)


class DashboardResponse(BaseModel):
    registered_candidates: int
    completed_tests: int
    pending_tests: int
    average_score: float
    best_score: float
    completion_rate: float
    candidates: list[CandidateListItem]
