from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import CandidateTest, TestStatus as CandidateTestStatus


def register_candidate(client: TestClient) -> tuple[str, str]:
    email = f"candidate-{uuid4()}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "first_name": "Test", "last_name": "Candidate"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"], email


def test_candidate_can_complete_selected_campaign():
    client = TestClient(app)
    token, _ = register_candidate(client)
    headers = {"Authorization": f"Bearer {token}"}
    offers = client.get("/api/v1/candidate/job-offers", headers=headers)
    assert offers.status_code == 200, offers.text
    campaign_id = offers.json()[0]["id"]

    started = client.post(f"/api/v1/candidate/test/start?campaign_id={campaign_id}", headers=headers)
    assert started.status_code == 200, started.text
    questions = client.get(f"/api/v1/candidate/test/questions?campaign_id={campaign_id}", headers=headers)
    assert questions.status_code == 200, questions.text
    assert len(questions.json()) == 33

    for question, answer in zip(questions.json(), ["B", "VRAI", "A"]):
        saved = client.put(
            f"/api/v1/candidate/test/answers/{question['id']}?campaign_id={campaign_id}",
            headers=headers,
            json={"answer": answer},
        )
        assert saved.status_code == 200, saved.text

    submitted = client.post(f"/api/v1/candidate/test/submit?campaign_id={campaign_id}", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert 0 <= submitted.json()["normalized_score"] <= 100


def test_expired_submission_is_locked_and_scored_once():
    client = TestClient(app)
    token, _ = register_candidate(client)
    headers = {"Authorization": f"Bearer {token}"}
    campaign_id = client.get("/api/v1/candidate/job-offers", headers=headers).json()[0]["id"]
    assert client.post(f"/api/v1/candidate/test/start?campaign_id={campaign_id}", headers=headers).status_code == 200
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]

    with SessionLocal() as db:
        assignment = db.query(CandidateTest).filter_by(candidate_id=user_id, campaign_id=campaign_id).one()
        assignment.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    submitted = client.post(f"/api/v1/candidate/test/submit?campaign_id={campaign_id}", headers=headers)
    assert submitted.status_code == 200, submitted.text
    with SessionLocal() as db:
        assignment = db.query(CandidateTest).filter_by(candidate_id=user_id, campaign_id=campaign_id).one()
        assert assignment.status == CandidateTestStatus.SUBMITTED
        first_score_id = assignment.score.id

    repeated = client.post(f"/api/v1/candidate/test/submit?campaign_id={campaign_id}", headers=headers)
    assert repeated.status_code == 200, repeated.text
    with SessionLocal() as db:
        assignment = db.query(CandidateTest).filter_by(candidate_id=user_id, campaign_id=campaign_id).one()
        assert assignment.score.id == first_score_id
