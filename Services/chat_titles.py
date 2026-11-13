"""
Titles and search snippets for tutor chat sessions.
Kept free of heavy imports — the 0010 migration uses session_title too.
"""
import re

MAX_TITLE = 60

# The tutor page wraps questions about a fresh upload like this — show the question instead
_UPLOAD_PREFIX = re.compile(r"^Regarding the (?:PDF|video) I just uploaded \(filename: ([^)]*)\):\s*", re.I)
_IMAGE_PREFIX = re.compile(r"^\[Uploaded image: ([^\]]*)\]\s*", re.I)


def clean_question(text: str) -> str:
    text = " ".join(str(text or "").split())
    m = _UPLOAD_PREFIX.match(text) or _IMAGE_PREFIX.match(text)
    if m:
        rest = text[m.end():].strip()
        text = f"{m.group(1)}: {rest}" if rest else m.group(1)
    return text


def shorten(text: str, limit: int = MAX_TITLE) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return (cut if len(cut) > limit // 2 else text[: limit - 1]).rstrip(" ,.;:") + "…"


def session_title(messages: list) -> str:
    """The first question, shortened — 'New chat' if there isn't one."""
    for m in messages or []:
        if isinstance(m, dict) and m.get("role") == "user" and str(m.get("content", "")).strip():
            return shorten(clean_question(m["content"])) or "New chat"
    return "New chat"


def search_snippet(text: str, query: str, radius: int = 40) -> str | None:
    """'…text around the match…' (case-insensitive), or None if query isn't in text."""
    text = " ".join(str(text or "").split())
    i = text.lower().find(query.lower())
    if i < 0:
        return None
    start, end = max(0, i - radius), min(len(text), i + len(query) + radius)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
