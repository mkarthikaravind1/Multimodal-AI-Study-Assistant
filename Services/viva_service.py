"""
Viva (oral exam) — question generation and answer grading.

Questions are open-ended (not MCQ). Each question carries hidden "key_points"
the examiner expects; answers are graded 0-10 against those points and the
lesson notes, with feedback, a model answer and the points that were missed.
"""
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Grading benefits from a stronger model. Set VIVA_MODEL in .env to use one
# (e.g. a larger Groq model); defaults to the model the rest of the app uses.
VIVA_MODEL = os.getenv("VIVA_MODEL", "llama-3.1-8b-instant")

MAX_NOTE_CHARS = 6000     # keep prompts well inside the token limit


class VivaError(Exception):
    """The LLM output couldn't be used."""


def _ask_json(system: str, prompt: str, temperature: float, max_tokens: int) -> dict:
    response = client.chat.completions.create(
        model=VIVA_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.choices[0].message.content or "")
    except json.JSONDecodeError as e:
        raise VivaError("The AI examiner returned an invalid response. Please try again.") from e
    if not isinstance(data, dict):
        raise VivaError("The AI examiner returned an invalid response. Please try again.")
    return data


def generate_viva_questions(content: str, topic: str, count: int, language_note: str = "") -> list[dict]:
    """Returns [{"question": str, "key_points": [str, ...]}, ...] (at least min(3, count))."""
    prompt = f"""
    You are an examiner conducting a VIVA (oral exam) on "{topic}".
    Based ONLY on the study notes below, write {count} open-ended questions a student
    must answer out loud in 3-6 sentences.

    Mix the question types:
    - "Explain ..." / "What is ... and why does it matter?"
    - "Compare ... with ..."
    - "Walk me through ..." / "What would happen if ...?"
    Start easy and get harder. No multiple choice. No yes/no questions.

    For each question also list 2-4 key points a good answer must mention.

    Study notes:
    {content[:MAX_NOTE_CHARS]}

    Return a JSON object exactly like:
    {{"questions": [{{"question": "...", "key_points": ["...", "..."]}}]}}
    """
    if language_note:
        prompt += f"\n    LANGUAGE of the questions and key points: {language_note} Keep the JSON keys in English.\n"
    data = _ask_json(
        "You are a fair, encouraging university viva examiner. Respond with JSON only.",
        prompt, temperature=0.6, max_tokens=1200,
    )

    questions = []
    seen = set()
    for q in data.get("questions") or []:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question", "")).strip()
        if not text or text.lower() in seen:
            continue
        points = q.get("key_points") or []
        points = [str(p).strip() for p in points if str(p).strip()] if isinstance(points, list) else []
        seen.add(text.lower())
        questions.append({"question": text, "key_points": points[:4]})

    questions = questions[:count]
    if len(questions) < min(3, count):
        raise VivaError("The AI examiner couldn't prepare enough questions. Please try again.")
    return questions


def grade_answer(question: str, key_points: list[str], answer: str, content: str, language_note: str = "") -> dict:
    """
    Returns {"score": 0-10, "feedback": str, "ideal_answer": str, "missed_points": [str]}.
    """
    points_text = "\n".join(f"- {p}" for p in key_points) or "- (use the notes)"
    prompt = f"""
    Viva question: "{question}"

    Key points a good answer should cover:
    {points_text}

    Reference notes (for accuracy):
    {content[:MAX_NOTE_CHARS]}

    The student's spoken answer (transcribed from speech — ignore filler words,
    small grammar slips and transcription errors):
    \"\"\"{answer}\"\"\"

    Grade it from 0 to 10:
      9-10 covers all key points correctly and clearly
      6-8  mostly correct, a point missing or slightly vague
      3-5  partly correct or important gaps
      0-2  wrong, off-topic, or "I don't know"
    Be fair: reward correct ideas even if worded differently from the notes.

    Return a JSON object exactly like:
    {{
      "score": 7,
      "feedback": "2-3 sentences to the student (second person): what was good, what to improve",
      "ideal_answer": "a concise model answer in 2-4 sentences",
      "missed_points": ["key point they missed", "..."]
    }}
    The answer may be in English, Hindi, Tamil, Hinglish or Tanglish — grade the ideas, not the language.
    """
    if language_note:
        prompt += f"\n    LANGUAGE of feedback, ideal_answer and missed_points: {language_note} Keep the JSON keys in English.\n"
    data = _ask_json(
        "You are a fair, encouraging university viva examiner. Respond with JSON only.",
        prompt, temperature=0.2, max_tokens=700,
    )

    try:
        score = int(round(float(data.get("score", 0))))
    except (TypeError, ValueError):
        raise VivaError("The AI examiner returned an invalid score. Please try again.")
    score = max(0, min(10, score))

    missed = data.get("missed_points") or []
    missed = [str(m).strip() for m in missed if str(m).strip()] if isinstance(missed, list) else []

    return {
        "score": score,
        "feedback": str(data.get("feedback", "")).strip() or "Answer recorded.",
        "ideal_answer": str(data.get("ideal_answer", "")).strip(),
        "missed_points": missed[:5],
    }
