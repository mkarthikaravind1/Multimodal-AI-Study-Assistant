from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import Note, QuizDetail, User
from schemas import MCQQuestion, QuizRequest, QuizResponse, QuizSubmitRequest, QuestionResult, QuizSubmitResponse
from Services.quiz_generator import generate_quiz    
from auth import get_current_user

router = APIRouter(prefix="/quiz", tags=["Quiz"])

@router.post("/generate", response_model=QuizResponse)
def generate_quiz_route(request: QuizRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    note = db.query(Note).filter(Note.note_id == request.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    questions = generate_quiz(str(note.content), request.topic)

    # ✓ Build mcq_list FIRST before using it below
    mcq_list = [
        MCQQuestion(
            question=q["question"],
            options=q["options"],
            correct_answer=q["correct_answer"]
        )
        for q in questions
    ]

    new_quiz = QuizDetail(
        topic=request.topic,
        questions=[q.model_dump() for q in mcq_list],  # use model_dump() not dict()
        total_questions=len(questions),
        correct_answers=0,
        incorrect_answers=0,
        score_percentage=0.00,
        attempted_at=datetime.utcnow(),
        user_id=current_user.user_id,
        note_id=request.note_id
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    return QuizResponse(
        quiz_id=int(new_quiz.quiz_id),          # type: ignore
        topic=request.topic,
        questions=mcq_list,
        total_questions=len(mcq_list),
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

    answer_key: dict[str,str] = {
        q["question"]: q["correct_answer"]
        for q in quiz.questions                 # type: ignore
    }

    results = []
    correct_count = 0

    for submitted in request.answers:
        correct_answer = answer_key.get(submitted.question)

        if correct_answer is None:
            raise HTTPException(
                status_code=400,
                detail=f"Question not found: {submitted.question}"
            )

        is_correct = submitted.user_answer.strip() == correct_answer.strip()
        if is_correct:
            correct_count += 1

        results.append(QuestionResult(
            question=submitted.question,
            user_answer=submitted.user_answer,
            correct_answer=str(correct_answer),
            is_correct=is_correct
        ))

    if len(request.answers)==0:
        raise HTTPException(status_code=404,detail="No answer found")
    
    incorrect_count = len(request.answers) - correct_count
    score = round((correct_count / len(request.answers)) * 100, 2)

    # type: ignore silences false Pylance errors on SQLAlchemy assignments
    quiz.correct_answers = correct_count        # type: ignore
    quiz.incorrect_answers = incorrect_count    # type: ignore
    quiz.score_percentage = score               # type: ignore
    db.commit()
    db.refresh(quiz)

    return QuizSubmitResponse(
        quiz_id=int(quiz.quiz_id),              # type: ignore
        topic=str(quiz.topic),                  # type: ignore
        total_questions=int(quiz.total_questions), # type: ignore
        correct_answers=correct_count,
        incorrect_answers=incorrect_count,
        score_percentage=score,
        results=results,
        message=f"Quiz submitted. You scored {score}%"
    )

