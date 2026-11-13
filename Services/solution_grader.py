"""
Handwritten solution grading.

Two vision passes over the photo of a worked problem:

  1. transcribe_solution — read the problem and every step exactly as written
     (no fixing). The student sees this transcription and can correct a
     misread step before re-checking, so a bad OCR read never "becomes" a
     mistake the student didn't make.
  2. grade_solution — check the steps in order, mark each one, and point at
     the FIRST real mistake (later steps that only carry that mistake forward
     are marked "follows_error", not blamed again).

All LLM output is validated here; the router only stores what comes back.
"""
import json

from Services.vision_service import vision_json
from Services.answer_check import parse_number, DEFAULT_RELATIVE_TOLERANCE

MAX_STEPS = 40
MAX_STEP_CHARS = 500

STEP_STATUSES = ("correct", "error", "follows_error", "unclear")
VERDICTS = ("correct", "incorrect", "incomplete", "unreadable")
ERROR_TYPES = (
    "arithmetic", "algebra", "sign", "concept", "formula", "units",
    "copying", "logic", "notation", "other",
)

SYSTEM = (
    "You are a careful, encouraging maths and science teacher marking a student's "
    "handwritten work. Respond with JSON only."
)


class SolutionError(Exception):
    """The vision model's output couldn't be used."""


def _parse(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SolutionError("The AI couldn't read this solution properly. Please try again.") from e
    if not isinstance(data, dict):
        raise SolutionError("The AI couldn't read this solution properly. Please try again.")
    return data


def _text(value, limit: int = MAX_STEP_CHARS) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def clean_steps(steps) -> list[str]:
    """List of non-empty step strings, trimmed and capped."""
    if not isinstance(steps, list):
        return []
    out = []
    for s in steps:
        if isinstance(s, dict):                 # tolerate [{"text": "..."}]
            s = s.get("text") or s.get("step") or ""
        t = _text(s)
        if t:
            out.append(t)
    return out[:MAX_STEPS]


# ── pass 1: transcription ─────────────────────────────────────────────────────

def transcribe_solution(image_bytes: bytes, mime_type: str, problem_hint: str = "") -> dict:
    """
    Returns {"problem": str, "steps": [str], "final_answer": str, "legible": bool}.
    """
    hint = (
        f'\nThe student says the problem is:\n"""{problem_hint}"""\n'
        if problem_hint else ""
    )
    prompt = f"""
    This photo shows a student's handwritten worked solution.{hint}
    Transcribe it EXACTLY as written — do NOT fix mistakes, do NOT skip lines,
    do NOT solve it yourself. Wrong working must stay wrong.

    - "problem": the question being solved, if it is written on the page (else "").
    - "steps": every line of working in order, one entry per line/step.
      Write maths in plain text: x^2, sqrt(x), 3/4, a*b, pi, theta, ->, <=.
      If a part is unreadable write [illegible] in its place.
    - "final_answer": the answer the student ended with (boxed/underlined/last line), or "".
    - "legible": false if the photo is too blurry, dark or cropped to read any working,
      or if it isn't handwritten working at all.

    Return JSON exactly like:
    {{"problem": "...", "steps": ["...", "..."], "final_answer": "...", "legible": true}}
    """
    data = _parse(vision_json(image_bytes, prompt, mime_type, SYSTEM, temperature=0.0, max_tokens=1500))

    steps = clean_steps(data.get("steps"))
    legible = data.get("legible", True) is not False and bool(steps)
    return {
        "problem": _text(data.get("problem"), 2000),
        "steps": steps,
        "final_answer": _text(data.get("final_answer"), 255),
        "legible": legible,
    }


# ── pass 2: grading ───────────────────────────────────────────────────────────

def answers_match(given: str, expected: str) -> bool | None:
    """
    Deterministic check when the student told us the expected answer.
    Numbers are compared within 1%; otherwise None (= can't tell, trust the AI).
    """
    if not given or not expected:
        return None
    g, e = parse_number(given), parse_number(expected)
    if g is None or e is None:
        return None
    return abs(g - e) <= max(abs(e) * DEFAULT_RELATIVE_TOLERANCE, 1e-9)


def grade_solution(
    image_bytes: bytes,
    mime_type: str,
    problem: str,
    steps: list[str],
    final_answer: str = "",
    expected_answer: str = "",
    topic: str = "",
    confirmed: bool = False,
) -> dict:
    """
    Returns {
      "steps": [{"text", "status", "comment", "correction"}],   same length/order as `steps`
      "first_error_step": int | None,                           0-based
      "error_type": str | None,
      "verdict": correct | incorrect | incomplete,
      "score": 0-10,
      "summary": str, "hint": str, "correct_answer": str,
      "answer_matches_expected": bool | None,
    }
    `confirmed` = the student checked/corrected the transcription themselves.
    """
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
    context = []
    if topic:
        context.append(f"Topic: {topic}")
    if expected_answer:
        context.append(f"The correct final answer (from the student's answer key): {expected_answer}")
    context_text = "\n    ".join(context)
    source_note = (
        "The student has CONFIRMED this transcription is what they wrote — trust the text over the photo."
        if confirmed else
        "This transcription was made from the photo; if a step looks misread, use the photo."
    )

    prompt = f"""
    Problem: {problem or "(not given — infer it from the photo)"}
    {context_text}

    The student's working, step by step ({source_note}):
    {numbered}

    Student's final answer: {final_answer or "(none written)"}

    Check EVERY step in order, re-doing each calculation yourself.
    For each step give a status:
      "correct"       — valid from the previous step
      "error"         — a NEW mistake is made in this step
      "follows_error" — the method is right but it carries forward an earlier mistake
      "unclear"       — can't be read or judged
    The first step marked "error" is the FIRST MISTAKE. Only blame a step that is really
    wrong — different-but-valid methods, skipped trivial steps and notation style are fine.

    For error steps: "comment" says exactly what went wrong (to the student, "you"),
    "correction" gives the corrected line. For other steps keep "comment" short or "".

    Return JSON exactly like:
    {{
      "steps": [{{"step": 1, "status": "correct", "comment": "", "correction": ""}}],
      "first_error_step": 3,
      "error_type": "arithmetic | algebra | sign | concept | formula | units | copying | logic | notation | other",
      "verdict": "correct | incorrect | incomplete",
      "score": 7,
      "summary": "2 sentences to the student: what went well and what went wrong",
      "hint": "a nudge to find/fix the mistake WITHOUT giving the answer",
      "correct_answer": "the correct final answer"
    }}
    Use null for first_error_step and error_type when there is no mistake.
    Score out of 10: full marks only if every step is correct and the answer is right;
    give method marks for correct steps before the first mistake.
    """
    data = _parse(vision_json(image_bytes, prompt, mime_type, SYSTEM, temperature=0.1, max_tokens=2500))

    # ── per-step marks: align to OUR step list by the "step" number (1-based) ──
    by_index: dict[int, dict] = {}
    raw_steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    for pos, item in enumerate(raw_steps):
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("step", pos + 1)) - 1
        except (TypeError, ValueError):
            idx = pos
        if 0 <= idx < len(steps) and idx not in by_index:
            by_index[idx] = item
    if steps and not by_index:
        raise SolutionError("The AI couldn't mark this solution. Please try again.")

    graded = []
    for i, text in enumerate(steps):
        item = by_index.get(i, {})
        status = str(item.get("status", "")).strip().lower()
        if status not in STEP_STATUSES:
            status = "unclear" if not item else "correct"
        graded.append({
            "text": text,
            "status": status,
            "comment": _text(item.get("comment")),
            "correction": _text(item.get("correction")),
        })

    # ── first mistake: the model's number must agree with the step statuses ──
    first_error = next((i for i, s in enumerate(graded) if s["status"] == "error"), None)
    try:
        claimed = data.get("first_error_step")
        claimed = int(claimed) - 1 if claimed is not None else None
    except (TypeError, ValueError):
        claimed = None
    if first_error is None and claimed is not None and 0 <= claimed < len(graded):
        graded[claimed]["status"] = "error"     # model named a mistake but didn't mark it
        first_error = claimed
    if first_error is not None:
        # nothing before the first mistake can "follow" from it
        for s in graded[:first_error]:
            if s["status"] == "follows_error":
                s["status"] = "correct"
        if not graded[first_error]["comment"]:
            graded[first_error]["comment"] = "This step contains the first mistake."

    error_type = str(data.get("error_type") or "").strip().lower() or None
    if first_error is None:
        error_type = None
    elif error_type not in ERROR_TYPES:
        error_type = "other"

    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in ("correct", "incorrect", "incomplete"):
        verdict = "incorrect" if first_error is not None else "correct"
    if first_error is not None:
        verdict = "incorrect"
    elif verdict == "incorrect":
        verdict = "incomplete"      # "incorrect" but no step is wrong → treat as unfinished

    # ── the answer key wins over the model on the final number ──
    match = answers_match(final_answer, expected_answer)
    if match is False and verdict == "correct":
        verdict = "incorrect"
    if match is True and verdict == "incomplete" and first_error is None:
        verdict = "correct"

    try:
        score = int(round(float(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(10, score))
    if verdict == "correct":
        score = max(score, 9)
    else:
        score = min(score, 8)       # any mistake / missing answer → not full marks

    correct_answer = _text(data.get("correct_answer"), 255)
    if expected_answer:
        correct_answer = expected_answer

    summary = _text(data.get("summary"), 1000)
    if not summary:
        summary = (
            "Every step checks out — well done!" if verdict == "correct"
            else f"Your working goes wrong at step {first_error + 1}." if first_error is not None
            else "Your working looks right so far but doesn't reach a final answer."
        )

    return {
        "steps": graded,
        "first_error_step": first_error,
        "error_type": error_type,
        "verdict": verdict,
        "score": score,
        "summary": summary,
        "hint": _text(data.get("hint"), 1000),
        "correct_answer": correct_answer,
        "answer_matches_expected": match,
    }
