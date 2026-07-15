import os
import base64
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_image(image_bytes: bytes, question: str) -> str:
    """
    Sends image + question to Groq Vision LLM.
    Returns the model's explanation/answer as a string.
    """

    # Step 1 — Convert image bytes to base64 string
    # Vision LLMs don't accept raw binary — they need base64 encoded text
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Step 2 — Call Groq Vision model
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",  # Groq's vision model
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
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