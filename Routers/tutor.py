#tutor.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, utcnow
from models import Note, TutorSession, User
from schemas import ChatRequest, ChatResponse, ChatMessage
from Services.chat_service import get_tutor_reply
from sqlalchemy.orm.attributes import flag_modified
from Services.embedding_service import retrieve_relevant_notes
from auth import get_current_user

router = APIRouter(prefix="/chat", tags=["Tutor"])


def load_or_new_session(db: Session, session_id: int | None, user_id: int, note_id: int | None = None) -> TutorSession:
    """
    Returns the user's existing session, or a NEW UNSAVED one.
    New sessions are only written to MySQL by save_session(), after the AI
    has replied — so a failed LLM call never leaves an empty session behind.
    """
    if session_id is not None:
        session = db.query(TutorSession).filter(
            TutorSession.session_id == session_id,
            TutorSession.user_id == user_id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    # A new chat can be linked to one of the user's own lessons
    if note_id is not None:
        owns_note = db.query(Note).filter(Note.note_id == note_id, Note.user_id == user_id).first()
        if not owns_note:
            raise HTTPException(status_code=404, detail="Lesson not found")

    return TutorSession(user_id=user_id, note_id=note_id, messages=[], started_at=utcnow())


def save_session(db: Session, session: TutorSession, history: list[dict]) -> TutorSession:
    """Stores the full history and commits (inserting the session if it is new)."""
    session.messages = history          # type: ignore
    flag_modified(session, "messages")
    if session.session_id is None:
        db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Step 1 — Fetch existing session or prepare a new (unsaved) one
    session = load_or_new_session(db, request.session_id, current_user.user_id, request.note_id)  # type: ignore

    # Step 2 — Copy history (don't mutate the ORM attribute in place) and add the user message
    history = list(session.messages or [])     # type: ignore
    history.append({"role": "user", "content": request.message})

    # Step 3 — Retrieve relevant notes from ChromaDB
    # (if the chat was started from a lesson, that lesson's chunks come first)
    context_chunks = retrieve_relevant_notes(
        query=request.message,
        user_id=current_user.user_id,       # type: ignore
        note_id=session.note_id,            # type: ignore
    )

    # Step 4 — Get LLM reply with context injected (if this fails, nothing is saved)
    reply = get_tutor_reply(history, context_chunks=context_chunks)  # type: ignore

    # Step 5 — Append assistant reply to history
    history.append({"role": "assistant", "content": reply})

    # Step 6 — Save to MySQL
    session = save_session(db, session, history)

    return ChatResponse(
        session_id=session.session_id,  # type: ignore
        reply=reply,
        messages=[ChatMessage(**m) for m in history]  # type: ignore
    )
