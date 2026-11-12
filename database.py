#database.py
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fail at startup with a clear message instead of a cryptic SQLAlchemy error
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to your .env file (see .env.example), e.g. "
        "mysql+pymysql://user:password@localhost:3306/study_assistant"
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker( autocommit = False, autoflush = False, bind = engine)
Base = declarative_base()


def utcnow() -> datetime:
    """
    Current UTC time as a naive datetime (MySQL DATETIME has no timezone).
    Replaces the deprecated datetime.utcnow(). Values are always UTC —
    use as_utc() when returning them to the frontend.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime | None) -> datetime | None:
    """
    Marks a naive UTC datetime from MySQL as UTC so the JSON contains
    '+00:00' and the browser converts it to the user's local time correctly.
    """
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def get_session_factory():
    """
    For streaming endpoints: the stream keeps running after the request's own
    DB session (get_db) may have been closed, so the generator opens its own
    session from this factory when it needs to save. Overridable in tests.
    """
    return SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
