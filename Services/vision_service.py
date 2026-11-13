import os
import base64
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"   # Groq's vision model


def _data_url(image_bytes: bytes, mime_type: str) -> str:
    # "image/jpg" is not a real MIME type — normalise it
    if mime_type == "image/jpg":
        mime_type = "image/jpeg"
    # Vision LLMs don't accept raw binary — they need base64 encoded text
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"


def vision_json(
    image_bytes: bytes,
    prompt: str,
    mime_type: str = "image/jpeg",
    system: str = "Respond with JSON only.",
    temperature: float = 0.1,
    max_tokens: int = 1500,
) -> str:
    """
    Image + prompt → the model's raw JSON text (JSON mode).
    The caller parses and validates it.
    """
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _data_url(image_bytes, mime_type)}},
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


def analyze_image(image_bytes: bytes, question: str, mime_type: str = "image/jpeg") -> str:
    """
    Sends image + question to Groq Vision LLM.
    Returns the model's explanation/answer as a string.
    mime_type must match the real image format (image/png, image/webp, …).
    """

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": _data_url(image_bytes, mime_type)}
                    },
                    {
                        "type": "text",
                        "text": question
                    }
                ]
            }
        ],
        temperature=0.7,
        max_tokens=1024
    )

    return response.choices[0].message.content or ""
