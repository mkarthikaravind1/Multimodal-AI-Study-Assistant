"""
Server-Sent Events helpers for streaming LLM output to the browser.

Wire format (one event):
    event: token
    data: {"text": "Hel"}

Events used by the app:
    token  — a piece of generated text                {"text": "..."}
    done   — generation finished and was saved        {...final result...}
    error  — generation failed; nothing was saved     {"detail": "..."}
"""
import json
from typing import Iterator

import groq
from fastapi.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",      # stop reverse proxies (nginx) from buffering the stream
}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def friendly_error(exc: Exception) -> str:
    """Same wording as the app's normal (non-streaming) error handlers."""
    if isinstance(exc, groq.RateLimitError):
        return "The AI service is busy (rate limit reached). Please wait a moment and try again."
    if isinstance(exc, groq.APIError):
        print(f"[Groq error] {type(exc).__name__}: {exc}")
        return "The AI service failed to respond. Please try again."
    print(f"[Stream error] {type(exc).__name__}: {exc}")
    return "Something went wrong while generating. Please try again."


def sse_response(events: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(events, media_type="text/event-stream", headers=SSE_HEADERS)
