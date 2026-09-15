from app.db import Base, SessionLocal, engine
from app.models import Campaign, Category, Difficulty, Question, QuestionStatus, QuestionType, Skill, TestVersion, TestVersionQuestion, User, Role
from app.security import hash_password


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter_by(active=True).first()
        if not campaign:
            campaign = Campaign(name="Campagne développeur Python", job_title="Développeur Python", duration_seconds=2700, show_result_to_candidate=True)
            db.add(campaign)
            db.flush()
        categories = {}
        for code, label in [("TECHNICAL", "Technique"), ("LOGIC", "Logique"), ("GENERAL", "Général")]:
            category = db.query(Category).filter_by(code=code).first()
            if not category:
                category = Category(code=code, label=label)
                db.add(category)
                db.flush()
            categories[code] = category
        skills = {}
        for name, code in [("Python", "TECHNICAL"), ("Raisonnement", "LOGIC"), ("Culture professionnelle", "GENERAL")]:
            skill = db.query(Skill).filter_by(name=name).first()
            if not skill:
                skill = Skill(name=name, category_id=categories[code].id)
                db.add(skill)
                db.flush()
            skills[name] = skill
        questions = db.query(Question).all()
        if not questions:
            questions = [
                Question(category_id=categories["TECHNICAL"].id, skill_id=skills["Python"].id, difficulty=Difficulty.MEDIUM, question_type=QuestionType.SINGLE_CHOICE, statement="Quel mot-clé définit une fonction Python ?", points=2, status=QuestionStatus.VALIDATED, options=[{"key": "A", "label": "func", "correct": False}, {"key": "B", "label": "def", "correct": True}, {"key": "C", "label": "function", "correct": False}]),
                Question(category_id=categories["LOGIC"].id, skill_id=skills["Raisonnement"].id, difficulty=Difficulty.MEDIUM, question_type=QuestionType.TRUE_FALSE, statement="La suite 2, 4, 8, 16 double à chaque étape.", points=2, status=QuestionStatus.VALIDATED, options=[{"key": "VRAI", "label": "Vrai", "correct": True}, {"key": "FAUX", "label": "Faux", "correct": False}]),
                Question(category_id=categories["GENERAL"].id, skill_id=skills["Culture professionnelle"].id, difficulty=Difficulty.EASY, question_type=QuestionType.SINGLE_CHOICE, statement="Quel comportement favorise une bonne revue de code ?", points=1, status=QuestionStatus.VALIDATED, options=[{"key": "A", "label": "Des retours précis et respectueux", "correct": True}, {"key": "B", "label": "Ne jamais expliquer les changements", "correct": False}]),
            ]
            db.add_all(questions)
            db.flush()
        version = db.query(TestVersion).filter_by(campaign_id=campaign.id, code="A").first()
        if not version:
            version = TestVersion(campaign_id=campaign.id, code="A", duration_seconds=campaign.duration_seconds, published=True)
            db.add(version)
            db.flush()
            db.add_all([TestVersionQuestion(test_version_id=version.id, question_id=question.id, position=index, points=question.points) for index, question in enumerate(questions, start=1)])
        if not db.query(User).filter_by(email="admin@example.com").first():
            db.add(User(email="admin@example.com", password_hash=hash_password("Admin123!"), role=Role.ADMIN))
        if not db.query(User).filter_by(email="recruiter@example.com").first():
            db.add(User(email="recruiter@example.com", password_hash=hash_password("Recruiter123!"), role=Role.RECRUITER))
        db.commit()
        print("Seed complete. Candidate registration is available; admin@example.com / Admin123! is for development only.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
