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