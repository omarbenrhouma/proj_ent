from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateScore, CandidateTest, Category, TestStatus, TestVersion, User


def get_active_campaign(db: Session):
    from app.models import Campaign
    campaign = db.scalar(select(Campaign).where(Campaign.active.is_(True)))
    if not campaign:
        raise HTTPException(status_code=503, detail="Aucune campagne active")
    return campaign


def assign_test(db: Session, user: User, campaign_id: str | None = None) -> CandidateTest:
    campaign = db.get(__import__("app.models", fromlist=["Campaign"]).Campaign, campaign_id) if campaign_id else get_active_campaign(db)
    if not campaign or not campaign.active:
        raise HTTPException(status_code=404, detail="Offre introuvable ou inactive")
    current = db.scalar(select(CandidateTest).where(CandidateTest.candidate_id == user.id, CandidateTest.campaign_id == campaign.id))
    if current:
        return current
    versions = list(db.scalars(select(TestVersion).where(TestVersion.campaign_id == campaign.id, TestVersion.published.is_(True)).order_by(TestVersion.code)).all())
    version = versions[hash(user.id) % len(versions)] if versions else None
    if not version:
        raise HTTPException(status_code=503, detail="Aucune version de test publiée")
    assignment = CandidateTest(candidate_id=user.id, campaign_id=campaign.id, test_version_id=version.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def score_test(db: Session, candidate_test: CandidateTest) -> CandidateScore:
    answers = {answer.question_id: answer for answer in candidate_test.answers}
    earned = 0.0
    maximum = 0.0
    category_points: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for item in candidate_test.version.questions:
        question = item.question
        maximum += item.points
        expected = [option["key"] for option in question.options if option.get("correct")]
        answer = answers.get(question.id)
        actual = answer.answer if answer else None
        correct = False
        if question.question_type in ("SINGLE_CHOICE", "TRUE_FALSE", "NUMERIC"):
            correct = str(actual).strip().lower() == (expected[0].lower() if expected else "")
        elif question.question_type == "MULTIPLE_CHOICE":
            correct = set(actual or []) == set(expected)
        points = item.points if correct else 0.0
        category = db.get(Category, question.category_id)
        label = category.label if category else question.category_id
        earned += points
        category_points[label][0] += points
        category_points[label][1] += item.points
    normalized = round((earned / maximum) * 100, 2) if maximum else 0
    level = "Faible" if normalized < 50 else "À améliorer" if normalized < 65 else "Intermédiaire" if normalized < 75 else "Bon" if normalized < 85 else "Excellent"
    breakdown = {label: {"earned": values[0], "maximum": values[1], "score": round(values[0] / values[1] * 100, 2) if values[1] else 0} for label, values in category_points.items()}
    score = CandidateScore(candidate_test_id=candidate_test.id, earned_points=earned, maximum_points=maximum, normalized_score=normalized, level=level, breakdown=breakdown)
    db.add(score)
    return score


def submit_test(db: Session, candidate_test: CandidateTest) -> CandidateScore:
    if candidate_test.status == TestStatus.SUBMITTED:
        if candidate_test.score:
            return candidate_test.score
        raise HTTPException(status_code=409, detail="Test déjà soumis")
    if candidate_test.status != TestStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Le test doit être démarré avant sa soumission")
    if candidate_test.expires_at:
        expires_at = candidate_test.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_at:
            candidate_test.status = TestStatus.EXPIRED
    candidate_test.status = TestStatus.SUBMITTED
    candidate_test.submitted_at = datetime.now(timezone.utc)
    score = score_test(db, candidate_test)
    db.commit()
    db.refresh(score)
    return score


def expire_if_needed(db: Session, candidate_test: CandidateTest) -> CandidateTest:
    """Make the server authoritative when a test is reopened after its deadline."""
    expires_at = candidate_test.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (candidate_test.status == TestStatus.IN_PROGRESS and expires_at
            and datetime.now(timezone.utc) >= expires_at):
        submit_test(db, candidate_test)
        db.refresh(candidate_test)
    return candidate_test
