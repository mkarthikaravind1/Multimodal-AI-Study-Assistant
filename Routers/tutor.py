#tutor.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import TutorSession, User
from schemas import ChatRequest, ChatResponse, ChatMessage
from Services.chat_service import get_tutor_reply
from sqlalchemy.orm.attributes import flag_modified
from Services.embedding_service import retrieve_relevant_notes 
from auth import get_current_user

router = APIRouter(prefix="/chat", tags=["Tutor"])

@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Step 1 — Fetch or create session (unchanged from Phase 9)
    if request.session_id is not None:
        session = db.query(TutorSession).filter(
            TutorSession.session_id == request.session_id,
            TutorSession.user_id == current_user.user_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        history = session.messages      # type: ignore
    else:
        session = TutorSession(
            user_id=current_user.user_id,
            note_id=request.note_id,
            messages=[],
            started_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        history = []

    # Step 2 — Append user message to history
    history.append({"role": "user", "content": request.message})

    # Step 3 — Retrieve relevant notes from ChromaDB   ← NEW
    context_chunks = retrieve_relevant_notes(
        query=request.message,
        user_id=current_user.user_id  # type: ignore
    )

    # Step 4 — Get LLM reply with context injected     
    reply = get_tutor_reply(history, context_chunks=context_chunks)  # type: ignore

    # Step 5 — Append assistant reply to history (unchanged)
    history.append({"role": "assistant", "content": reply})

    # Step 6 — Save to MySQL (unchanged)
    session.messages = history          # type: ignore
    flag_modified(session, "messages")
    db.commit()
    db.refresh(session)

    return ChatResponse(
        session_id=session.session_id,  # type: ignore
        reply=reply,
        messages=[ChatMessage(**m) for m in history]  # type: ignore
    )