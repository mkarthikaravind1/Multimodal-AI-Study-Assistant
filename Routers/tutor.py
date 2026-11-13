#tutor.py
"""
AI tutor chat.

POST   /chat                    ask (whole answer at once)
POST   /chat/stream             ask (answer streamed as Server-Sent Events)
GET    /chat/sessions           chat history — newest first, ?q= searches titles and messages
GET    /chat/sessions/{id}      one conversation (resume it)
PATCH  /chat/sessions/{id}      rename
DELETE /chat/sessions/{id}      delete

A request can carry material_id ("only search this document"): retrieval is
limited to that one upload and the tutor is told to stay inside it. The
choice is remembered on the session, so a resumed chat keeps its focus.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from typing import cast
from database import get_db, get_session_factory, utcnow, as_utc
from models import Note, TutorSession, UploadedMaterial, User
from schemas import (
    ChatRequest, ChatResponse, ChatMessage, ChatSessionSummary, ChatSessionDetail, ChatSessionRename,
)
from Services.chat_service import get_tutor_reply, stream_tutor_reply, normalize_citations
from Services.chat_titles import session_title, shorten, clean_question, search_snippet
from Services.sse import sse, sse_response, friendly_error
from Services.citations import build_sources, public_citation
from sqlalchemy.orm.attributes import flag_modified
from Services.embedding_service import retrieve_sources
from auth import get_current_user
from Services.language import language_note

router = APIRouter(prefix="/chat", tags=["Tutor"])

MAX_LISTED_SESSIONS = 100
_KEEP = object()        # save_session: leave the session's document focus as it is


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


def save_session(db: Session, session: TutorSession, history: list[dict], material_id=_KEEP) -> TutorSession:
    """
    Stores the full history and commits (inserting the session if it is new).
    The title comes from the first question unless the student renamed it.
    """
    session.messages = history          # type: ignore
    flag_modified(session, "messages")
    if not session.title:
        session.title = session_title(history)      # type: ignore
    session.updated_at = utcnow()                   # type: ignore
    if material_id is not _KEEP:
        session.material_id = material_id           # type: ignore
    if session.session_id is None:
        db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _focus_material(db: Session, material_id: int | None, user_id: int) -> UploadedMaterial | None:
    if material_id is None:
        return None
    material = db.query(UploadedMaterial).filter(
        UploadedMaterial.material_id == material_id, UploadedMaterial.user_id == user_id
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="That document was not found — it may have been deleted.")
    return material


def prepare_chat(
    db: Session, request: ChatRequest, user_id: int,
) -> tuple[TutorSession, list[dict], list[dict], UploadedMaterial | None]:
    """
    Everything that happens BEFORE the LLM call (shared by /chat and /chat/stream):
    load or create the session, add the user message, retrieve and number sources.
    Raises HTTPException (e.g. 404) before any streaming starts.
    """
    session = load_or_new_session(db, request.session_id, user_id, request.note_id)
    focus = _focus_material(db, request.material_id, user_id)

    # Copy history (don't mutate the ORM attribute in place) and add the user message
    history = list(session.messages or [])     # type: ignore
    history.append({"role": "user", "content": request.message})

    # Retrieve relevant chunks from ChromaDB and number them S1, S2, …
    # (one document only when focused; otherwise a linked lesson's chunks come first)
    if focus is not None:
        hits = retrieve_sources(
            query=request.message, user_id=user_id,
            material_id=cast(int, focus.material_id), material_source=cast(str, focus.file_type),
        )
    else:
        hits = retrieve_sources(query=request.message, user_id=user_id, note_id=session.note_id)   # type: ignore
    note_ids = {h["meta"].get("note_id") for h in hits if h["meta"].get("source") == "note"}
    note_titles = {
        n.note_id: n.title
        for n in db.query(Note).filter(Note.note_id.in_(note_ids), Note.user_id == user_id).all()
    } if note_ids else {}
    sources = build_sources(hits, note_titles)    # type: ignore
    return session, history, sources, focus


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
    session, history, sources, focus = prepare_chat(db, request, cast(int, current_user.user_id))

    # Get LLM reply (if this fails, nothing is saved)
    # Reply language from the profile ("auto" → the language of this question)
    lang = language_note(current_user.preferred_language, request.message)     # type: ignore
    raw = get_tutor_reply(
        history, sources=sources, language_note=lang,
        focus_document=cast(str, focus.filename) if focus else "",
    )
    reply, cited = finish_reply(raw, sources)
    history.append({"role": "assistant", "content": reply, "sources": cited})

    session = save_session(db, session, history, material_id=request.material_id)

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
    session, history, sources, focus = prepare_chat(db, request, user_id)
    existing_id = session.session_id
    note_id = session.note_id
    lang = language_note(current_user.preferred_language, request.message)     # type: ignore
    focus_name = cast(str, focus.filename) if focus else ""

    def events():
        parts: list[str] = []
        try:
            for piece in stream_tutor_reply(history, sources=sources, language_note=lang, focus_document=focus_name):
                parts.append(piece)
                yield sse("token", {"text": piece})
        except Exception as e:      # Groq error, network error, …
            yield sse("error", {"detail": friendly_error(e)})
            return

        reply, cited = finish_reply("".join(parts), sources)
        full_history = history + [{"role": "assistant", "content": reply, "sources": cited}]

        try:
            with session_factory() as db2:
                tutor_session = db2.get(TutorSession, existing_id) if existing_id is not None else None
                if tutor_session is None:
                    # new chat — or the chat was deleted (in another tab) while answering
                    tutor_session = TutorSession(user_id=user_id, note_id=note_id, messages=[], started_at=utcnow())
                saved = save_session(db2, tutor_session, full_history, material_id=request.material_id)
                session_id = saved.session_id
        except Exception as e:
            yield sse("error", {"detail": "The answer was generated but could not be saved. " + friendly_error(e)})
            return

        yield sse("done", {"session_id": session_id, "reply": reply, "sources": cited})

    return sse_response(events())


# ── chat history ──────────────────────────────────────────────────────────────

def _get_session(db: Session, session_id: int, user_id: int) -> TutorSession:
    session = db.query(TutorSession).filter(
        TutorSession.session_id == session_id, TutorSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    q: str = Query(default="", max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Newest first. With ?q= only chats whose title or any message contains it (case-insensitive)."""
    query = q.strip()
    sessions = db.query(TutorSession).filter(TutorSession.user_id == current_user.user_id).all()
    sessions.sort(key=lambda s: s.updated_at or s.started_at, reverse=True)     # type: ignore

    out = []
    for s in sessions:
        messages: list[dict] = s.messages or []      # type: ignore
        title = cast(str, s.title) or session_title(messages)
        match = None
        if query:
            if query.lower() in title.lower():
                match = None                          # the title itself shows the match
            else:
                for m in messages:
                    match = search_snippet(clean_question(m.get("content", "")), query)
                    if match:
                        break
                if match is None:
                    continue
        last = clean_question(messages[-1].get("content", "")) if messages else ""
        out.append(ChatSessionSummary(
            session_id=cast(int, s.session_id),
            title=title,
            preview=shorten(last, 90),
            match=match,
            message_count=len(messages),
            note_id=s.note_id,                        # type: ignore
            material_id=s.material_id,                # type: ignore
            started_at=as_utc(s.started_at),          # type: ignore
            updated_at=as_utc(s.updated_at or s.started_at),   # type: ignore
        ))
        if len(out) >= MAX_LISTED_SESSIONS:
            break
    return out


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def get_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = cast(int, current_user.user_id)
    s = _get_session(db, session_id, user_id)
    note = db.get(Note, s.note_id) if s.note_id else None
    material = None
    if s.material_id:
        material = db.query(UploadedMaterial).filter(
            UploadedMaterial.material_id == s.material_id, UploadedMaterial.user_id == user_id
        ).first()
    messages: list[dict] = s.messages or []          # type: ignore
    return ChatSessionDetail(
        session_id=cast(int, s.session_id),
        title=cast(str, s.title) or session_title(messages),
        messages=[ChatMessage(**{k: m.get(k) for k in ("role", "content")}, sources=m.get("sources") or []) for m in messages],
        note_id=s.note_id,                                       # type: ignore
        note_title=cast(str, note.title) if note else None,
        material_id=cast(int, material.material_id) if material else None,
        material_filename=cast(str, material.filename) if material else None,
        material_type=cast(str, material.file_type) if material else None,
        started_at=as_utc(s.started_at),                         # type: ignore
        updated_at=as_utc(s.updated_at or s.started_at),         # type: ignore
    )


@router.patch("/sessions/{session_id}", response_model=ChatSessionSummary)
def rename_session(
    session_id: int, request: ChatSessionRename,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    s = _get_session(db, session_id, cast(int, current_user.user_id))
    s.title = request.title          # type: ignore — renaming doesn't change updated_at (no new message)
    db.commit()
    db.refresh(s)
    messages: list[dict] = s.messages or []          # type: ignore
    return ChatSessionSummary(
        session_id=cast(int, s.session_id),
        title=cast(str, s.title),
        preview=shorten(clean_question(messages[-1].get("content", "")), 90) if messages else "",
        message_count=len(messages),
        note_id=s.note_id,                            # type: ignore
        material_id=s.material_id,                    # type: ignore
        started_at=as_utc(s.started_at),              # type: ignore
        updated_at=as_utc(s.updated_at or s.started_at),   # type: ignore
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    s = _get_session(db, session_id, cast(int, current_user.user_id))
    db.delete(s)
    db.commit()
    return {"message": "Chat deleted"}
