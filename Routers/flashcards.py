"""
Spaced-repetition flashcards.

GET    /flashcards/due             cards due now + stats (the daily review queue)
GET    /flashcards/stats           counts for the dashboard
GET    /flashcards                 all cards (search / topic filter)
POST   /flashcards                 add a card by hand
POST   /flashcards/generate        AI cards from a lesson
POST   /flashcards/{id}/review     rate a card: again | hard | good | easy (SM-2)
PATCH  /flashcards/{id}            edit front/back
DELETE /flashcards/{id}            delete
GET    /flashcards/export/anki     download every card for Anki
"""
from datetime import datetime, timedelta, timezone
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, utcnow, as_utc
from models import Flashcard, Note, User
from schemas import (
    FlashcardOut, FlashcardCreate, FlashcardUpdate, FlashcardGenerateRequest,
    FlashcardGenerateResponse, ReviewRequest, FlashcardStats, DueCards,
)
from Services.srs import CardState, schedule, previews
from Services.flashcard_service import (
    add_cards, anki_export, generate_cards_from_note, FlashcardGenerationError,
)

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])

MASTERED_DAYS = 21


def _state(card: Flashcard) -> CardState:
    return CardState(
        ease_factor=float(card.ease_factor),       # type: ignore
        interval_days=int(card.interval_days),     # type: ignore
        repetitions=int(card.repetitions),         # type: ignore
        lapses=int(card.lapses),                   # type: ignore
    )


def _out(card: Flashcard, with_previews: bool = False) -> FlashcardOut:
    return FlashcardOut(
        card_id=card.card_id,                      # type: ignore
        front=card.front,                          # type: ignore
        back=card.back,                            # type: ignore
        topic=card.topic,                          # type: ignore
        source=card.source,                        # type: ignore
        note_id=card.note_id,                      # type: ignore
        due_at=as_utc(card.due_at),                # type: ignore
        interval_days=card.interval_days,          # type: ignore
        repetitions=card.repetitions,              # type: ignore
        lapses=card.lapses,                        # type: ignore
        ease_factor=float(card.ease_factor),       # type: ignore
        previews=previews(_state(card), utcnow()) if with_previews else None,
    )


def _get_card(db: Session, card_id: int, user_id: int) -> Flashcard:
    card = db.query(Flashcard).filter(Flashcard.card_id == card_id, Flashcard.user_id == user_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    return card


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _stats(db: Session, user_id: int, since: datetime | None) -> FlashcardStats:
    now = utcnow()
    base = db.query(Flashcard).filter(Flashcard.user_id == user_id)
    since_utc = _naive_utc(since) or (now - timedelta(hours=24))
    next_due = None
    due_now = base.filter(Flashcard.due_at <= now).count()
    if due_now == 0:
        next_due = db.query(func.min(Flashcard.due_at)).filter(Flashcard.user_id == user_id).scalar()
    return FlashcardStats(
        total=base.count(),
        due_now=due_now,
        new=base.filter(Flashcard.repetitions == 0, Flashcard.last_reviewed_at.is_(None)).count(),
        learning=base.filter(Flashcard.last_reviewed_at.isnot(None), Flashcard.interval_days < MASTERED_DAYS).count(),
        mastered=base.filter(Flashcard.interval_days >= MASTERED_DAYS).count(),
        reviewed_today=base.filter(Flashcard.last_reviewed_at >= since_utc).count(),
        next_due_at=as_utc(next_due),
    )


@router.get("/due", response_model=DueCards)
def due_cards(
    limit: int = Query(default=100, ge=1, le=500),
    since: datetime | None = Query(default=None, description="start of the user's local day, for 'reviewed today'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The review queue: cards due now, most overdue first (new cards last)."""
    user_id = cast(int, current_user.user_id)
    cards = db.query(Flashcard).filter(
        Flashcard.user_id == user_id, Flashcard.due_at <= utcnow()
    ).order_by(
        (Flashcard.last_reviewed_at.is_(None)).asc(),   # cards already in rotation before brand-new ones
        Flashcard.due_at.asc(),
        Flashcard.card_id.asc(),
    ).limit(limit).all()
    return DueCards(cards=[_out(c, with_previews=True) for c in cards], stats=_stats(db, user_id, since))


@router.get("/stats", response_model=FlashcardStats)
def card_stats(
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _stats(db, cast(int, current_user.user_id), since)


@router.get("/export/anki")
def export_anki(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cards = db.query(Flashcard).filter(Flashcard.user_id == current_user.user_id).order_by(Flashcard.card_id).all()
    if not cards:
        raise HTTPException(status_code=404, detail="You don't have any flashcards to export yet.")
    return Response(
        content=anki_export(cards),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="study-assistant-flashcards.txt"'},
    )


@router.get("", response_model=list[FlashcardOut])
def list_cards(
    search: str | None = Query(default=None, max_length=200),
    topic: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Flashcard).filter(Flashcard.user_id == current_user.user_id)
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.filter(or_(Flashcard.front.ilike(like), Flashcard.back.ilike(like), Flashcard.topic.ilike(like)))
    if topic and topic.strip():
        q = q.filter(func.lower(Flashcard.topic) == topic.strip().lower())
    return [_out(c) for c in q.order_by(Flashcard.created_at.desc(), Flashcard.card_id.desc()).limit(1000).all()]


@router.post("", response_model=FlashcardOut, status_code=201)
def create_card(request: FlashcardCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    added = add_cards(
        db, cast(int, current_user.user_id),
        [{"front": request.front, "back": request.back}],
        source="manual", topic=request.topic or None,
    )
    if not added:
        raise HTTPException(status_code=409, detail="You already have a card with this front.")
    db.commit()
    db.refresh(added[0])
    return _out(added[0])


@router.post("/generate", response_model=FlashcardGenerateResponse)
def generate_from_note(request: FlashcardGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    note = db.query(Note).filter(Note.note_id == request.note_id, Note.user_id == current_user.user_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Lesson not found")

    title = cast(str, note.title)
    topic = title
    for prefix in ("Notes on ", "Simplified Notes: ", "Fix-up Notes: "):
        if topic.startswith(prefix):
            topic = topic[len(prefix):].split(" (round")[0]

    try:
        cards = generate_cards_from_note(cast(str, note.content), topic, request.count)
    except FlashcardGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))

    added = add_cards(db, cast(int, current_user.user_id), cards, source="note", topic=topic, note_id=note.note_id)  # type: ignore
    db.commit()
    for c in added:
        db.refresh(c)
    skipped = len(cards) - len(added)
    return FlashcardGenerateResponse(
        added=[_out(c) for c in added],
        skipped_duplicates=skipped,
        message=f"Added {len(added)} flashcard{'s' if len(added) != 1 else ''} from “{topic}”"
                + (f" ({skipped} duplicate{'s' if skipped != 1 else ''} skipped)" if skipped else "") + ".",
    )


@router.post("/{card_id}/review", response_model=FlashcardOut)
def review_card(card_id: int, request: ReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = _get_card(db, card_id, cast(int, current_user.user_id))
    now = utcnow()
    nxt = schedule(_state(card), request.rating, now)
    card.ease_factor = nxt.ease_factor          # type: ignore
    card.interval_days = nxt.interval_days      # type: ignore
    card.repetitions = nxt.repetitions          # type: ignore
    card.lapses = nxt.lapses                    # type: ignore
    card.due_at = nxt.due_at                    # type: ignore
    card.last_reviewed_at = now                 # type: ignore
    db.commit()
    db.refresh(card)
    return _out(card, with_previews=True)


@router.patch("/{card_id}", response_model=FlashcardOut)
def update_card(card_id: int, request: FlashcardUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = _get_card(db, card_id, cast(int, current_user.user_id))
    if request.front is not None:
        card.front = request.front              # type: ignore
    if request.back is not None:
        card.back = request.back                # type: ignore
    db.commit()
    db.refresh(card)
    return _out(card)


@router.delete("/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = _get_card(db, card_id, cast(int, current_user.user_id))
    db.delete(card)
    db.commit()
    return {"message": "Flashcard deleted"}
