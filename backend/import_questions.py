"""Import a reviewed single-choice question bank into the application.

Usage (from backend/):
    python import_questions.py C:\path\questions.json

The command is idempotent: importing the same file again updates its questions
instead of creating duplicates. Review the source file before publishing the
questions in an official test version.
"""
import json
import re
import sys
from pathlib import Path

from app.db import Base, SessionLocal, engine
from app.models import Campaign, Category, Difficulty, Question, QuestionStatus, QuestionType, Skill, TestVersion, TestVersionQuestion

# Simple, transparent V1 interview blueprint. All imported items stay in the
# question bank; only this balanced subset is published to candidates.
BLUEPRINT = {
    "TECHNIQUE": 7,
    "LOGIQUE": 4,
    "GENERAL": 4,
}

DATA_ANALYST_CATEGORIES = {
    "TECHNIQUE": ("Technique",),
    "LOGIQUE": ("Logique", "Logique/Calcul"),
    "GENERAL": ("Metier Retail", "Analyse", "Culture generale", "Vocabulaire"),
}


def data_analyst_category(source: str) -> tuple[str, str]:
    """Map source topics to the three candidate-facing Data Analyst areas."""
    normalized = code(source)
    for category_code, topics in DATA_ANALYST_CATEGORIES.items():
        if normalized in {code(topic) for topic in topics}:
            label = {"TECHNIQUE": "Technique", "LOGIQUE": "Logique", "GENERAL": "Général"}[category_code]
            return category_code, label
    return "GENERAL", "Général"


def code(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    return normalized[:50] or "GENERAL"


def import_data(data: dict) -> int:
    questions = [question for section in data.get("sections", []) for question in section.get("questions", [])]
    if not questions:
        raise ValueError("Le fichier ne contient aucune question.")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        imported = 0
        imported_by_category: dict[str, list[Question]] = {category: [] for category in BLUEPRINT}
        for raw in questions:
            required = {"id", "category", "prompt", "options", "correct_option"}
            correct_option = str(raw.get("correct_option", "")).upper()
            option_keys = {str(key).upper() for key in raw.get("options", {})}
            if not required.issubset(raw) or correct_option not in option_keys:
                raise ValueError(f"Question invalide : {raw.get('id', 'sans id')}")
            category_code, category_label = data_analyst_category(raw["category"])
            category = db.query(Category).filter_by(code=category_code).first()
            if not category:
                category = Category(code=category_code, label=category_label)
                db.add(category); db.flush()
            else:
                category.label = category_label
            skill_name = raw["category"]
            skill = db.query(Skill).filter_by(name=skill_name).first()
            if not skill:
                skill = Skill(name=skill_name, category_id=category.id)
                db.add(skill); db.flush()
            else:
                skill.category_id = category.id
            options = [{"key": str(key).upper(), "label": label, "correct": str(key).upper() == correct_option} for key, label in raw["options"].items()]
            question = db.query(Question).filter_by(statement=raw["prompt"], skill_id=skill.id).first()
            values = dict(category_id=category.id, skill_id=skill.id, difficulty=Difficulty.MEDIUM, question_type=QuestionType.SINGLE_CHOICE, statement=raw["prompt"], explanation=raw.get("explanation", ""), points=2, status=QuestionStatus.VALIDATED, options=options)
            if question:
                for key, value in values.items(): setattr(question, key, value)
            else:
                question = Question(**values)
                db.add(question); db.flush()
            imported_by_category[category_code].append(question)
            imported += 1
        # This supplied questionnaire is an approved campaign questionnaire.
        # Keep one deterministic published version containing every validated item.
        campaign = db.query(Campaign).filter_by(active=True).first()
        if campaign:
            campaign.name = "Évaluation Data Analyst"
            campaign.job_title = "Data Analyst"
            version = db.query(TestVersion).filter_by(campaign_id=campaign.id, code="A").first()
            if not version:
                version = TestVersion(campaign_id=campaign.id, code="A", duration_seconds=1500, published=True)
                db.add(version); db.flush()
            version.duration_seconds = 1500
            version.published = True
            for other_version in db.query(TestVersion).filter(TestVersion.campaign_id == campaign.id, TestVersion.id != version.id):
                other_version.published = False
            selected = []
            for category_code, count in BLUEPRINT.items():
                candidates = imported_by_category[category_code]
                if len(candidates) < count:
                    raise ValueError(f"Questions insuffisantes pour {category_code} ({len(candidates)}/{count})")
                selected.extend(candidates[:count])
            db.query(TestVersionQuestion).filter_by(test_version_id=version.id).delete()
            db.flush()
            for position, question in enumerate(selected, start=1):
                db.add(TestVersionQuestion(test_version_id=version.id, question_id=question.id, position=position, points=question.points))
        db.commit()
        return imported
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def import_file(source: Path) -> int:
    with source.open(encoding="utf-8") as handle:
        return import_data(json.load(handle))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage : python import_questions.py <fichier.json>")
    count = import_file(Path(sys.argv[1]))
    print(f"{count} questions importées et la version Data Analyst est publiée.")
