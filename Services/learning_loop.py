"""
Self-healing learning loop — the logic shared by the quiz, analytics and
learning routers.

  quiz < 70%  →  targeted fix-up notes  →  retest on the same concepts
       ↑                                              │
       └──────────── still < 70% ─────────────────────┘     ≥ 70% → recovered ✓

Topic mastery uses the RECENT average (last 3 attempts) rather than the
all-time average, so recovering from a weak start actually shows up.
"""
from sqlalchemy.orm import Session

from models import QuizDetail
from Services.answer_check import check_answer

PASS_MARK = 70.0
RECENT_ATTEMPTS = 3
MAX_LOOP_ROUNDS = 5     # stop generating retests after this many rounds in one chain


def loop_round(db: Session, quiz: QuizDetail) -> int:
    """1 for an original quiz, 2 for its first retest, and so on."""
    rounds = 1
    current = quiz
    seen = {current.quiz_id}
    while current.parent_quiz_id is not None:
        parent = db.get(QuizDetail, current.parent_quiz_id)
        if parent is None or parent.quiz_id in seen:
            break
        seen.add(parent.quiz_id)
        rounds += 1
        current = parent
    return rounds


def find_mistakes(quiz: QuizDetail) -> list[dict]:
    """
    Questions the student got wrong: [{question, user_answer, correct_answer}].
    For quizzes submitted before answers were recorded we can't tell which
    were wrong, so every question is treated as one to revisit.
    """
    answers: dict | None = quiz.user_answers      # type: ignore
    mistakes = []
    for q in quiz.questions:                      # type: ignore
        given = answers.get(q["question"]) if answers else None
        if answers is None or not check_answer(q, given)[0]:
            mistakes.append({
                "question": q["question"],
                "user_answer": given,
                "correct_answer": q["correct_answer"],
            })
    return mistakes


def topic_status(scores: list[float], loop_started: bool) -> str:
    """
    mastered    — latest ≥ 70 and never failed
    recovered   — latest ≥ 70 after failing earlier
    in_recovery — latest < 70 and a fix-up loop has been started
    needs_work  — latest < 70, no loop yet
    """
    latest = scores[-1]
    if latest >= PASS_MARK:
        return "recovered" if any(s < PASS_MARK for s in scores[:-1]) else "mastered"
    return "in_recovery" if loop_started else "needs_work"


def recent_average(scores: list[float]) -> float:
    recent = scores[-RECENT_ATTEMPTS:]
    return round(sum(recent) / len(recent), 2)


def submitted_quizzes_by_topic(db: Session, user_id: int) -> dict[str, list[QuizDetail]]:
    """{lower-cased topic: [submitted quizzes, oldest first]}"""
    quizzes = db.query(QuizDetail).filter(
        QuizDetail.user_id == user_id,
        QuizDetail.submitted_at.isnot(None),
    ).order_by(QuizDetail.submitted_at, QuizDetail.quiz_id).all()

    grouped: dict[str, list[QuizDetail]] = {}
    for q in quizzes:
        grouped.setdefault(str(q.topic).strip().lower(), []).append(q)
    return grouped
