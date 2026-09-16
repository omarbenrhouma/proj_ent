from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Role(StrEnum):
    CANDIDATE = "CANDIDATE"
    RECRUITER = "RECRUITER"
    ADMIN = "ADMIN"


class QuestionStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    ARCHIVED = "ARCHIVED"


class QuestionType(StrEnum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    NUMERIC = "NUMERIC"
    TEXT = "TEXT"


class Difficulty(StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class TestStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(String(20), default=Role.CANDIDATE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    profile: Mapped["CandidateProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    availability: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    user: Mapped[User] = relationship(back_populates="profile")


class CvDocument(Base):
    __tablename__ = "cv_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    storage_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    job_title: Mapped[str] = mapped_column(String(200))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=2700)
    show_result_to_candidate: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    label: Mapped[str] = mapped_column(String(100))


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    difficulty: Mapped[Difficulty] = mapped_column(String(20))
    question_type: Mapped[QuestionType] = mapped_column(String(30))
    statement: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    points: Mapped[float] = mapped_column(Float, default=1)
    status: Mapped[QuestionStatus] = mapped_column(String(20), default=QuestionStatus.DRAFT)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class TestVersion(Base):
    __tablename__ = "test_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    code: Mapped[str] = mapped_column(String(10))
    duration_seconds: Mapped[int] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    questions: Mapped[list["TestVersionQuestion"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("campaign_id", "code"),)


class TestVersionQuestion(Base):
    __tablename__ = "test_version_questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    test_version_id: Mapped[str] = mapped_column(ForeignKey("test_versions.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    position: Mapped[int] = mapped_column(Integer)
    points: Mapped[float] = mapped_column(Float)
    question: Mapped[Question] = relationship()
    __table_args__ = (UniqueConstraint("test_version_id", "question_id"), UniqueConstraint("test_version_id", "position"))


class CandidateTest(Base):
    __tablename__ = "candidate_tests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    test_version_id: Mapped[str] = mapped_column(ForeignKey("test_versions.id"))
    status: Mapped[TestStatus] = mapped_column(String(20), default=TestStatus.ASSIGNED)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[TestVersion] = relationship()
    answers: Mapped[list["CandidateAnswer"]] = relationship(cascade="all, delete-orphan")
    score: Mapped["CandidateScore | None"] = relationship(cascade="all, delete-orphan", uselist=False)
    __table_args__ = (UniqueConstraint("candidate_id", "campaign_id"),)


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_test_id: Mapped[str] = mapped_column(ForeignKey("candidate_tests.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    answer: Mapped[Any] = mapped_column(JSON)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("candidate_test_id", "question_id"),)


class CandidateScore(Base):
    __tablename__ = "candidate_scores"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_test_id: Mapped[str] = mapped_column(ForeignKey("candidate_tests.id"), unique=True)
    earned_points: Mapped[float] = mapped_column(Float)
    maximum_points: Mapped[float] = mapped_column(Float)
    normalized_score: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(30))
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
