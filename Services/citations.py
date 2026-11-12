"""
Turns retrieved ChromaDB chunks into numbered, clickable citations.

A citation (what the frontend receives) looks like:
    {"id": "S1", "type": "pdf", "label": "lecture.pdf · p. 4",
     "filename": "lecture.pdf", "material_id": 7, "page": 4}
    {"id": "S2", "type": "video", "label": "talk.mp4 · 03:42",
     "material_id": 9, "start_sec": 222.0, "timestamp": "03:42"}
    {"id": "S3", "type": "note", "label": "Notes on Graphs", "note_id": 12}
"""


def format_timestamp(seconds: float) -> str:
    """75.3 -> '01:15', 3725 -> '1:02:05'"""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def build_sources(hits: list[dict], note_titles: dict[int, str]) -> list[dict]:
    """
    hits: [{"text": ..., "meta": {...}}] from embedding_service.retrieve_sources
    note_titles: {note_id: title} for lesson chunks
    Returns citations with ids S1..Sn, each also carrying "text" (for the prompt only).
    """
    sources = []
    for i, hit in enumerate(hits, start=1):
        meta = hit["meta"]
        kind = meta.get("source", "note")
        src: dict = {"id": f"S{i}", "type": kind, "text": hit["text"]}

        if kind == "note":
            note_id = meta.get("note_id")
            src["note_id"] = note_id
            src["label"] = note_titles.get(note_id, f"Notes on {str(meta.get('topic', '')).title()}".strip())
        else:
            filename = meta.get("filename", "file")
            src["filename"] = filename
            src["material_id"] = meta.get("material_id")
            label = filename
            if kind == "pdf" and meta.get("page"):
                src["page"] = int(meta["page"])
                label += f" · p. {src['page']}"
            if kind == "video" and meta.get("start_sec") is not None:
                src["start_sec"] = float(meta["start_sec"])
                src["timestamp"] = format_timestamp(src["start_sec"])
                label += f" · {src['timestamp']}"
            src["label"] = label

        sources.append(src)
    return sources


def public_citation(source: dict) -> dict:
    """The citation without the chunk text — what gets stored and sent to the browser."""
    return {k: v for k, v in source.items() if k != "text"}
