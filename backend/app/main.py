from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from io import StringIO
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, engine, get_db
from app.models import Campaign, CandidateAnswer, CandidateProfile, CandidateTest, Category, CvDocument, Question, Role, Skill, TestStatus, TestVersion, TestVersionQuestion, User
from app.schemas import AdminQuestionItem, AnswerRequest, CandidateAnswerDetail, CandidateDetailResponse, CandidateListItem, CandidateManageRequest, CvResponse, DashboardResponse, JobOfferResponse, LoginRequest, ProfileResponse, ProfileUpdateRequest, QuestionArchiveRequest, QuestionCreateRequest, QuestionResponse, QuestionUpdateRequest, RegisterRequest, ScoreResponse, TestStateResponse, TestVersionCreateRequest, TestVersionItem, TestVersionQuestionsRequest, TokenResponse
from app.security import create_access_token, decode_subject, hash_password, verify_password
from app.services import assign_test, expire_if_needed, submit_test

settings = get_settings()
@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if engine.url.get_backend_name() == "sqlite":
        with engine.begin() as connection:
            existing = {row[1] for row in connection.execute(text("PRAGMA table_info(candidate_profiles)"))}
            for name, definition in {"location": "VARCHAR(150)", "linkedin_url": "VARCHAR(500)", "availability": "VARCHAR(100)", "summary": "TEXT"}.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE candidate_profiles ADD COLUMN {name} {definition}"))
    yield


app = FastAPI(title="Candidate Evaluation Platform", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)


def utc_now_for(value: datetime | None = None) -> datetime:
    current = datetime.now(timezone.utc)
    if value is not None and value.tzinfo is None:
        return current.replace(tzinfo=None)
    return current


def utc_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    subject = decode_subject(credentials.credentials) if credentials else None
    user = db.get(User, subject) if subject else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise")
    return user


def candidate_only(user: User = Depends(current_user)) -> User:
    if user.role != Role.CANDIDATE:
        raise HTTPException(status_code=403, detail="Accès candidat requis")
    return user


def recruiter_only(user: User = Depends(current_user)) -> User:
    if user.role not in (Role.RECRUITER, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Accès recruteur requis")
    return user


def admin_only(user: User = Depends(current_user)) -> User:
    if user.role not in (Role.RECRUITER, Role.ADMIN):
        raise HTTPException(status_code=403, detail="Accès administrateur requis")
    return user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/auth/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Email déjà utilisé")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), role=Role.CANDIDATE)
    user.profile = CandidateProfile(first_name=payload.first_name, last_name=payload.last_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    return TokenResponse(access_token=create_access_token(user.id))


@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user)) -> dict[str, str]:
    return {"id": user.id, "email": user.email, "role": user.role}


@app.get("/api/v1/candidate/profile", response_model=ProfileResponse)
def profile(user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> ProfileResponse:
    profile_data = user.profile
    document = db.scalar(select(CvDocument).where(CvDocument.candidate_id == user.id))
    return ProfileResponse(user_id=user.id, email=user.email, first_name=profile_data.first_name, last_name=profile_data.last_name, phone=profile_data.phone, education=profile_data.education, experience=profile_data.experience, cv_name=document.original_name if document else None, location=profile_data.location, linkedin_url=profile_data.linkedin_url, availability=profile_data.availability, summary=profile_data.summary)


@app.get("/api/v1/candidate/job-offers", response_model=list[JobOfferResponse])
def job_offers(user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> list[JobOfferResponse]:
    offers = list(db.scalars(select(Campaign).where(Campaign.active.is_(True)).order_by(Campaign.job_title)).all())
    result = []
    for offer in offers:
        assignment = db.scalar(select(CandidateTest).where(CandidateTest.candidate_id == user.id, CandidateTest.campaign_id == offer.id))
        result.append(JobOfferResponse(id=offer.id, name=offer.name, job_title=offer.job_title, duration_seconds=offer.duration_seconds, show_result_to_candidate=offer.show_result_to_candidate, status=assignment.status if assignment else "AVAILABLE"))
    return result


@app.put("/api/v1/candidate/profile", response_model=ProfileResponse)
def update_profile(payload: ProfileUpdateRequest, user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> ProfileResponse:
    profile_data = user.profile
    profile_data.phone, profile_data.education, profile_data.experience = payload.phone, payload.education, payload.experience
    profile_data.location, profile_data.linkedin_url = payload.location, payload.linkedin_url
    profile_data.availability, profile_data.summary = payload.availability, payload.summary
    db.commit()
    return profile(user, db)


@app.post("/api/v1/candidate/cv", response_model=CvResponse, status_code=201)
async def upload_cv(file: UploadFile = File(...), user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> CvResponse:
    allowed = {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail="Format CV accepté : PDF, DOC ou DOCX")
    content = await file.read()
    if not content or len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Le CV doit peser entre 1 octet et 5 Mo")
    directory = Path(settings.storage_path).resolve() / "cv"
    directory.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "cv").suffix.lower()
    destination = directory / f"{uuid4()}{suffix}"
    destination.write_bytes(content)
    document = db.scalar(select(CvDocument).where(CvDocument.candidate_id == user.id))
    if document:
        previous = Path(document.storage_path)
        if previous.is_file(): previous.unlink()
        document.original_name, document.mime_type, document.storage_path, document.size_bytes = file.filename or "cv", file.content_type, str(destination), len(content)
    else:
        document = CvDocument(candidate_id=user.id, original_name=file.filename or "cv", mime_type=file.content_type, storage_path=str(destination), size_bytes=len(content))
        db.add(document)
    db.commit(); db.refresh(document)
    return CvResponse(id=document.id, original_name=document.original_name, mime_type=document.mime_type, size_bytes=document.size_bytes)


@app.get("/api/v1/candidate/test", response_model=TestStateResponse)
def test_state(campaign_id: str | None = None, user: User = Depends(candidate_only, use_cache=True), db: Session = Depends(get_db)) -> TestStateResponse:
    assignment = expire_if_needed(db, assign_test(db, user, campaign_id))
    return TestStateResponse(id=assignment.id, status=assignment.status, version=assignment.version.code, duration_seconds=assignment.version.duration_seconds, started_at=utc_timestamp(assignment.started_at), expires_at=utc_timestamp(assignment.expires_at), answered_count=len(assignment.answers), total_questions=len(assignment.version.questions))


@app.post("/api/v1/candidate/test/start", response_model=TestStateResponse)
def start_test(campaign_id: str | None = None, user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> TestStateResponse:
    assignment = assign_test(db, user, campaign_id)
    if assignment.status == TestStatus.ASSIGNED:
        assignment.status = TestStatus.IN_PROGRESS
        assignment.started_at = datetime.now(timezone.utc)
        assignment.expires_at = assignment.started_at + timedelta(seconds=assignment.version.duration_seconds)
        db.commit()
        db.refresh(assignment)
    return test_state(campaign_id, user, db)


@app.get("/api/v1/candidate/test/questions", response_model=list[QuestionResponse])
def questions(campaign_id: str | None = None, user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> list[QuestionResponse]:
    assignment = expire_if_needed(db, assign_test(db, user, campaign_id))
    if assignment.status != TestStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Le test doit être démarré avant d'accéder aux questions")
    result: list[QuestionResponse] = []
    for item in assignment.version.questions:
        question = item.question
        category = db.get(Category, question.category_id)
        skill = db.get(Skill, question.skill_id)
        safe_options = [{"key": option["key"], "label": option["label"]} for option in question.options]
        result.append(QuestionResponse(id=question.id, position=item.position, statement=question.statement, question_type=question.question_type, options=safe_options, points=item.points, skill=skill.name if skill else "", category=category.label if category else ""))
    return result


@app.get("/api/v1/candidate/test/answers")
def saved_answers(campaign_id: str | None = None, user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> dict[str, dict]:
    assignment = expire_if_needed(db, assign_test(db, user, campaign_id))
    return {answer.question_id: {"answer": answer.answer, "marked_for_review": answer.marked_for_review} for answer in assignment.answers}


@app.put("/api/v1/candidate/test/answers/{question_id}")
def save_answer(question_id: str, campaign_id: str, payload: AnswerRequest, user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> dict[str, str]:
    assignment = assign_test(db, user, campaign_id)
    if assignment.status != TestStatus.IN_PROGRESS or (assignment.expires_at and utc_now_for(assignment.expires_at) >= assignment.expires_at):
        raise HTTPException(status_code=409, detail="Le test n'accepte plus de réponse")
    item = next((item for item in assignment.version.questions if item.question_id == question_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Question inconnue")
    answer = db.scalar(select(CandidateAnswer).where(CandidateAnswer.candidate_test_id == assignment.id, CandidateAnswer.question_id == question_id))
    if answer:
        answer.answer = payload.answer
        answer.marked_for_review = payload.marked_for_review
    else:
        db.add(CandidateAnswer(candidate_test_id=assignment.id, question_id=question_id, answer=payload.answer, marked_for_review=payload.marked_for_review))
    db.commit()
    return {"status": "saved"}


@app.post("/api/v1/candidate/test/submit", response_model=ScoreResponse)
def submit(campaign_id: str, user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> ScoreResponse:
    assignment = assign_test(db, user, campaign_id)
    score = submit_test(db, assignment)
    return ScoreResponse(earned_points=score.earned_points, maximum_points=score.maximum_points, normalized_score=score.normalized_score, level=score.level, breakdown=score.breakdown)


@app.get("/api/v1/candidate/result", response_model=ScoreResponse)
def result(campaign_id: str, user: User = Depends(candidate_only), db: Session = Depends(get_db)) -> ScoreResponse:
    assignment = assign_test(db, user, campaign_id)
    if assignment.status != TestStatus.SUBMITTED or not assignment.score:
        raise HTTPException(status_code=404, detail="Aucun résultat disponible")
    score = assignment.score
    return ScoreResponse(earned_points=score.earned_points, maximum_points=score.maximum_points, normalized_score=score.normalized_score, level=score.level, breakdown=score.breakdown)


@app.get("/api/v1/recruiter/dashboard", response_model=DashboardResponse)
def recruiter_dashboard(user: User = Depends(recruiter_only), db: Session = Depends(get_db)) -> DashboardResponse:
    candidates = list(db.scalars(select(User).where(User.role == Role.CANDIDATE, User.is_active.is_(True))).all())
    candidate_ids = [candidate.id for candidate in candidates]
    assignments = list(db.scalars(select(CandidateTest).where(CandidateTest.candidate_id.in_(candidate_ids)).order_by(CandidateTest.id)).all())
    rows: list[CandidateListItem] = []
    scores = [assignment.score.normalized_score for assignment in assignments if assignment.score]
    for candidate in candidates:
        assignment = next((item for item in assignments if item.candidate_id == candidate.id), None)
        rows.append(CandidateListItem(id=candidate.id, first_name=candidate.profile.first_name, last_name=candidate.profile.last_name, email=candidate.email, status=assignment.status if assignment else "NOT_ASSIGNED", version=assignment.version.code if assignment else "-", score=assignment.score.normalized_score if assignment and assignment.score else None, level=assignment.score.level if assignment and assignment.score else None, submitted_at=assignment.submitted_at if assignment else None))
    completed = len(scores)
    return DashboardResponse(registered_candidates=len(candidates), completed_tests=completed, pending_tests=len(candidates) - completed, average_score=round(sum(scores) / completed, 2) if completed else 0, best_score=max(scores) if scores else 0, completion_rate=round(completed / len(candidates) * 100, 2) if candidates else 0, candidates=rows)


def recruiter_candidate_row(db: Session, candidate: User) -> CandidateListItem:
    assignment = db.scalar(select(CandidateTest).where(CandidateTest.candidate_id == candidate.id))
    return CandidateListItem(id=candidate.id, first_name=candidate.profile.first_name, last_name=candidate.profile.last_name, email=candidate.email, status=assignment.status if assignment else "NOT_ASSIGNED", version=assignment.version.code if assignment else "-", score=assignment.score.normalized_score if assignment and assignment.score else None, level=assignment.score.level if assignment and assignment.score else None, submitted_at=assignment.submitted_at if assignment else None)


@app.get("/api/v1/recruiter/candidates", response_model=list[CandidateListItem])
def recruiter_candidates(query: str = "", status_filter: str | None = Query(None, alias="status"), level: str | None = None, sort: str = "submitted_at", direction: str = "desc", user: User = Depends(recruiter_only), db: Session = Depends(get_db)) -> list[CandidateListItem]:
    rows = [recruiter_candidate_row(db, candidate) for candidate in db.scalars(select(User).where(User.role == Role.CANDIDATE, User.is_active.is_(True))).all()]
    needle = query.casefold().strip()
    if needle:
        rows = [row for row in rows if needle in f"{row.first_name} {row.last_name} {row.email}".casefold()]
    if status_filter: rows = [row for row in rows if row.status == status_filter]
    if level: rows = [row for row in rows if row.level == level]
    reverse = direction.lower() != "asc"
    if sort == "name": rows.sort(key=lambda row: (row.last_name.casefold(), row.first_name.casefold()), reverse=reverse)
    elif sort == "score": rows.sort(key=lambda row: row.score if row.score is not None else -1, reverse=reverse)
    else:
        def submitted_sort_key(row: CandidateListItem) -> datetime:
            value = row.submitted_at
            if value is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        rows.sort(key=submitted_sort_key, reverse=reverse)
    return rows


@app.get("/api/v1/recruiter/candidates/{candidate_id}", response_model=CandidateDetailResponse)
def recruiter_candidate_detail(candidate_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)) -> CandidateDetailResponse:
    candidate = db.get(User, candidate_id)
    if not candidate or candidate.role != Role.CANDIDATE or not candidate.is_active: raise HTTPException(status_code=404, detail="Candidat introuvable")
    row = recruiter_candidate_row(db, candidate)
    assignment = db.scalar(select(CandidateTest).where(CandidateTest.candidate_id == candidate.id))
    details: list[CandidateAnswerDetail] = []
    if assignment:
        answer_map = {answer.question_id: answer for answer in assignment.answers}
        for item in assignment.version.questions:
            question, answer = item.question, answer_map.get(item.question_id)
            expected = [option["key"] for option in question.options if option.get("correct")]
            actual = answer.answer if answer else None
            is_correct = (set(actual or []) == set(expected)) if question.question_type == "MULTIPLE_CHOICE" else str(actual).strip().lower() == (expected[0].lower() if expected else "")
            details.append(CandidateAnswerDetail(position=item.position, statement=question.statement, category=db.get(Category, question.category_id).label, skill=db.get(Skill, question.skill_id).name, candidate_answer=actual, correct_answer=expected, earned_points=item.points if is_correct else 0, maximum_points=item.points))
    return CandidateDetailResponse(**row.model_dump(), phone=candidate.profile.phone, education=candidate.profile.education, experience=candidate.profile.experience, location=candidate.profile.location, linkedin_url=candidate.profile.linkedin_url, availability=candidate.profile.availability, summary=candidate.profile.summary, breakdown=assignment.score.breakdown if assignment and assignment.score else {}, answers=details)


@app.put("/api/v1/recruiter/candidates/{candidate_id}", response_model=CandidateDetailResponse)
def update_candidate(candidate_id: str, payload: CandidateManageRequest, user: User = Depends(recruiter_only), db: Session = Depends(get_db)) -> CandidateDetailResponse:
    candidate = db.get(User, candidate_id)
    if not candidate or candidate.role != Role.CANDIDATE or not candidate.is_active:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    duplicate = db.scalar(select(User).where(User.email == payload.email.lower(), User.id != candidate.id))
    if duplicate:
        raise HTTPException(status_code=409, detail="Cet email est déjà utilisé")
    candidate.email = payload.email.lower()
    candidate.profile.first_name, candidate.profile.last_name = payload.first_name, payload.last_name
    candidate.profile.phone, candidate.profile.education, candidate.profile.experience = payload.phone, payload.education, payload.experience
    candidate.profile.location, candidate.profile.linkedin_url = payload.location, payload.linkedin_url
    candidate.profile.availability, candidate.profile.summary = payload.availability, payload.summary
    db.commit()
    return recruiter_candidate_detail(candidate_id, user, db)


@app.delete("/api/v1/recruiter/candidates/{candidate_id}", status_code=204)
def deactivate_candidate(candidate_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)) -> None:
    candidate = db.get(User, candidate_id)
    if not candidate or candidate.role != Role.CANDIDATE:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    candidate.is_active = False
    db.commit()


@app.get("/api/v1/recruiter/cv/{candidate_id}")
def recruiter_cv(candidate_id: str, user: User = Depends(recruiter_only), db: Session = Depends(get_db)) -> FileResponse:
    document = db.scalar(select(CvDocument).where(CvDocument.candidate_id == candidate_id))
    if not document or not Path(document.storage_path).is_file():
        raise HTTPException(status_code=404, detail="CV introuvable")
    return FileResponse(document.storage_path, media_type=document.mime_type, filename=document.original_name)


@app.get("/api/v1/recruiter/export.csv")
def export_candidates(user: User = Depends(recruiter_only), db: Session = Depends(get_db)) -> StreamingResponse:
    import csv
    output = StringIO(); writer = csv.writer(output)
    writer.writerow(["Prénom", "Nom", "Email", "Statut", "Version", "Score global", "Niveau", "Date"])
    for row in recruiter_candidates(user=user, db=db): writer.writerow([row.first_name, row.last_name, row.email, row.status, row.version, row.score or "", row.level or "", row.submitted_at.isoformat() if row.submitted_at else ""])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=resultats-candidats.csv"})


@app.get("/api/v1/admin/questions", response_model=list[AdminQuestionItem])
def admin_questions(query: str = "", status_filter: str | None = Query(None, alias="status"), user: User = Depends(admin_only), db: Session = Depends(get_db)) -> list[AdminQuestionItem]:
    questions = list(db.scalars(select(Question).order_by(Question.statement)).all())
    needle = query.casefold().strip()
    response = []
    for question in questions:
        if needle and needle not in question.statement.casefold():
            continue
        if status_filter and question.status != status_filter:
            continue
        category, skill = db.get(Category, question.category_id), db.get(Skill, question.skill_id)
        response.append(AdminQuestionItem(id=question.id, statement=question.statement, category_id=question.category_id, skill_id=question.skill_id, category=category.label if category else "", skill=skill.name if skill else "", difficulty=question.difficulty, question_type=question.question_type, points=question.points, status=question.status, options=question.options))
    return response


@app.post("/api/v1/admin/questions/import")
async def import_question_bank(file: UploadFile = File(...), user: User = Depends(admin_only)) -> dict[str, int]:
    if not (file.filename or "").lower().endswith(".json"):
        raise HTTPException(status_code=415, detail="Le fichier doit être au format JSON")
    import json
    from import_questions import import_data
    try:
        data = json.loads((await file.read()).decode("utf-8"))
        return {"imported": import_data(data)}
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Questionnaire invalide : {exc}") from exc


@app.post("/api/v1/admin/questions", response_model=AdminQuestionItem, status_code=201)
def create_question(payload: QuestionCreateRequest, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> AdminQuestionItem:
    question = Question(category_id=payload.category_id, skill_id=payload.skill_id, statement=payload.statement, difficulty=payload.difficulty, question_type=payload.question_type, points=payload.points, status="DRAFT", options=[option.model_dump() for option in payload.options])
    db.add(question); db.commit(); db.refresh(question)
    category, skill = db.get(Category, question.category_id), db.get(Skill, question.skill_id)
    return AdminQuestionItem(id=question.id, statement=question.statement, category_id=question.category_id, skill_id=question.skill_id, category=category.label if category else "", skill=skill.name if skill else "", difficulty=question.difficulty, question_type=question.question_type, points=question.points, status=question.status, options=question.options)


@app.put("/api/v1/admin/questions/{question_id}", response_model=AdminQuestionItem)
def update_question(question_id: str, payload: QuestionUpdateRequest, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> AdminQuestionItem:
    question = db.get(Question, question_id)
    if not question: raise HTTPException(status_code=404, detail="Question introuvable")
    for field in ("category_id", "skill_id", "statement", "difficulty", "question_type", "points"):
        setattr(question, field, getattr(payload, field))
    question.status, question.options = payload.status, [option.model_dump() for option in payload.options]
    db.commit(); db.refresh(question)
    category, skill = db.get(Category, question.category_id), db.get(Skill, question.skill_id)
    return AdminQuestionItem(id=question.id, statement=question.statement, category_id=question.category_id, skill_id=question.skill_id, category=category.label if category else "", skill=skill.name if skill else "", difficulty=question.difficulty, question_type=question.question_type, points=question.points, status=question.status, options=question.options)


@app.delete("/api/v1/admin/questions/{question_id}", status_code=204)
def delete_question(question_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> None:
    question = db.get(Question, question_id)
    if not question: raise HTTPException(status_code=404, detail="Question introuvable")
    question.status = "ARCHIVED"
    db.commit()


@app.post("/api/v1/admin/questions/archive")
def archive_questions(payload: QuestionArchiveRequest, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> dict[str, int]:
    question_ids = list(dict.fromkeys(payload.question_ids))
    questions = list(db.scalars(select(Question).where(Question.id.in_(question_ids))).all())
    if len(questions) != len(question_ids):
        raise HTTPException(status_code=404, detail="Une ou plusieurs questions sont introuvables")
    for question in questions:
        question.status = "ARCHIVED"
    db.commit()
    return {"archived": len(questions)}


@app.post("/api/v1/admin/questions/{question_id}/validate", response_model=AdminQuestionItem)
def validate_question(question_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> AdminQuestionItem:
    question = db.get(Question, question_id)
    if not question: raise HTTPException(status_code=404, detail="Question introuvable")
    question.status = "VALIDATED"
    db.commit(); db.refresh(question)
    category, skill = db.get(Category, question.category_id), db.get(Skill, question.skill_id)
    return AdminQuestionItem(id=question.id, statement=question.statement, category_id=question.category_id, skill_id=question.skill_id, category=category.label if category else "", skill=skill.name if skill else "", difficulty=question.difficulty, question_type=question.question_type, points=question.points, status=question.status, options=question.options)


def version_item(version: TestVersion) -> TestVersionItem:
    return TestVersionItem(id=version.id, campaign_id=version.campaign_id, code=version.code, duration_seconds=version.duration_seconds, published=version.published, question_count=len(version.questions), max_points=sum(item.points for item in version.questions))


@app.get("/api/v1/admin/test-versions", response_model=list[TestVersionItem])
def admin_test_versions(campaign_id: str | None = None, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> list[TestVersionItem]:
    query = select(TestVersion).order_by(TestVersion.code)
    if campaign_id: query = query.where(TestVersion.campaign_id == campaign_id)
    return [version_item(version) for version in db.scalars(query).all()]


@app.post("/api/v1/admin/test-versions", response_model=TestVersionItem, status_code=201)
def create_test_version(payload: TestVersionCreateRequest, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> TestVersionItem:
    campaign = db.get(Campaign, payload.campaign_id)
    if not campaign: raise HTTPException(status_code=404, detail="Campagne introuvable")
    version = TestVersion(campaign_id=campaign.id, code=payload.code, duration_seconds=payload.duration_seconds, published=False)
    db.add(version); db.commit(); db.refresh(version)
    return version_item(version)


@app.delete("/api/v1/admin/test-versions/{version_id}", status_code=204)
def delete_test_version(version_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> None:
    version = db.get(TestVersion, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version introuvable")
    assignments = list(db.scalars(select(CandidateTest).where(CandidateTest.test_version_id == version.id)).all())
    active_assignments = db.scalar(select(CandidateTest.id).join(User, User.id == CandidateTest.candidate_id).where(CandidateTest.test_version_id == version.id, User.is_active.is_(True)))
    if active_assignments:
        raise HTTPException(status_code=409, detail="Cette version est déjà attribuée à un candidat actif")
    # A deleted candidate is inactive. Its historical assignment no longer has
    # to keep a draft version locked, so remove it with the version.
    for assignment in assignments:
        db.delete(assignment)
    db.delete(version)
    db.commit()


@app.put("/api/v1/admin/test-versions/{version_id}/questions", response_model=TestVersionItem)
def set_test_version_questions(version_id: str, payload: TestVersionQuestionsRequest, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> TestVersionItem:
    version = db.get(TestVersion, version_id)
    if not version: raise HTTPException(status_code=404, detail="Version introuvable")
    if version.published: raise HTTPException(status_code=409, detail="Une version publiée est immuable")
    unique_ids = list(dict.fromkeys(payload.question_ids))
    questions = list(db.scalars(select(Question).where(Question.id.in_(unique_ids), Question.status == "VALIDATED")).all())
    if len(questions) != len(unique_ids): raise HTTPException(status_code=422, detail="Toutes les questions doivent être validées et disponibles")
    by_id = {question.id: question for question in questions}
    version.questions.clear()
    version.questions.extend([TestVersionQuestion(question_id=question_id, position=position, points=by_id[question_id].points) for position, question_id in enumerate(unique_ids, start=1)])
    db.commit(); db.refresh(version)
    return version_item(version)


@app.post("/api/v1/admin/test-versions/{version_id}/publish", response_model=TestVersionItem)
def publish_test_version(version_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)) -> TestVersionItem:
    version = db.get(TestVersion, version_id)
    if not version: raise HTTPException(status_code=404, detail="Version introuvable")
    if not version.questions: raise HTTPException(status_code=422, detail="Une version doit contenir au moins une question")
    published = list(db.scalars(select(TestVersion).where(TestVersion.campaign_id == version.campaign_id, TestVersion.published.is_(True))).all())
    for other in published: other.published = False
    version.published = True
    db.commit(); db.refresh(version)
    return version_item(version)
