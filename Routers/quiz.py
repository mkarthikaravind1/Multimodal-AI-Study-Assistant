from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, utcnow
from Routers.lessons import normalize_topic
from models import Note, QuizDetail, User
from schemas import QuestionPublic, QuizRequest, QuizResponse, QuizSubmitRequest, QuestionResult, QuizSubmitResponse
from Services.answer_check import check_answer, why_wrong, qtype
from Services.quiz_generator import generate_quiz, QuizGenerationError
from auth import get_current_user
from Services.language import language_note
from Services.learning_loop import PASS_MARK, loop_round
from Services.flashcard_service import add_cards

router = APIRouter(prefix="/quiz", tags=["Quiz"])


def to_public(q: dict) -> QuestionPublic:
    """Only what the student may see before answering."""
    return QuestionPublic(
        question=q["question"],
        type=qtype(q),                       # type: ignore
        options=q.get("options") or [],
        difficulty=q.get("difficulty"),
        unit=q.get("unit"),
    )

@router.post("/generate", response_model=QuizResponse)
def generate_quiz_route(request: QuizRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    # Only allow quizzes on the current user's own notes
    note = db.query(Note).filter(
        Note.note_id == request.note_id,
        Note.user_id == current_user.user_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    topic = normalize_topic(request.topic)

    try:
        questions = generate_quiz(
            str(note.content), topic,
            question_types=list(dict.fromkeys(request.question_types)),
            difficulty=request.difficulty,
            count=request.count,
            # explanations in the student's language ("auto": the lesson's language)
            language_note=language_note(current_user.preferred_language, str(note.content)),   # type: ignore
        )
    except QuizGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Full questions (with answers) are stored server-side only
    new_quiz = QuizDetail(
        topic=topic,
        questions=questions,
        total_questions=len(questions),
        correct_answers=0,
        incorrect_answers=0,
        score_percentage=0.00,
        attempted_at=utcnow(),
        submitted_at=None,
        difficulty=request.difficulty,
        user_id=current_user.user_id,
        note_id=note.note_id
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    # The client only gets question, type and options — never the answer or explanations
    return QuizResponse(
        quiz_id=int(new_quiz.quiz_id),          # type: ignore
        topic=str(new_quiz.topic),              # type: ignore
        questions=[to_public(q) for q in questions],
        total_questions=len(questions),
        difficulty=request.difficulty,
        message="Quiz generated successfully"
    )

@router.post("/submit", response_model=QuizSubmitResponse)
def submit_quiz(request: QuizSubmitRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    quiz = db.query(QuizDetail).filter(
        QuizDetail.quiz_id == request.quiz_id,
        QuizDetail.user_id == current_user.user_id
    ).first()

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # A quiz can only be scored once
    if quiz.submitted_at is not None:
        raise HTTPException(status_code=409, detail="This quiz has already been submitted")

    answer_key: dict[str, dict] = {q["question"]: q for q in quiz.questions}   # type: ignore

    # One answer per question: duplicates collapse, and every question must be answered
    submitted: dict[str, str] = {a.question: a.user_answer for a in request.answers}
    if len(submitted) != len(request.answers) or set(submitted) != set(answer_key):
        raise HTTPException(
            status_code=400,
            detail="Answer every question in the quiz exactly once."
        )

    results = []
    correct_count = 0

    # Iterate in the original question order
    for question, q in answer_key.items():
        user_answer = submitted[question]
        # Marks by type: exact option, true/false, typo-tolerant text, or number within tolerance
        is_correct, note = check_answer(q, user_answer)
        if is_correct:
            correct_count += 1

        results.append(QuestionResult(
            question=question,
            user_answer=user_answer,
            correct_answer=q["correct_answer"],
            is_correct=is_correct,
            type=qtype(q),
            difficulty=q.get("difficulty"),
            unit=q.get("unit"),
            explanation=q.get("explanation") or None,
            why_wrong=None if is_correct else why_wrong(q, user_answer),
            note=note,
        ))

    total = int(quiz.total_questions)           # type: ignore
    incorrect_count = total - correct_count
    score = round((correct_count / total) * 100, 2)

    # type: ignore silences false Pylance errors on SQLAlchemy assignments
    quiz.correct_answers = correct_count        # type: ignore
    quiz.incorrect_answers = incorrect_count    # type: ignore
    quiz.score_percentage = score               # type: ignore
    quiz.submitted_at = utcnow()       # type: ignore
    quiz.user_answers = submitted      # type: ignore  — needed to find mistakes for the learning loop

    # Every wrong answer becomes a flashcard (no AI call): question → answer + why
    def card_back(r: QuestionResult) -> str:
        answer = f"{r.correct_answer} {r.unit}".strip() if r.unit else r.correct_answer
        return f"{answer}\n\n{r.explanation}" if r.explanation else answer

    new_cards = add_cards(
        db, int(quiz.user_id),     # type: ignore
        [{"front": r.question, "back": card_back(r)} for r in results if not r.is_correct],
        source="mistake", topic=str(quiz.topic), note_id=quiz.note_id, quiz_id=quiz.quiz_id,   # type: ignore
    )
    db.commit()
    db.refresh(quiz)

    return QuizSubmitResponse(
        quiz_id=int(quiz.quiz_id),              # type: ignore
        topic=str(quiz.topic),                  # type: ignore
        total_questions=total,
        correct_answers=correct_count,
        incorrect_answers=incorrect_count,
        score_percentage=score,
        results=results,
        loop_round=loop_round(db, quiz),
        passed=score >= PASS_MARK,
        flashcards_added=len(new_cards),
        message=f"Quiz submitted. You scored {score}%"
    )
