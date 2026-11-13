"""
Self-healing learning loop endpoints.

POST /learning/remediate  — fix-up notes + a retest for a failed quiz
GET  /learning/progress   — per-topic attempt history and recovery status
"""
from typing import cast
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from Services.language import language_note
from database import get_db, utcnow, as_utc
from models import Note, QuizDetail, User
from schemas import (
    RemediateRequest, RemediationResponse, LessonLite, QuizResponse,
    TopicProgress, Attempt,
)
from Routers.lessons import save_note_and_index, youtube_search_links
from Services.lesson_generator import generate_remediation_notes
from Services.quiz_generator import generate_quiz, QuizGenerationError
from Services.answer_check import qtype
from Routers.quiz import to_public
from Services.learning_loop import (
    PASS_MARK, MAX_LOOP_ROUNDS, loop_round, find_mistakes, topic_status,
    recent_average, submitted_quizzes_by_topic,
)

router = APIRouter(prefix="/learning", tags=["Learning loop"])


def _quiz_response(quiz: QuizDetail) -> QuizResponse:
    return QuizResponse(
        quiz_id=cast(int, quiz.quiz_id),
        topic=cast(str, quiz.topic),
        questions=[to_public(q) for q in quiz.questions],  # type: ignore
        total_questions=cast(int, quiz.total_questions),
        difficulty=cast(str, quiz.difficulty) or "medium",
        message="Retest ready",
    )


def _remediation_response(db: Session, retest: QuizDetail, note: Note, missed: int, message: str) -> RemediationResponse:
    return RemediationResponse(
        loop_round=loop_round(db, retest),
        missed_count=missed,
        note=LessonLite(note_id=note.note_id, title=note.title, content=note.content),   # type: ignore
        quiz=_quiz_response(retest),
        message=message,
    )


@router.post("/remediate", response_model=RemediationResponse)
def remediate(request: RemediateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    quiz = db.query(QuizDetail).filter(
        QuizDetail.quiz_id == request.quiz_id,
        QuizDetail.user_id == current_user.user_id,
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.submitted_at is None:
        raise HTTPException(status_code=400, detail="Submit the quiz first.")
    if float(quiz.score_percentage) >= PASS_MARK:     # type: ignore
        raise HTTPException(status_code=400, detail="You already passed this quiz — nothing to fix!")

    mistakes = find_mistakes(quiz)

    # Already generated a retest for this quiz? Reuse it instead of paying for a new one.
    existing = db.query(QuizDetail).filter(
        QuizDetail.parent_quiz_id == quiz.quiz_id,
        QuizDetail.user_id == current_user.user_id,
    ).order_by(QuizDetail.quiz_id.desc()).first()
    if existing is not None:
        if existing.submitted_at is not None:
            raise HTTPException(
                status_code=409,
                detail="You've already retaken this quiz. Continue the loop from your latest attempt.",
            )
        note = db.get(Note, existing.note_id)
        return _remediation_response(db, existing, note, len(mistakes), "Your retest is still waiting for you.")   # type: ignore

    next_round = loop_round(db, quiz) + 1
    if next_round > MAX_LOOP_ROUNDS:
        raise HTTPException(
            status_code=400,
            detail=f"You've done {MAX_LOOP_ROUNDS} rounds on this topic. Take a break, "
                   "ask the tutor about it, or try the viva for a different angle.",
        )

    topic = cast(str, quiz.topic)
    student_class = cast(str, current_user.student_class) or "college"

    # "auto" follows the language of the lesson this quiz was taken on
    original_note = db.get(Note, quiz.note_id)
    lang = language_note(
        current_user.preferred_language,                                     # type: ignore
        cast(str, original_note.content) if original_note else topic,
    )

    # Generate BOTH before saving anything, so a failure leaves no half-finished loop
    content = generate_remediation_notes(topic, student_class, mistakes, language_note=lang)
    try:
        # Retest in the same format as the original: same question types, difficulty and length
        questions = generate_quiz(
            content, topic,
            focus=[m["question"] for m in mistakes],
            question_types=list(dict.fromkeys(qtype(q) for q in quiz.questions)),   # type: ignore
            difficulty=cast(str, quiz.difficulty) or "medium",
            count=max(3, min(10, cast(int, quiz.total_questions))),
            language_note=lang,
        )
    except QuizGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))

    note = save_note_and_index(
        db, cast(int, current_user.user_id),
        title=f"Fix-up Notes: {topic.title()} (round {next_round})",
        content=content, topic=topic,
        youtube_links=youtube_search_links(f"{topic} common mistakes", student_class),
    )

    retest = QuizDetail(
        topic=topic,
        questions=questions,
        total_questions=len(questions),
        correct_answers=0,
        incorrect_answers=0,
        score_percentage=0.00,
        attempted_at=utcnow(),
        submitted_at=None,
        difficulty=quiz.difficulty,
        user_id=current_user.user_id,
        note_id=note.note_id,
        parent_quiz_id=quiz.quiz_id,
    )
    db.add(retest)
    db.commit()
    db.refresh(retest)

    return _remediation_response(
        db, retest, note, len(mistakes),
        f"Round {next_round}: fix-up notes for {len(mistakes)} missed question(s), then a fresh retest.",
    )


@router.get("/progress", response_model=list[TopicProgress])
def progress(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Every topic's attempts over time and where it stands in the loop."""
    result = []
    for quizzes in submitted_quizzes_by_topic(db, cast(int, current_user.user_id)).values():
        scores = [float(q.score_percentage) for q in quizzes]      # type: ignore
        rounds = [loop_round(db, q) for q in quizzes]
        latest = quizzes[-1]
        result.append(TopicProgress(
            topic=cast(str, latest.topic),
            status=topic_status(scores, loop_started=any(r > 1 for r in rounds)),
            recent_average=recent_average(scores),
            latest_score=scores[-1],
            latest_quiz_id=cast(int, latest.quiz_id),
            attempts=[
                Attempt(quiz_id=q.quiz_id, score=s, submitted_at=as_utc(q.submitted_at), loop_round=r)   # type: ignore
                for q, s, r in zip(quizzes, scores, rounds)
            ],
        ))

    order = {"needs_work": 0, "in_recovery": 1, "recovered": 2, "mastered": 3}
    result.sort(key=lambda t: (order.get(t.status, 9), t.recent_average))
    return result
