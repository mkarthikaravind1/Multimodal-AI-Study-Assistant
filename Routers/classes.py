"""
Classes: teachers create them, students join with a 6-character code,
teachers assign quizzes and see a weak-topic heatmap for the whole class.

Teacher
  POST   /classes                              create (a join code is generated)
  PATCH  /classes/{id}                         rename / change subject
  POST   /classes/{id}/new-code                replace the join code (old one stops working)
  DELETE /classes/{id}                         delete class, members, assignments (students keep their own quizzes)
  DELETE /classes/{id}/members/{student_id}    remove a student
  POST   /classes/{id}/assignments             assign a quiz (AI notes + questions, generated once)
  DELETE /classes/{id}/assignments/{aid}
  GET    /classes/{id}/heatmap                 students × assignments, weakest topics first
Student
  POST   /classes/join                         join with a code
  POST   /classes/{id}/leave
  POST   /classes/assignments/{aid}/start      own copy of the notes + quiz (resumes if already started)
Both
  GET    /classes                              my classes (teaching or joined)
  GET    /classes/{id}                         one class (teacher: members + class stats; student: own status)

Privacy: the heatmap only uses results of quizzes assigned in the class —
a student's own self-study quizzes stay private.
"""
import re
import secrets
from datetime import timedelta
from typing import cast
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, utcnow, as_utc
from models import Assignment, ClassMember, ClassRoom, QuizDetail, User
from schemas import (
    AssignmentCreate, AssignmentOut, ClassCreate, ClassDetail, ClassSummary, ClassUpdate, HeatCell,
    Heatmap, HeatTopic, JoinRequest, MemberOut, MyAssignmentStatus, QuizResponse, StartAssignmentResponse,
)
from Routers.lessons import normalize_topic, save_note_and_index, youtube_search_links
from Routers.quiz import to_public
from Services.lesson_generator import generate_notes
from Services.quiz_generator import generate_quiz, QuizGenerationError
from Services.language import language_note
from Services.learning_loop import PASS_MARK

router = APIRouter(prefix="/classes", tags=["Classes"])

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"     # no 0/O or 1/I — easy to read out in class
CODE_LENGTH = 6
MAX_CLASSES_PER_TEACHER = 30
MAX_CLASSES_PER_STUDENT = 20


# ── helpers ───────────────────────────────────────────────────────────────────

def role_of(user: User) -> str:
    return getattr(user.role, "value", str(user.role))


def require_teacher(current_user: User = Depends(get_current_user)) -> User:
    if role_of(current_user) != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can do this. Ask an admin to make you a teacher.")
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    if role_of(current_user) != "student":
        raise HTTPException(status_code=403, detail="Only students can join classes and take assignments.")
    return current_user


def new_join_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not db.query(ClassRoom).filter(ClassRoom.join_code == code).first():
            return code
    raise HTTPException(status_code=500, detail="Couldn't make a unique class code. Please try again.")


def normalize_code(code: str) -> str:
    """' abc-23k ' → 'ABC23K' (spaces / dashes people type are ignored)."""
    return re.sub(r"[\s\-_]", "", code).upper()


def _teacher_class(db: Session, class_id: int, teacher: User) -> ClassRoom:
    c = db.query(ClassRoom).filter(ClassRoom.class_id == class_id, ClassRoom.teacher_id == teacher.user_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Class not found")
    return c


def _visible_class(db: Session, class_id: int, user: User) -> tuple[ClassRoom, bool]:
    """(class, is_teacher) — the teacher who owns it, or a student who is a member."""
    c = db.get(ClassRoom, class_id)
    if c is not None:
        if c.teacher_id == user.user_id and role_of(user) == "teacher":
            return c, True
        is_member = db.query(ClassMember).filter(
            ClassMember.class_id == class_id, ClassMember.student_id == user.user_id
        ).first()
        if is_member:
            return c, False
    raise HTTPException(status_code=404, detail="Class not found")


def _attempts(db: Session, assignment_ids: list[int], student_ids: list[int] | None = None) -> dict[tuple[int, int], list[QuizDetail]]:
    """{(student_id, assignment_id): [quizzes oldest first]} — the attempt and its fix-up retests."""
    if not assignment_ids:
        return {}
    q = db.query(QuizDetail).filter(QuizDetail.assignment_id.in_(assignment_ids))
    if student_ids is not None:
        q = q.filter(QuizDetail.user_id.in_(student_ids))
    out: dict[tuple[int, int], list[QuizDetail]] = {}
    for quiz in q.order_by(QuizDetail.attempted_at, QuizDetail.quiz_id).all():
        out.setdefault((cast(int, quiz.user_id), cast(int, quiz.assignment_id)), []).append(quiz)
    return out


def _cell(quizzes: list[QuizDetail]) -> HeatCell:
    submitted = [q for q in quizzes if q.submitted_at is not None]
    if not quizzes:
        return HeatCell(status="not_started", first_score=None, latest_score=None, attempts=0)
    if not submitted:
        return HeatCell(status="in_progress", first_score=None, latest_score=None, attempts=0)
    submitted.sort(key=lambda q: (q.submitted_at, q.quiz_id))     # type: ignore
    return HeatCell(
        status="submitted",
        first_score=float(submitted[0].score_percentage),            # type: ignore
        latest_score=float(submitted[-1].score_percentage),          # type: ignore
        attempts=len(submitted),
    )


def _assignment_out(a: Assignment, **extra) -> AssignmentOut:
    return AssignmentOut(
        assignment_id=cast(int, a.assignment_id),
        title=cast(str, a.title),
        topic=cast(str, a.topic),
        difficulty=cast(str, a.difficulty),
        question_types=a.question_types or [],          # type: ignore
        questions=len(a.questions or []),               # type: ignore
        due_date=a.due_date,                            # type: ignore
        created_at=as_utc(a.created_at),                # type: ignore
        **extra,
    )


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _members(db: Session, class_id: int) -> list[tuple[ClassMember, User]]:
    return db.query(ClassMember, User).join(User, User.user_id == ClassMember.student_id).filter(
        ClassMember.class_id == class_id
    ).order_by(User.username).all()


# ── classes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ClassSummary])
def my_classes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    role = role_of(current_user)
    if role == "teacher":
        classes = db.query(ClassRoom).filter(ClassRoom.teacher_id == current_user.user_id).order_by(ClassRoom.created_at.desc()).all()
    else:
        classes = db.query(ClassRoom).join(ClassMember, ClassMember.class_id == ClassRoom.class_id).filter(
            ClassMember.student_id == current_user.user_id
        ).order_by(ClassMember.joined_at.desc()).all()
    out = []
    for c in classes:
        teacher = db.get(User, c.teacher_id)
        out.append(ClassSummary(
            class_id=cast(int, c.class_id), name=cast(str, c.name), subject=c.subject,          # type: ignore
            join_code=cast(str, c.join_code) if role == "teacher" else None,
            teacher=cast(str, teacher.username) if teacher else "—",
            students=db.query(ClassMember).filter(ClassMember.class_id == c.class_id).count(),
            assignments=db.query(Assignment).filter(Assignment.class_id == c.class_id).count(),
            created_at=as_utc(c.created_at),                                                   # type: ignore
        ))
    return out


@router.post("", response_model=ClassSummary)
def create_class(request: ClassCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    if db.query(ClassRoom).filter(ClassRoom.teacher_id == teacher.user_id).count() >= MAX_CLASSES_PER_TEACHER:
        raise HTTPException(status_code=400, detail=f"You can have up to {MAX_CLASSES_PER_TEACHER} classes.")
    c = ClassRoom(teacher_id=teacher.user_id, name=request.name, subject=request.subject or None,
                  join_code=new_join_code(db), created_at=utcnow())
    db.add(c)
    db.commit()
    db.refresh(c)
    return ClassSummary(class_id=cast(int, c.class_id), name=cast(str, c.name), subject=c.subject,   # type: ignore
                        join_code=cast(str, c.join_code), teacher=cast(str, teacher.username),
                        students=0, assignments=0, created_at=as_utc(c.created_at))               # type: ignore


@router.post("/join", response_model=ClassSummary)
def join_class(request: JoinRequest, db: Session = Depends(get_db), student: User = Depends(require_student)):
    code = normalize_code(request.code)
    c = db.query(ClassRoom).filter(ClassRoom.join_code == code).first()
    if not c:
        raise HTTPException(status_code=404, detail="No class has that code. Check it with your teacher.")
    already = db.query(ClassMember).filter(ClassMember.class_id == c.class_id, ClassMember.student_id == student.user_id).first()
    if not already:
        if db.query(ClassMember).filter(ClassMember.student_id == student.user_id).count() >= MAX_CLASSES_PER_STUDENT:
            raise HTTPException(status_code=400, detail=f"You can be in up to {MAX_CLASSES_PER_STUDENT} classes.")
        db.add(ClassMember(class_id=c.class_id, student_id=student.user_id, joined_at=utcnow()))
        try:
            db.commit()
        except IntegrityError:              # joined twice at the same moment
            db.rollback()
    teacher = db.get(User, c.teacher_id)
    return ClassSummary(
        class_id=cast(int, c.class_id), name=cast(str, c.name), subject=c.subject, join_code=None,    # type: ignore
        teacher=cast(str, teacher.username) if teacher else "—",
        students=db.query(ClassMember).filter(ClassMember.class_id == c.class_id).count(),
        assignments=db.query(Assignment).filter(Assignment.class_id == c.class_id).count(),
        created_at=as_utc(c.created_at),                                                             # type: ignore
    )


@router.get("/{class_id}", response_model=ClassDetail)
def get_class(class_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c, is_teacher = _visible_class(db, class_id, current_user)
    teacher = db.get(User, c.teacher_id)
    assignments = db.query(Assignment).filter(Assignment.class_id == class_id).order_by(Assignment.created_at.desc()).all()
    ids = [cast(int, a.assignment_id) for a in assignments]

    if is_teacher:
        members = _members(db, class_id)
        student_ids = [cast(int, u.user_id) for _, u in members]
        attempts = _attempts(db, ids, student_ids)
        out_assignments = []
        for a in assignments:
            cells = [_cell(attempts.get((sid, cast(int, a.assignment_id)), [])) for sid in student_ids]
            done = [x.latest_score for x in cells if x.status == "submitted" and x.latest_score is not None]
            out_assignments.append(_assignment_out(a, submitted=len(done), average=_average(done)))
        member_out = [MemberOut(student_id=cast(int, u.user_id), username=cast(str, u.username), joined_at=as_utc(m.joined_at))  # type: ignore
                      for m, u in members]
    else:
        attempts = _attempts(db, ids, [cast(int, current_user.user_id)])
        out_assignments = []
        for a in assignments:
            quizzes = attempts.get((cast(int, current_user.user_id), cast(int, a.assignment_id)), [])
            cell = _cell(quizzes)
            first_attempt = next((q for q in quizzes if q.parent_quiz_id is None), None)
            out_assignments.append(_assignment_out(a, mine=MyAssignmentStatus(
                status=cell.status, quiz_id=cast(int, first_attempt.quiz_id) if first_attempt else None,
                first_score=cell.first_score, latest_score=cell.latest_score,
            )))
        member_out = []

    return ClassDetail(
        class_id=cast(int, c.class_id), name=cast(str, c.name), subject=c.subject,     # type: ignore
        join_code=cast(str, c.join_code) if is_teacher else None,
        teacher=cast(str, teacher.username) if teacher else "—",
        is_teacher=is_teacher, members=member_out, assignments=out_assignments,
        created_at=as_utc(c.created_at),                                               # type: ignore
    )


@router.patch("/{class_id}", response_model=ClassDetail)
def update_class(class_id: int, request: ClassUpdate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    c = _teacher_class(db, class_id, teacher)
    if request.name is not None:
        c.name = request.name                    # type: ignore
    if request.subject is not None:
        c.subject = request.subject or None      # type: ignore
    db.commit()
    return get_class(class_id, db, teacher)


@router.post("/{class_id}/new-code", response_model=ClassDetail)
def regenerate_code(class_id: int, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    c = _teacher_class(db, class_id, teacher)
    c.join_code = new_join_code(db)              # type: ignore
    db.commit()
    return get_class(class_id, db, teacher)


@router.delete("/{class_id}")
def delete_class(class_id: int, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    c = _teacher_class(db, class_id, teacher)
    ids = [a.assignment_id for a in db.query(Assignment.assignment_id).filter(Assignment.class_id == class_id).all()]
    if ids:
        # students keep their notes and quiz results — just no longer linked to the class
        db.query(QuizDetail).filter(QuizDetail.assignment_id.in_(ids)).update(
            {QuizDetail.assignment_id: None}, synchronize_session=False)
    db.query(Assignment).filter(Assignment.class_id == class_id).delete(synchronize_session=False)
    db.query(ClassMember).filter(ClassMember.class_id == class_id).delete(synchronize_session=False)
    db.delete(c)
    db.commit()
    return {"message": "Class deleted"}


@router.delete("/{class_id}/members/{student_id}")
def remove_member(class_id: int, student_id: int, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    _teacher_class(db, class_id, teacher)
    n = db.query(ClassMember).filter(ClassMember.class_id == class_id, ClassMember.student_id == student_id).delete()
    if not n:
        raise HTTPException(status_code=404, detail="That student isn't in this class")
    db.commit()
    return {"message": "Student removed"}


@router.post("/{class_id}/leave")
def leave_class(class_id: int, db: Session = Depends(get_db), student: User = Depends(require_student)):
    n = db.query(ClassMember).filter(ClassMember.class_id == class_id, ClassMember.student_id == student.user_id).delete()
    if not n:
        raise HTTPException(status_code=404, detail="Class not found")
    db.commit()
    return {"message": "You left the class"}


# ── assignments ───────────────────────────────────────────────────────────────

@router.post("/{class_id}/assignments", response_model=AssignmentOut)
def create_assignment(class_id: int, request: AssignmentCreate, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    _teacher_class(db, class_id, teacher)
    # a day of slack for time zones (the teacher's "today" may be the server's yesterday)
    if request.due_date is not None and request.due_date < utcnow().date() - timedelta(days=1):
        raise HTTPException(status_code=400, detail="The due date is in the past.")
    topic = normalize_topic(request.topic)

    # notes in the teacher's language setting ("auto": the language of the topic / pasted notes)
    lang = language_note(teacher.preferred_language, request.notes or topic)       # type: ignore
    notes = request.notes or generate_notes(topic, cast(str, teacher.student_class) or "college", language_note=lang)
    if not notes.strip():
        raise HTTPException(status_code=502, detail="The AI returned empty notes. Please try again.")
    try:
        questions = generate_quiz(
            notes, topic, question_types=list(request.question_types),
            difficulty=request.difficulty, count=request.count, language_note=lang,
        )
    except QuizGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))

    a = Assignment(
        class_id=class_id, teacher_id=teacher.user_id,
        title=(request.title or f"Quiz: {topic}")[:200], topic=topic, notes=notes,
        questions=questions, question_types=list(request.question_types), difficulty=request.difficulty,
        due_date=request.due_date, created_at=utcnow(),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _assignment_out(a, submitted=0, average=None)


@router.delete("/{class_id}/assignments/{assignment_id}")
def delete_assignment(class_id: int, assignment_id: int, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    _teacher_class(db, class_id, teacher)
    a = db.query(Assignment).filter(Assignment.assignment_id == assignment_id, Assignment.class_id == class_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.query(QuizDetail).filter(QuizDetail.assignment_id == assignment_id).update(
        {QuizDetail.assignment_id: None}, synchronize_session=False)
    db.delete(a)
    db.commit()
    return {"message": "Assignment deleted"}


@router.post("/assignments/{assignment_id}/start", response_model=StartAssignmentResponse)
def start_assignment(assignment_id: int, db: Session = Depends(get_db), student: User = Depends(require_student)):
    a = db.get(Assignment, assignment_id)
    member = a and db.query(ClassMember).filter(
        ClassMember.class_id == a.class_id, ClassMember.student_id == student.user_id
    ).first()
    if not a or not member:
        raise HTTPException(status_code=404, detail="Assignment not found")

    existing = db.query(QuizDetail).filter(
        QuizDetail.user_id == student.user_id, QuizDetail.assignment_id == assignment_id,
        QuizDetail.parent_quiz_id.is_(None),
    ).first()
    if existing is not None:
        if existing.submitted_at is not None:
            raise HTTPException(status_code=409, detail="You've already submitted this assignment — see your score in the class.")
        quiz, note_id, resumed = existing, cast(int, existing.note_id), True
    else:
        # the student's own copy of the notes (also searchable by their tutor) + quiz
        note = save_note_and_index(
            db, cast(int, student.user_id), f"Class notes: {a.title}"[:255], cast(str, a.notes),
            cast(str, a.topic), youtube_search_links(cast(str, a.topic), cast(str, student.student_class) or "college"),
        )
        quiz = QuizDetail(
            topic=a.topic, questions=a.questions, total_questions=len(a.questions or []),     # type: ignore
            correct_answers=0, incorrect_answers=0, score_percentage=0.00,
            attempted_at=utcnow(), submitted_at=None, difficulty=a.difficulty,
            user_id=student.user_id, note_id=note.note_id, assignment_id=a.assignment_id,
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        note_id, resumed = cast(int, note.note_id), False

    return StartAssignmentResponse(
        quiz=QuizResponse(
            quiz_id=cast(int, quiz.quiz_id), topic=cast(str, quiz.topic),
            questions=[to_public(q) for q in quiz.questions],                 # type: ignore
            total_questions=cast(int, quiz.total_questions), difficulty=cast(str, quiz.difficulty) or "medium",
            message=f"Assignment: {a.title}",
        ),
        note_id=note_id, resumed=resumed,
    )


# ── heatmap ───────────────────────────────────────────────────────────────────

@router.get("/{class_id}/heatmap", response_model=Heatmap)
def class_heatmap(class_id: int, db: Session = Depends(get_db), teacher: User = Depends(require_teacher)):
    _teacher_class(db, class_id, teacher)
    members = _members(db, class_id)
    students = [MemberOut(student_id=cast(int, u.user_id), username=cast(str, u.username), joined_at=as_utc(m.joined_at))   # type: ignore
                for m, u in members]
    student_ids = [s.student_id for s in students]
    assignments = db.query(Assignment).filter(Assignment.class_id == class_id).order_by(Assignment.created_at).all()
    ids = [cast(int, a.assignment_id) for a in assignments]
    attempts = _attempts(db, ids, student_ids)

    cells: dict[str, dict[str, HeatCell]] = {}
    per_assignment: dict[int, list[float]] = {aid: [] for aid in ids}
    student_avg: dict[str, float | None] = {}
    for sid in student_ids:
        row, mine = {}, []
        for aid in ids:
            cell = _cell(attempts.get((sid, aid), []))
            row[str(aid)] = cell
            if cell.latest_score is not None:
                mine.append(cell.latest_score)
                per_assignment[aid].append(cell.latest_score)
        cells[str(sid)] = row
        student_avg[str(sid)] = _average(mine)

    # topics: assignments on the same topic are pooled; weakest first
    by_topic: dict[str, list[Assignment]] = {}
    for a in assignments:
        by_topic.setdefault(cast(str, a.topic).lower(), []).append(a)
    topics = []
    for group in by_topic.values():
        scores = [s for a in group for s in per_assignment[cast(int, a.assignment_id)]]
        weak = 0
        for sid in student_ids:
            latest = [cells[str(sid)][str(a.assignment_id)].latest_score for a in group]
            latest = [x for x in latest if x is not None]
            if latest and sum(latest) / len(latest) < PASS_MARK:
                weak += 1
        topics.append(HeatTopic(
            topic=cast(str, group[-1].topic), assignment_ids=[cast(int, a.assignment_id) for a in group],
            average=_average(scores), submitted=len(scores), weak_students=weak,
        ))
    topics.sort(key=lambda t: (t.average is None, t.average if t.average is not None else 0))

    return Heatmap(
        class_id=class_id, students=students,
        assignments=[_assignment_out(a, submitted=len(per_assignment[cast(int, a.assignment_id)]),
                                     average=_average(per_assignment[cast(int, a.assignment_id)])) for a in assignments],
        cells=cells, student_averages=student_avg, topics=topics,
    )
