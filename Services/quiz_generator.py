import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_quiz(content:str,topic:str)->list[dict]:
    """
    Takes note content, returns list of 5 MCQ dicts.
    One job only — generate and parse. Nothing else.
    """
    prompt = f"""
    You are a quiz generator. Based on the following study notes, generate exactly 5 
    multiple choice questions.

    Study Notes:
    {content}

    Rules:
    - Each question must have exactly 4 options
    - Only one option is correct
    - Return ONLY a JSON array, no explanation, no extra text
    - Do not wrap in markdown or code blocks

    Return this exact format:
    [
        {{
            "question": "question text here",
            "options": ["option A", "option B", "option C", "option D"],
            "correct_answer": "option A"
        }}
    ]
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are a quiz generator. Always respond with valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.5,    # lower = more consistent JSON structure
        max_tokens=1024
    )

    raw_text = str(response.choices[0].message.content).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]         # remove opening ```json
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]                 # remove the word "json"

    questions = json.loads(raw_text)                # convert string → list of dicts

    return questions