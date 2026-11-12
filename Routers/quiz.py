from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, utcnow
from Routers.lessons import normalize_topic
from models import Note, QuizDetail, User
from schemas import MCQQuestionPublic, QuizRequest, QuizResponse, QuizSubmitRequest, QuestionResult, QuizSubmitResponse
from Services.quiz_generator import generate_quiz, QuizGenerationError
from auth import get_current_user

router = APIRouter(prefix="/quiz", tags=["Quiz"])

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
        questions = generate_quiz(str(note.content), topic)
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
        user_id=current_user.user_id,
        note_id=note.note_id
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    # The client only gets question + options — never correct_answer
    return QuizResponse(
        quiz_id=int(new_quiz.quiz_id),          # type: ignore
        topic=str(new_quiz.topic),              # type: ignore
        questions=[MCQQuestionPublic(question=q["question"], options=q["options"]) for q in questions],
        total_questions=len(questions),
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

    answer_key: dict[str, str] = {
        q["question"]: q["correct_answer"]
        for q in quiz.questions                 # type: ignore
    }

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
    for question, correct_answer in answer_key.items():
        user_answer = submitted[question]
        is_correct = user_answer.strip() == correct_answer.strip()
        if is_correct:
            correct_count += 1

        results.append(QuestionResult(
            question=question,
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct
        ))

    total = int(quiz.total_questions)           # type: ignore
    incorrect_count = total - correct_count
    score = round((correct_count / total) * 100, 2)

    # type: ignore silences false Pylance errors on SQLAlchemy assignments
    quiz.correct_answers = correct_count        # type: ignore
    quiz.incorrect_answers = incorrect_count    # type: ignore
    quiz.score_percentage = score               # type: ignore
    quiz.submitted_at = utcnow()       # type: ignore
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
        message=f"Quiz submitted. You scored {score}%"
    )
