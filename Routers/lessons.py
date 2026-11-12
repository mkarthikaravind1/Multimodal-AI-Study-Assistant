from typing import cast
from urllib.parse import quote_plus
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, utcnow, as_utc
from models import Note, User
from schemas import LessonRequest, LessonResponse
from Services.lesson_generator import generate_notes
from auth import get_current_user
from Services.embedding_service import add_note_to_vectorstore, delete_note_vectors

router = APIRouter(prefix="/lessons", tags=["Lessons"])


def normalize_topic(topic: str) -> str:
    """'  dijkstra's   algorithm ' → "dijkstra's algorithm" (collapses inner whitespace)."""
    return " ".join(topic.split())


def youtube_search_links(topic: str, student_class: str) -> list[str]:
    """
    YouTube search links for the topic (no API key needed).
    Stored in notes.youtube_links and shown under each lesson.
    """
    queries = [f"{topic} explained", f"{topic} {student_class} tutorial"]
    return [f"https://www.youtube.com/results?search_query={quote_plus(q)}" for q in queries]


def save_note_and_index(db: Session, user_id: int, title: str, content: str, topic: str, youtube_links: list[str]) -> Note:
    """
    Saves the note in MySQL and its vectors in ChromaDB together.
    The note is only committed once the vectors are stored; if either step
    fails, both are rolled back so the two stores never disagree.
    """
    note = Note(title=title, content=content, youtube_links=youtube_links, created_at=utcnow(), user_id=user_id)
    db.add(note)
    db.flush()      # assigns note_id without committing

    note_id = cast(int, note.note_id)
    try:
        add_note_to_vectorstore(note_id=note_id, content=content, user_id=user_id, topic=topic)
        db.commit()
    except Exception:
        db.rollback()
        try:
            delete_note_vectors(note_id)
        except Exception:
            pass
        raise

    db.refresh(note)
    return note


@router.post("/generate", response_model=LessonResponse)
def generate_lesson(request: LessonRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    topic = normalize_topic(request.topic)
    content = generate_notes(topic=topic, student_class=request.student_class)
    title = f"Notes on {topic.title()}"

    # Remember the student's education level (pre-fills forms, shown to admin)
    current_user.student_class = request.student_class      # type: ignore
    links = youtube_search_links(topic, request.student_class)
    new_note = save_note_and_index(db, cast(int, current_user.user_id), title, content, topic, links)

    return LessonResponse(
        note_id=new_note.note_id,        # type: ignore
        title=new_note.title,            # type: ignore
        content=new_note.content,        # type: ignore
        topic=topic,
        student_class=request.student_class,
        youtube_links=new_note.youtube_links or [],     # type: ignore
        message="AI lesson generated and stored successfully"
    )

@router.get("/all")
def get_all_lessons(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    notes = db.query(Note).filter(Note.user_id == current_user.user_id).order_by(Note.created_at).all()
    return [
        {
            "note_id": n.note_id,
            "title": n.title,
            "content": n.content,
            "youtube_links": n.youtube_links or [],
            "created_at": as_utc(n.created_at)     # type: ignore  — sent with +00:00
        }
        for n in notes
    ]

@router.post("/regenerate-weak", response_model=LessonResponse)
def regenerate_weak_topic(request: LessonRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    topic = normalize_topic(request.topic)

    # Step 1 — Generate notes with easy_mode=True
    content = generate_notes(topic, request.student_class, easy_mode=True)
    title = f"Simplified Notes: {topic.title()}"

    # Step 2 — Store as a new note (so old confusing note stays for reference)
    current_user.student_class = request.student_class      # type: ignore
    links = youtube_search_links(f"{topic} for beginners", request.student_class)
    new_note = save_note_and_index(db, cast(int, current_user.user_id), title, content, topic, links)

    return LessonResponse(
        note_id=new_note.note_id,        # type: ignore
        title=new_note.title,            # type: ignore
        content=new_note.content,        # type: ignore
        topic=topic,
        student_class=request.student_class,
        youtube_links=new_note.youtube_links or [],     # type: ignore
        message="Simplified notes generated for weak topic"
    )
