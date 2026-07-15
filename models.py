from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime,
    Text, JSON, DECIMAL, ForeignKey, Enum, func
)
from sqlalchemy.orm import relationship
from database import Base
import enum

# Python enum to match MySQL ENUM
class RoleEnum(str, enum.Enum):
    student = "student"
    admin = "admin"

class User(Base):
    __tablename__ = "user_details"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    student_class = Column(String(50))
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.student)
    registered_date = Column(DateTime, default=datetime.utcnow)

    # Relationships — lets you do user.notes, user.quizzes etc.
    notes = relationship("Note", back_populates="user")
    quizzes = relationship("QuizDetail", back_populates="user")
    tutor_sessions = relationship("TutorSession", back_populates="user")
    materials = relationship("UploadedMaterial", back_populates="user")


class Note(Base):
    __tablename__ = "notes"

    note_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    youtube_links = Column(JSON)              # stored as array of URL strings
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("user_details.user_id"), nullable=False)

    user = relationship("User", back_populates="notes")
    quizzes = relationship("QuizDetail", back_populates="note")
    tutor_sessions = relationship("TutorSession", back_populates="note")


class QuizDetail(Base):
    __tablename__ = "quiz_details"

    quiz_id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), nullable=False)
    questions = Column(JSON, nullable=False)      # ← add this line
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    incorrect_answers = Column(Integer, nullable=False)
    score_percentage = Column(DECIMAL(5, 2), nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("user_details.user_id"), nullable=False)
    note_id = Column(Integer, ForeignKey("notes.note_id"), nullable=False)

    user = relationship("User", back_populates="quizzes")
    note = relationship("Note", back_populates="quizzes")


class TutorSession(Base):
    __tablename__ = "tutor_sessions"

    session_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_details.user_id"), nullable=False)
    note_id = Column(Integer, ForeignKey("notes.note_id"), nullable=True)  # nullable
    messages = Column(JSON, nullable=False)   # stores conversation history array
    started_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tutor_sessions")
    note = relationship("Note", back_populates="tutor_sessions")

class UploadedMaterial(Base):
    __tablename__ = "uploaded_materials"

    material_id  = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("user_details.user_id"), nullable=False)
    filename     = Column(String(255), nullable=False)
    file_type    = Column(String(50), nullable=False)
    total_chunks = Column(Integer, nullable=False)
    uploaded_at  = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="materials")