"""
Quiz generation: multiple choice, true/false, fill-in-the-blank and numerical
questions, at a chosen difficulty, each with an explanation — and for multiple
choice, an explanation of why every wrong option is wrong.
"""
import os
import json
from groq import Groq
from dotenv import load_dotenv

from Services.answer_check import QUESTION_TYPES, parse_number

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MIN_VALID_QUESTIONS = 3
DIFFICULTIES = ("easy", "medium", "hard", "mixed")
MAX_NOTE_CHARS = 8000
MAX_FILL_WORDS = 6

TYPE_LABELS = {
    "mcq": "multiple choice",
    "true_false": "true/false",
    "fill_blank": "fill-in-the-blank",
    "numerical": "numerical",
}

DIFFICULTY_GUIDE = {
    "easy": "EASY — recall of definitions and key facts straight from the notes.",
    "medium": "MEDIUM — understanding and applying ideas, not just recalling them.",
    "hard": "HARD — multi-step reasoning, edge cases, comparisons; wrong options must be very plausible.",
    "mixed": "MIXED — start easy, end hard (label each question's own difficulty).",
}

FORMAT_EXAMPLE = """{
  "questions": [
    {"type": "mcq", "difficulty": "easy",
     "question": "Which data structure gives O(1) access to the minimum element?",
     "options": ["Min-heap", "Linked list", "Queue", "Hash table"],
     "correct_answer": "Min-heap",
     "explanation": "A min-heap always stores the smallest element at the root.",
     "option_explanations": {"Linked list": "Finding the minimum needs a full O(n) scan.",
                             "Queue": "A queue only gives fast access to the oldest element.",
                             "Hash table": "Hash tables have no ordering, so no quick minimum."}},
    {"type": "true_false", "difficulty": "medium",
     "question": "Inserting into a binary heap takes O(n) time.",
     "options": ["True", "False"], "correct_answer": "False",
     "explanation": "Insertion sifts up at most the tree's height, so it is O(log n).",
     "option_explanations": {"True": "O(n) is the cost of building a heap from n items, not of one insert."}},
    {"type": "fill_blank", "difficulty": "easy",
     "question": "In a max-heap, the largest element is always stored at the ____.",
     "correct_answer": "root", "accepted_answers": ["top", "root node"],
     "explanation": "The heap property puts the maximum at the root."},
    {"type": "numerical", "difficulty": "hard",
     "question": "What is the height of a complete binary heap with 1023 nodes? (count edges)",
     "correct_answer": "9", "tolerance": 0, "unit": "",
     "explanation": "1023 = 2^10 − 1 nodes fill 10 levels, so the height is 10 − 1 = 9 edges."}
  ]
}"""


class QuizGenerationError(Exception):
    """Raised when the LLM output can't be turned into a usable quiz."""


def _difficulty(value, quiz_difficulty: str) -> str:
    v = str(value or "").strip().lower()
    if v in ("easy", "medium", "hard"):
        return v
    return "medium" if quiz_difficulty == "mixed" else quiz_difficulty


def _clean_question(q: dict, quiz_difficulty: str) -> dict | None:
    """Validates one generated question; returns the stored shape or None if unusable."""
    t = str(q.get("type", "mcq")).strip().lower().replace("-", "_").replace(" ", "_")
    t = {"multiple_choice": "mcq", "truefalse": "true_false", "tf": "true_false",
         "fill_in_the_blank": "fill_blank", "fill_in": "fill_blank", "numeric": "numerical"}.get(t, t)
    if t not in QUESTION_TYPES:
        return None

    question = str(q.get("question", "")).strip()
    correct = str(q.get("correct_answer", "")).strip()
    explanation = str(q.get("explanation", "")).strip()
    if not question or not correct:
        return None

    out = {
        "type": t,
        "question": question,
        "options": [],
        "correct_answer": correct,
        "explanation": explanation,
        "difficulty": _difficulty(q.get("difficulty"), quiz_difficulty),
    }
    raw_expl = q.get("option_explanations") if isinstance(q.get("option_explanations"), dict) else {}

    if t == "mcq":
        options = q.get("options")
        if not isinstance(options, list) or len(options) != 4:
            return None
        options = [str(o).strip() for o in options]
        if len(set(options)) != 4 or "" in options or correct not in options:
            return None
        out["options"] = options
        out["option_explanations"] = {
            o: str(raw_expl.get(o, "")).strip() for o in options if o != correct and str(raw_expl.get(o, "")).strip()
        }

    elif t == "true_false":
        value = correct.casefold()
        if value in ("true", "t", "yes"):
            correct = "True"
        elif value in ("false", "f", "no"):
            correct = "False"
        else:
            return None
        out["correct_answer"] = correct
        out["options"] = ["True", "False"]
        wrong = "False" if correct == "True" else "True"
        why = next((str(v).strip() for k, v in raw_expl.items() if str(k).strip().casefold() == wrong.casefold()), "")
        out["option_explanations"] = {wrong: why} if why else {}

    elif t == "fill_blank":
        if len(correct.split()) > MAX_FILL_WORDS:
            return None                       # an essay answer can't be marked automatically
        accepted = q.get("accepted_answers") if isinstance(q.get("accepted_answers"), list) else []
        out["accepted_answers"] = [str(a).strip() for a in accepted if str(a).strip() and str(a).strip() != correct][:5]
        if "____" not in question and "___" not in question:
            question = question.rstrip()
            out["question"] = question if question.endswith("?") else f"{question} ____"

    elif t == "numerical":
        value = parse_number(correct)
        if value is None:
            return None
        out["correct_answer"] = f"{value:g}"
        tol = parse_number(q.get("tolerance")) if q.get("tolerance") not in (None, "") else None
        if tol is not None and tol >= 0:
            out["tolerance"] = abs(tol)
        unit = str(q.get("unit", "") or "").strip()
        if unit:
            out["unit"] = unit[:20]

    return out


def _validate_questions(raw_questions, allowed_types: tuple[str, ...], quiz_difficulty: str) -> list[dict]:
    if not isinstance(raw_questions, list):
        return []
    valid, seen = [], set()
    for q in raw_questions:
        if not isinstance(q, dict):
            continue
        clean = _clean_question(q, quiz_difficulty)
        if not clean or clean["type"] not in allowed_types:
            continue
        key = clean["question"].casefold()
        if key in seen:                       # answers are keyed by question text
            continue
        seen.add(key)
        valid.append(clean)
    return valid


def generate_quiz(
    content: str,
    topic: str,
    focus: list[str] | None = None,
    question_types: list[str] | None = None,
    difficulty: str = "medium",
    count: int = 5,
) -> list[dict]:
    """
    Generates `count` questions of the requested types and difficulty from the notes.
    focus: questions the student previously got wrong — the new quiz re-tests
           the same concepts with DIFFERENT questions (self-healing loop).
    Raises QuizGenerationError if the model output is unusable.
    """
    types = tuple(t for t in (question_types or ["mcq"]) if t in QUESTION_TYPES) or ("mcq",)
    difficulty = difficulty if difficulty in DIFFICULTIES else "medium"

    focus_text = ""
    if focus:
        listed = "\n".join(f"    - {q}" for q in focus)
        focus_text = f"""
    The student previously got these questions wrong:
{listed}
    Test the SAME underlying concepts again, but write NEW questions
    (different wording, different examples). Do not reuse the questions above.
"""

    type_list = ", ".join(f'"{t}" ({TYPE_LABELS[t]})' for t in types)
    numerical_note = (
        '\n    - "numerical": only if the notes contain something to calculate; otherwise use another allowed type'
        if "numerical" in types else ""
    )

    prompt = f"""
    Write exactly {count} quiz questions about "{topic}" based ONLY on the study notes below.

    Study Notes:
    {content[:MAX_NOTE_CHARS]}
    {focus_text}
    Question types to use: {type_list}. Mix them roughly evenly.
    Difficulty: {DIFFICULTY_GUIDE[difficulty]}

    Rules for every question:
    - "type" is one of the allowed types, "difficulty" is "easy", "medium" or "hard"
    - "explanation": 1-2 sentences on WHY the correct answer is correct
    - "mcq": exactly 4 different options; "correct_answer" copied EXACTLY from the options;
      "option_explanations" gives, for EACH wrong option, why a student might pick it and why it is wrong
    - "true_false": options ["True", "False"]; "correct_answer" is "True" or "False";
      "option_explanations" explains why the wrong choice is wrong
    - "fill_blank": the question contains ____ for the missing word(s); the answer is 1-4 words;
      "accepted_answers" lists synonyms/alternative spellings that are also correct
    - "numerical": "correct_answer" is a plain number (no units), "unit" holds the unit,
      "tolerance" is the allowed absolute error (0 for exact integers){numerical_note}

    Return a JSON object in exactly this format (this example is about a different topic):
    {FORMAT_EXAMPLE}
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are an expert examiner who writes fair, precise quizzes. Respond with a valid JSON object only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,    # lower = more consistent JSON structure
        max_tokens=3000,    # explanations for every option need room
        response_format={"type": "json_object"},   # forces syntactically valid JSON
    )

    raw_text = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise QuizGenerationError("The AI returned an invalid quiz. Please try again.") from e

    raw_questions = data.get("questions") if isinstance(data, dict) else data
    questions = _validate_questions(raw_questions, types, difficulty)[:count]

    needed = min(MIN_VALID_QUESTIONS, count)
    if len(questions) < needed:
        if types == ("numerical",):
            raise QuizGenerationError(
                "This lesson doesn't have enough to calculate for a numerical-only quiz. "
                "Add another question type and try again."
            )
        raise QuizGenerationError("The AI returned an incomplete quiz. Please try again.")

    if difficulty == "mixed":
        order = {"easy": 0, "medium": 1, "hard": 2}
        questions.sort(key=lambda q: order[q["difficulty"]])

    return questions
