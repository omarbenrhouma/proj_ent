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
from app.models import Category, Difficulty, Question, QuestionStatus, QuestionType, Skill


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
        for raw in questions:
            required = {"id", "category", "prompt", "options", "correct_option"}
            correct_option = str(raw.get("correct_option", "")).upper()
            option_keys = {str(key).upper() for key in raw.get("options", {})}
            if not required.issubset(raw) or correct_option not in option_keys:
                raise ValueError(f"Question invalide : {raw.get('id', 'sans id')}")
            category_code = code(raw["category"])
            category = db.query(Category).filter_by(code=category_code).first()
            if not category:
                category = Category(code=category_code, label=raw["category"])
                db.add(category); db.flush()
            skill_name = raw["category"]
            skill = db.query(Skill).filter_by(name=skill_name).first()
            if not skill:
                skill = Skill(name=skill_name, category_id=category.id)
                db.add(skill); db.flush()
            options = [{"key": str(key).upper(), "label": label, "correct": str(key).upper() == correct_option} for key, label in raw["options"].items()]
            question = db.query(Question).filter_by(statement=raw["prompt"], skill_id=skill.id).first()
            values = dict(category_id=category.id, skill_id=skill.id, difficulty=Difficulty.MEDIUM, question_type=QuestionType.SINGLE_CHOICE, statement=raw["prompt"], explanation=raw.get("explanation", ""), points=2, status=QuestionStatus.DRAFT, options=options)
            if question:
                for key, value in values.items(): setattr(question, key, value)
            else:
                db.add(Question(**values))
            imported += 1
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
    print(f"{count} questions importées en brouillon.")
