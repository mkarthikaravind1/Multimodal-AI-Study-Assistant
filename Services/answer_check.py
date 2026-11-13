"""
Marks a student's answer for every question type.

Stored question shape (quiz_details.questions):
  {
    "type": "mcq" | "true_false" | "fill_blank" | "numerical",   (missing → "mcq", for old quizzes)
    "question": str,
    "options": [...],              mcq: 4 options · true_false: ["True", "False"] · others: []
    "correct_answer": str,         mcq/tf: exact option · fill: canonical answer · numerical: number
    "accepted_answers": [str],     fill_blank: other acceptable answers
    "tolerance": float,            numerical: allowed absolute error
    "unit": str,                   numerical: shown next to the input, ignored when marking
    "explanation": str,            why the correct answer is correct
    "option_explanations": {opt: why it's wrong}    mcq / true_false
    "difficulty": "easy" | "medium" | "hard"
  }
"""
import re
import unicodedata

QUESTION_TYPES = ("mcq", "true_false", "fill_blank", "numerical")
DEFAULT_RELATIVE_TOLERANCE = 0.01      # numerical: within 1% if the quiz didn't say


def qtype(q: dict) -> str:
    t = q.get("type")
    return t if t in QUESTION_TYPES else "mcq"


# ── normalising typed answers ─────────────────────────────────────────────────

_ARTICLES = {"a", "an", "the"}


def normalize_text(text: str) -> str:
    """'  The  Mitochondria! ' → 'mitochondria' (case, accents, punctuation, articles ignored)."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    # Remove punctuation (P*) and symbols (S*) by Unicode category — NOT a \w regex,
    # which would also strip the vowel signs of Tamil / Hindi words (combining marks).
    text = "".join(
        " " if unicodedata.category(ch)[0] in "PS" and ch not in ".+-" else ch
        for ch in text
    )
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)   # drop full stops, keep decimal points
    words = [w for w in text.split() if w not in _ARTICLES]
    return " ".join(words)


def _edit_distance(a: str, b: str, limit: int) -> int:
    """Levenshtein distance, giving up early once it exceeds `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _typo_allowance(answer: str) -> int:
    """No typos for short answers (too easy to hit another word), 1 for 5+ letters, 2 for 10+."""
    n = len(answer.replace(" ", ""))
    return 0 if n < 5 else 1 if n < 10 else 2


# ── numbers ───────────────────────────────────────────────────────────────────

_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_number(text) -> float | None:
    """
    '3,000' → 3000 · '9.81 m/s²' → 9.81 · '1.5e-3' → 0.0015 · '-4' → -4 · '1/4' → 0.25
    Returns None if there's no number.
    """
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    s = unicodedata.normalize("NFKC", str(text)).strip()
    s = s.replace("−", "-").replace("×10^", "e").replace("x10^", "e").replace("*10^", "e")
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)        # thousands separators
    frac = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*", s)
    if frac and float(frac.group(2)) != 0:
        return float(frac.group(1)) / float(frac.group(2))
    m = _NUMBER.search(s)
    return float(m.group()) if m else None


def numeric_tolerance(q: dict, correct: float) -> float:
    tol = q.get("tolerance")
    try:
        tol = float(tol)
        if tol >= 0:
            return tol
    except (TypeError, ValueError):
        pass
    return max(abs(correct) * DEFAULT_RELATIVE_TOLERANCE, 1e-9)


# ── marking ───────────────────────────────────────────────────────────────────

def check_answer(q: dict, given: str | None) -> tuple[bool, str | None]:
    """
    Returns (is_correct, note). `note` explains a lenient decision, e.g.
    "Accepted — small spelling difference" or "Accepted — within ±0.05".
    """
    given = (given or "").strip()
    if not given:
        return False, None
    t = qtype(q)
    correct = str(q.get("correct_answer", "")).strip()

    if t == "mcq":
        return given == correct, None

    if t == "true_false":
        return given.casefold() == correct.casefold(), None

    if t == "numerical":
        expected, got = parse_number(correct), parse_number(given)
        if expected is None or got is None:
            return False, None
        tol = numeric_tolerance(q, expected)
        if got == expected:
            return True, None
        if abs(got - expected) <= tol:
            return True, f"Accepted — within ±{tol:g} of {expected:g}"
        return False, None

    # fill_blank
    answer = normalize_text(given)
    accepted = [correct] + [str(a) for a in q.get("accepted_answers") or []]
    targets = [normalize_text(a) for a in accepted if str(a).strip()]
    if answer in targets:
        return True, None
    for target in targets:
        limit = _typo_allowance(target)
        if limit and _edit_distance(answer, target, limit) <= limit:
            return True, "Accepted — small spelling difference"
    return False, None


def why_wrong(q: dict, given: str | None) -> str | None:
    """For multiple choice / true-false: the stored explanation of why the chosen option is wrong."""
    if qtype(q) not in ("mcq", "true_false") or not given:
        return None
    explanations = q.get("option_explanations") or {}
    for option, why in explanations.items():
        if str(option).strip().casefold() == given.strip().casefold() and str(why).strip():
            return str(why).strip()
    return None
