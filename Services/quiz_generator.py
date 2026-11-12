import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MIN_VALID_QUESTIONS = 3


class QuizGenerationError(Exception):
    """Raised when the LLM output can't be turned into a usable quiz."""


def _validate_questions(raw_questions) -> list[dict]:
    """
    Keeps only well-formed MCQs: a question, exactly 4 distinct options,
    and a correct_answer that is literally one of the options.
    Duplicate question texts are dropped (answers are keyed by question text).
    """
    if not isinstance(raw_questions, list):
        return []

    valid = []
    seen_questions = set()
    for q in raw_questions:
        if not isinstance(q, dict):
            continue
        question = str(q.get("question", "")).strip()
        options = q.get("options")
        correct = str(q.get("correct_answer", "")).strip()

        if not question or question in seen_questions:
            continue
        if not isinstance(options, list) or len(options) != 4:
            continue
        options = [str(o).strip() for o in options]
        if len(set(options)) != 4 or correct not in options:
            continue

        seen_questions.add(question)
        valid.append({"question": question, "options": options, "correct_answer": correct})

    return valid


def generate_quiz(content: str, topic: str) -> list[dict]:
    """
    Takes note content, returns a list of validated MCQ dicts (up to 5).
    Raises QuizGenerationError if the model output is unusable.
    """
    prompt = f"""
    You are a quiz generator. Based on the following study notes, generate exactly 5
    multiple choice questions about "{topic}".

    Study Notes:
    {content}

    Rules:
    - Each question must have exactly 4 different options
    - Only one option is correct
    - "correct_answer" must be copied EXACTLY from one of the 4 options (not a letter like "A")

    Return a JSON object in this exact format:
    {{
        "questions": [
            {{
                "question": "question text here",
                "options": ["option A", "option B", "option C", "option D"],
                "correct_answer": "option A"
            }}
        ]
    }}
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are a quiz generator. Always respond with a valid JSON object only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.5,    # lower = more consistent JSON structure
        max_tokens=1024,
        response_format={"type": "json_object"},   # forces syntactically valid JSON
    )

    raw_text = (response.choices[0].message.content or "").strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise QuizGenerationError("The AI returned an invalid quiz. Please try again.") from e

    raw_questions = data.get("questions") if isinstance(data, dict) else data
    questions = _validate_questions(raw_questions)[:5]

    if len(questions) < MIN_VALID_QUESTIONS:
        raise QuizGenerationError("The AI returned an incomplete quiz. Please try again.")

    return questions
