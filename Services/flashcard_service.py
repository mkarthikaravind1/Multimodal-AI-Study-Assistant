"""
Flashcards: AI generation from lessons, auto-cards from mistakes, de-duplication
and Anki export.
"""
import os
import json
import html
from groq import Groq
from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import utcnow
from models import Flashcard

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MAX_FRONT = 500
MAX_BACK = 1500
MAX_NOTE_CHARS = 6000


class FlashcardGenerationError(Exception):
    """The LLM output couldn't be turned into cards."""


def _clean(card: dict) -> dict | None:
    front = str(card.get("front", "")).strip()[:MAX_FRONT]
    back = str(card.get("back", "")).strip()[:MAX_BACK]
    return {"front": front, "back": back} if front and back else None


def generate_cards_from_note(content: str, topic: str, count: int) -> list[dict]:
    """LLM → [{"front": question, "back": answer}, ...] (at least 1)."""
    prompt = f"""
    Create {count} flashcards for active recall from these study notes on "{topic}".

    Good flashcards:
    - test ONE fact or idea each (atomic)
    - front: a clear question or cue (not "What is in the notes?")
    - back: a short, complete answer (1-3 sentences)
    - cover the most important ideas; no duplicates

    Study notes:
    {content[:MAX_NOTE_CHARS]}

    Return a JSON object exactly like:
    {{"cards": [{{"front": "question", "back": "answer"}}]}}
    """
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You write excellent study flashcards. Respond with JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.choices[0].message.content or "")
    except json.JSONDecodeError as e:
        raise FlashcardGenerationError("The AI returned invalid flashcards. Please try again.") from e

    raw = data.get("cards") if isinstance(data, dict) else None
    cards = [c for c in (_clean(x) for x in raw or [] if isinstance(x, dict)) if c]
    if not cards:
        raise FlashcardGenerationError("The AI couldn't make flashcards from this lesson. Please try again.")
    return cards[:count]


def add_cards(
    db: Session,
    user_id: int,
    cards: list[dict],
    source: str,
    topic: str | None = None,
    note_id: int | None = None,
    quiz_id: int | None = None,
) -> list[Flashcard]:
    """
    Adds cards that the user doesn't already have (same front text, case-insensitive).
    New cards are due immediately. Does NOT commit — the caller does.
    """
    existing = {
        f.lower()
        for (f,) in db.query(func.lower(Flashcard.front)).filter(Flashcard.user_id == user_id).all()
    }
    added = []
    for card in cards:
        clean = _clean(card)
        if not clean or clean["front"].lower() in existing:
            continue
        existing.add(clean["front"].lower())
        fc = Flashcard(
            user_id=user_id, front=clean["front"], back=clean["back"],
            topic=topic, source=source, note_id=note_id, quiz_id=quiz_id,
            ease_factor=2.5, interval_days=0, repetitions=0, lapses=0,
            due_at=utcnow(), created_at=utcnow(),
        )
        db.add(fc)
        added.append(fc)
    return added


def _anki_field(text: str) -> str:
    # Anki text import with "#html:true": escape HTML, keep line breaks, no tabs
    return html.escape(text).replace("\t", "    ").replace("\r\n", "\n").replace("\n", "<br>")


def _anki_tag(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text.strip())[:60]


def anki_export(cards: list[Flashcard]) -> str:
    """
    Anki's plain-text import format (File → Import in Anki 2.1.55+): one card per
    line, tab-separated Front / Back / Tags, with header lines telling Anki how
    to read the file — no manual field mapping needed.
    """
    lines = [
        "#separator:Tab",
        "#html:true",
        "#notetype:Basic",
        "#deck:Multimodal AI Study Assistant",
        "#tags column:3",
    ]
    for c in cards:
        tags = ["study-assistant", f"source::{c.source}"]
        if c.topic:
            tags.append(_anki_tag(str(c.topic)))
        lines.append("\t".join([_anki_field(str(c.front)), _anki_field(str(c.back)), " ".join(tags)]))
    return "\n".join(lines) + "\n"
