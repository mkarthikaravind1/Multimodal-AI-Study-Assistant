#tutor.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from typing import cast
from database import get_db, get_session_factory, utcnow
from models import Note, TutorSession, User
from schemas import ChatRequest, ChatResponse, ChatMessage
from Services.chat_service import get_tutor_reply, stream_tutor_reply, normalize_citations
from Services.sse import sse, sse_response, friendly_error
from Services.citations import build_sources, public_citation
from sqlalchemy.orm.attributes import flag_modified
from Services.embedding_service import retrieve_sources
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


def prepare_chat(db: Session, request: ChatRequest, user_id: int) -> tuple[TutorSession, list[dict], list[dict]]:
    """
    Everything that happens BEFORE the LLM call (shared by /chat and /chat/stream):
    load or create the session, add the user message, retrieve and number sources.
    Raises HTTPException (e.g. 404) before any streaming starts.
    """
    session = load_or_new_session(db, request.session_id, user_id, request.note_id)

    # Copy history (don't mutate the ORM attribute in place) and add the user message
    history = list(session.messages or [])     # type: ignore
    history.append({"role": "user", "content": request.message})

    # Retrieve relevant chunks from ChromaDB and number them S1, S2, …
    # (if the chat was started from a lesson, that lesson's chunks come first)
    hits = retrieve_sources(query=request.message, user_id=user_id, note_id=session.note_id)   # type: ignore
    note_ids = {h["meta"].get("note_id") for h in hits if h["meta"].get("source") == "note"}
    note_titles = {
        n.note_id: n.title
        for n in db.query(Note).filter(Note.note_id.in_(note_ids), Note.user_id == user_id).all()
    } if note_ids else {}
    sources = build_sources(hits, note_titles)    # type: ignore
    return session, history, sources


def finish_reply(raw_reply: str, sources: list[dict]) -> tuple[str, list[dict]]:
    """Keep only valid citation tags; return (clean_reply, cited_sources)."""
    reply, cited_ids = normalize_citations(raw_reply, {s["id"] for s in sources})
    by_id = {s["id"]: s for s in sources}
    return reply, [public_citation(by_id[i]) for i in cited_ids]


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session, history, sources = prepare_chat(db, request, cast(int, current_user.user_id))

    # Get LLM reply (if this fails, nothing is saved)
    reply, cited = finish_reply(get_tutor_reply(history, sources=sources), sources)
    history.append({"role": "assistant", "content": reply, "sources": cited})

    session = save_session(db, session, history)

    return ChatResponse(
        session_id=session.session_id,  # type: ignore
        reply=reply,
        messages=[ChatMessage(**m) for m in history]  # type: ignore
    )


@router.post("/stream")
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_factory=Depends(get_session_factory),
):
    """
    Same as POST /chat, but streams the answer as Server-Sent Events:
      token → {"text"}   …many…
      done  → {"session_id", "reply", "sources"}   (reply has cleaned-up citations)
      error → {"detail"}   (nothing saved)
    The conversation is saved only after the full answer arrived, so a failed
    or cancelled stream never leaves half a message in the database.
    """
    user_id = cast(int, current_user.user_id)
    session, history, sources = prepare_chat(db, request, user_id)
    existing_id = session.session_id
    note_id = session.note_id

    def events():
        parts: list[str] = []
        try:
            for piece in stream_tutor_reply(history, sources=sources):
                parts.append(piece)
                yield sse("token", {"text": piece})
        except Exception as e:      # Groq error, network error, …
            yield sse("error", {"detail": friendly_error(e)})
            return

        reply, cited = finish_reply("".join(parts), sources)
        full_history = history + [{"role": "assistant", "content": reply, "sources": cited}]

        try:
            with session_factory() as db2:
                if existing_id is not None:
                    tutor_session = db2.get(TutorSession, existing_id)
                else:
                    tutor_session = TutorSession(user_id=user_id, note_id=note_id, messages=[], started_at=utcnow())
                saved = save_session(db2, tutor_session, full_history)
                session_id = saved.session_id
        except Exception as e:
            yield sse("error", {"detail": "The answer was generated but could not be saved. " + friendly_error(e)})
            return

        yield sse("done", {"session_id": session_id, "reply": reply, "sources": cited})

    return sse_response(events())
