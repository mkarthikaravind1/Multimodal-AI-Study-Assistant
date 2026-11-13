from sqlalchemy import (
    Column, Integer, String, DateTime, Date,
    Text, JSON, DECIMAL, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from database import Base, utcnow
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
    # Reply language for tutor, lessons, quiz feedback and viva:
    # en | hi | ta | hinglish | tanglish | auto  (see Services/language.py)
    preferred_language = Column(String(12), nullable=False, default="en", server_default="en")
    registered_date = Column(DateTime, default=utcnow)

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
    created_at = Column(DateTime, default=utcnow)
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
    attempted_at = Column(DateTime, default=utcnow)
    submitted_at = Column(DateTime, nullable=True)   # NULL = generated but not submitted yet
    difficulty = Column(String(10), nullable=True)   # easy | medium | hard | mixed (NULL = older quiz)
    user_answers = Column(JSON, nullable=True)       # {question: answer} saved on submit
    # Self-healing loop: a retest quiz points at the quiz it is fixing
    parent_quiz_id = Column(Integer, ForeignKey("quiz_details.quiz_id"), nullable=True)
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
    started_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="tutor_sessions")
    note = relationship("Note", back_populates="tutor_sessions")

class UploadedMaterial(Base):
    __tablename__ = "uploaded_materials"

    material_id  = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("user_details.user_id"), nullable=False)
    filename     = Column(String(255), nullable=False)
    file_type    = Column(String(50), nullable=False)
    total_chunks = Column(Integer, nullable=False)
    uploaded_at  = Column(DateTime, default=utcnow)
    stored_path  = Column(String(500), nullable=True)   # original file in uploads/ (for citations)

    user = relationship("User", back_populates="materials")


class VivaSession(Base):
    """An oral exam: AI asks open questions about a lesson, grades spoken/typed answers."""
    __tablename__ = "viva_sessions"

    viva_id      = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("user_details.user_id"), nullable=False)
    note_id      = Column(Integer, ForeignKey("notes.note_id"), nullable=False)
    topic        = Column(String(255), nullable=False)
    # [{question, key_points, answer, score, feedback, ideal_answer, missed_points}]
    questions    = Column(JSON, nullable=False)
    total_score  = Column(Integer, nullable=True)    # sum of 0-10 scores, set when finished
    max_score    = Column(Integer, nullable=False)
    started_at   = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

class Flashcard(Base):
    """A spaced-repetition card (SM-2). Made from lessons, wrong quiz answers, weak viva answers, or by hand."""
    __tablename__ = "flashcards"

    card_id          = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("user_details.user_id"), nullable=False, index=True)
    front            = Column(Text, nullable=False)
    back             = Column(Text, nullable=False)
    topic            = Column(String(255), nullable=True)
    source           = Column(String(20), nullable=False, default="manual")   # note | mistake | viva | manual
    note_id          = Column(Integer, ForeignKey("notes.note_id"), nullable=True)
    quiz_id          = Column(Integer, ForeignKey("quiz_details.quiz_id"), nullable=True)
    # SM-2 scheduling state
    ease_factor      = Column(DECIMAL(4, 2), nullable=False, default=2.50)
    interval_days    = Column(Integer, nullable=False, default=0)
    repetitions      = Column(Integer, nullable=False, default=0)
    lapses           = Column(Integer, nullable=False, default=0)
    due_at           = Column(DateTime, nullable=False, default=utcnow, index=True)
    last_reviewed_at = Column(DateTime, nullable=True)
    created_at       = Column(DateTime, default=utcnow)


class SolutionCheck(Base):
    """A photo of handwritten working, checked step by step by the vision model."""
    __tablename__ = "solution_checks"

    check_id        = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("user_details.user_id"), nullable=False, index=True)
    topic           = Column(String(255), nullable=True)
    problem         = Column(Text, nullable=True)            # typed by the student or read from the photo
    expected_answer = Column(String(255), nullable=True)     # from the student's answer key (optional)
    final_answer    = Column(String(255), nullable=True)     # what the student wrote
    filename        = Column(String(255), nullable=False)
    stored_path     = Column(String(500), nullable=True)     # uploads/<user_id>/solutions/<check_id><ext>
    mime_type       = Column(String(50), nullable=False)
    # [{text, status, comment, correction}]  status: correct | error | follows_error | unclear
    steps           = Column(JSON, nullable=False)
    # {first_error_step, error_type, summary, hint, correct_answer, answer_matches_expected}
    result          = Column(JSON, nullable=False)
    verdict         = Column(String(20), nullable=False)     # correct | incorrect | incomplete | unreadable
    score           = Column(Integer, nullable=True)         # 0-10 (NULL when unreadable)
    rechecks        = Column(Integer, nullable=False, default=0)
    created_at      = Column(DateTime, default=utcnow)
    updated_at      = Column(DateTime, nullable=True)


class ExamPlan(Base):
    """A day-by-day study plan from a syllabus to an exam date (see Services/study_planner.py)."""
    __tablename__ = "exam_plans"

    plan_id           = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("user_details.user_id"), nullable=False, index=True)
    exam_name         = Column(String(200), nullable=False)
    exam_date         = Column(Date, nullable=False)
    start_date        = Column(Date, nullable=False)
    minutes_per_day   = Column(Integer, nullable=False)
    rest_days         = Column(JSON, nullable=False)       # weekdays off, 0 = Monday … 6 = Sunday
    # [{unit, topic, size, score, matched_topic, status, weight, minutes}]
    topics            = Column(JSON, nullable=False)
    # [{date, rest, exam, items: [{id, topic, kind, minutes, done}]}]
    days              = Column(JSON, nullable=False)
    syllabus_filename = Column(String(255), nullable=True)
    created_at        = Column(DateTime, default=utcnow)
    updated_at        = Column(DateTime, nullable=True)
