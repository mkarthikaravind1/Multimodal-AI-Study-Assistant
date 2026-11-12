"""
Viva / oral-exam mode.

POST /viva/start              — new viva on one of the user's lessons
POST /viva/{viva_id}/answer   — grade the answer to the CURRENT question
GET  /viva/history            — the user's past vivas
GET  /viva/{viva_id}          — full state (resume or review)

The server decides which question is being answered (the first unanswered
one), so a question can't be answered twice or out of order.
"""
from typing import cast
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from auth import get_current_user
from database import get_db, utcnow, as_utc
from models import Note, User, VivaSession
from schemas import (
    VivaStartRequest, VivaAnswerRequest, VivaAnswerResponse, VivaGradedQuestion,
    VivaState, VivaSummary,
)
from Services.viva_service import generate_viva_questions, grade_answer, VivaError

router = APIRouter(prefix="/viva", tags=["Viva"])

POINTS_PER_QUESTION = 10


def _topic_from_title(title: str) -> str:
    for prefix in ("Notes on ", "Simplified Notes: ", "Fix-up Notes: "):
        if title.startswith(prefix):
            return title[len(prefix):].split(" (round")[0]
    return title


def _graded(q: dict) -> VivaGradedQuestion:
    return VivaGradedQuestion(
        question=q["question"], answer=q["answer"], score=q["score"],
        feedback=q["feedback"], ideal_answer=q["ideal_answer"], missed_points=q["missed_points"],
    )


def _state(viva: VivaSession) -> VivaState:
    questions: list[dict] = viva.questions      # type: ignore
    graded = [q for q in questions if q.get("score") is not None]
    current = next((i for i, q in enumerate(questions) if q.get("score") is None), None)
    return VivaState(
        viva_id=cast(int, viva.viva_id),
        note_id=cast(int, viva.note_id),
        topic=cast(str, viva.topic),
        total_questions=len(questions),
        graded=[_graded(q) for q in graded],
        current_index=current,
        # key_points stay server-side — only the question text is sent
        current_question=questions[current]["question"] if current is not None else None,
        finished=current is None,
        total_score=viva.total_score,           # type: ignore
        max_score=cast(int, viva.max_score),
        started_at=as_utc(viva.started_at),     # type: ignore
        completed_at=as_utc(viva.completed_at), # type: ignore
    )


def _get_viva(db: Session, viva_id: int, user_id: int) -> VivaSession:
    viva = db.query(VivaSession).filter(
        VivaSession.viva_id == viva_id, VivaSession.user_id == user_id
    ).first()
    if not viva:
        raise HTTPException(status_code=404, detail="Viva not found")
    return viva


@router.post("/start", response_model=VivaState)
def start_viva(request: VivaStartRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    note = db.query(Note).filter(
        Note.note_id == request.note_id, Note.user_id == current_user.user_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Lesson not found")

    topic = _topic_from_title(cast(str, note.title))
    try:
        questions = generate_viva_questions(cast(str, note.content), topic, request.num_questions)
    except VivaError as e:
        raise HTTPException(status_code=502, detail=str(e))

    viva = VivaSession(
        user_id=current_user.user_id,
        note_id=note.note_id,
        topic=topic,
        questions=[
            {"question": q["question"], "key_points": q["key_points"], "answer": None,
             "score": None, "feedback": None, "ideal_answer": None, "missed_points": []}
            for q in questions
        ],
        max_score=len(questions) * POINTS_PER_QUESTION,
        started_at=utcnow(),
    )
    db.add(viva)
    db.commit()
    db.refresh(viva)
    return _state(viva)


@router.post("/{viva_id}/answer", response_model=VivaAnswerResponse)
def answer_question(viva_id: int, request: VivaAnswerRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    viva = _get_viva(db, viva_id, cast(int, current_user.user_id))
    questions = [dict(q) for q in viva.questions]       # type: ignore  — copy, then reassign

    index = next((i for i, q in enumerate(questions) if q.get("score") is None), None)
    if index is None:
        raise HTTPException(status_code=409, detail="This viva is already finished.")

    answer = request.answer.strip()
    if len(answer) < 3:
        raise HTTPException(status_code=400, detail="Please say or type an answer first.")

    note = db.get(Note, viva.note_id)
    try:
        grading = grade_answer(
            questions[index]["question"], questions[index].get("key_points", []),
            answer, cast(str, note.content) if note else "",
        )
    except VivaError as e:
        raise HTTPException(status_code=502, detail=str(e))

    questions[index].update(answer=answer, **grading)
    viva.questions = questions                          # type: ignore
    flag_modified(viva, "questions")

    if all(q.get("score") is not None for q in questions):
        viva.total_score = sum(q["score"] for q in questions)   # type: ignore
        viva.completed_at = utcnow()                             # type: ignore

    db.commit()
    db.refresh(viva)
    return VivaAnswerResponse(result=_graded(questions[index]), question_index=index, state=_state(viva))


@router.get("/history", response_model=list[VivaSummary])
def viva_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    vivas = db.query(VivaSession).filter(
        VivaSession.user_id == current_user.user_id
    ).order_by(VivaSession.started_at.desc()).limit(20).all()
    return [
        VivaSummary(
            viva_id=v.viva_id,                                                   # type: ignore
            topic=v.topic,                                                       # type: ignore
            answered=sum(1 for q in v.questions if q.get("score") is not None),  # type: ignore
            total_questions=len(v.questions),                                    # type: ignore
            total_score=v.total_score,                                           # type: ignore
            max_score=v.max_score,                                               # type: ignore
            finished=v.completed_at is not None,
            started_at=as_utc(v.started_at),                                     # type: ignore
        )
        for v in vivas
    ]


@router.get("/{viva_id}", response_model=VivaState)
def get_viva(viva_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _state(_get_viva(db, viva_id, cast(int, current_user.user_id)))
