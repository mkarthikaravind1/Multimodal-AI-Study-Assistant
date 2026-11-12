import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """
    Sends audio file to Groq Whisper API.
    Returns transcript as a plain string.
    One job only — transcribe. Nothing else.
    """

    # Groq's transcription API needs a file-like tuple:
    # (filename, bytes, content_type)
    response = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",   # Groq's hosted Whisper model
        file=(filename, audio_bytes),
        response_format="text"            # returns plain string, not JSON
    )

    return response                     # type: ignore

def transcribe_with_segments(audio_bytes: bytes, filename: str) -> tuple[str, list[dict]]:
    """
    Like transcribe_audio, but also returns timed segments:
    [{"start": 12.4, "end": 17.9, "text": "..."}, ...]
    Used for videos so tutor answers can cite an exact timestamp.
    """
    response = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=(filename, audio_bytes),
        response_format="verbose_json",   # includes per-segment timings
    )

    # The SDK model allows extra fields — segments arrive as dicts or objects
    raw_segments = getattr(response, "segments", None) or []
    segments = []
    for seg in raw_segments:
        get = seg.get if isinstance(seg, dict) else lambda k, d=None, s=seg: getattr(s, k, d)
        text = (get("text", "") or "").strip()
        if text:
            segments.append({"start": float(get("start", 0) or 0), "end": float(get("end", 0) or 0), "text": text})

    full_text = (getattr(response, "text", "") or " ".join(s["text"] for s in segments)).strip()
    return full_text, segments
