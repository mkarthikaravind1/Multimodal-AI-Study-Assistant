from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import Note, User
from schemas import LessonRequest, LessonResponse
from Services.lesson_generator import generate_notes
from auth import get_current_user
from Services.embedding_service import add_note_to_vectorstore

router = APIRouter(prefix="/lessons", tags=["Lessons"])

@router.post("/generate", response_model=LessonResponse)
def generate_lesson(request: LessonRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = generate_notes(topic=request.topic, student_class=request.student_class)
    title = f"Notes on {request.topic.title()}"
    
    new_note = Note(title=title, content=content, youtube_links=[], created_at=datetime.utcnow(), user_id=current_user.user_id)
    db.add(new_note)
    db.commit()
    db.refresh(new_note)

    # NEW — embed and store in ChromaDB
    add_note_to_vectorstore(
        note_id=new_note.note_id,        # type: ignore
        content=new_note.content,        # type: ignore
        user_id=current_user.user_id,    # type: ignore
        topic=request.topic
    )

    return LessonResponse.model_validate({
        "note_id": new_note.note_id,
        "title": new_note.title,
        "content": new_note.content,
        "topic": request.topic,
        "student_class": request.student_class, # Fixed: pulled from request since Note table doesn't have it
        "message": "AI lesson generated and stored successfully"
    })

@router.get("/all")
def get_all_lessons(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    notes = db.query(Note).filter(Note.user_id == current_user.user_id).all()
    return [
        {
            "note_id": n.note_id,
            "title": n.title,
            "content": n.content,
            "created_at": n.created_at
        }
        for n in notes
    ]

@router.post("/regenerate-weak", response_model=LessonResponse)
def regenerate_weak_topic(request: LessonRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    # Step 1 — Generate notes with easy_mode=True
    content = generate_notes(request.topic, request.student_class, easy_mode=True)

    title = f"Simplified Notes: {request.topic.title()}"

    # user_id = 1
    # user = db.query(User).filter(User.user_id == user_id).first()
    # if not user:
    #     raise HTTPException(status_code=404, detail="User not found")

    # Step 2 — Store as a new note (so old confusing note stays for reference)
    new_note = Note(
        title=title,
        content=content,
        youtube_links=[],
        created_at=datetime.utcnow(),
        user_id=current_user.user_id
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)

    # NEW — embed and store in ChromaDB
    add_note_to_vectorstore(
        note_id=new_note.note_id,        # type: ignore
        content=new_note.content,        # type: ignore
        user_id=current_user.user_id,    # type: ignore
        topic=request.topic
    )

    return LessonResponse(
        note_id=new_note.note_id,        # type: ignore
        title=new_note.title,            # type: ignore
        content=new_note.content,        # type: ignore
        topic=request.topic,
        student_class=request.student_class,
        message="Simplified notes generated for weak topic"
    )