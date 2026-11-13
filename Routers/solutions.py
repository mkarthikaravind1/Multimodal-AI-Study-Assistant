"""
Handwritten solution checking ("Check my work").

POST   /solutions/check               photo of worked solution → step-by-step marking
POST   /solutions/{id}/recheck        re-mark with the student's corrected transcription
POST   /solutions/{id}/flashcard      save the first mistake as a flashcard
GET    /solutions/history             the user's past checks
GET    /solutions/{id}                one check (review)
GET    /solutions/{id}/image          the original photo
DELETE /solutions/{id}                delete a check and its photo
"""
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, utcnow, as_utc
from models import SolutionCheck, User
from schemas import SolutionCheckOut, SolutionSummary, SolutionRecheckRequest
from Routers import upload as upload_module          # UPLOAD_DIR is read at call time (tests override it)
from Routers.upload import read_upload, MAX_IMAGE_BYTES
from Services.solution_grader import (
    transcribe_solution, grade_solution, SolutionError, MAX_STEPS,
)
from Services.flashcard_service import add_cards

router = APIRouter(prefix="/solutions", tags=["Solutions"])

ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_RECHECKS = 5        # each re-check is another vision call


def _out(check: SolutionCheck, flashcard_added: bool = False) -> SolutionCheckOut:
    result: dict = check.result or {}       # type: ignore
    return SolutionCheckOut(
        check_id=cast(int, check.check_id),
        topic=check.topic,                          # type: ignore
        problem=check.problem,                      # type: ignore
        expected_answer=check.expected_answer,      # type: ignore
        final_answer=check.final_answer,            # type: ignore
        filename=cast(str, check.filename),
        steps=check.steps,                          # type: ignore
        verdict=check.verdict,                      # type: ignore
        score=check.score,                          # type: ignore
        first_error_step=result.get("first_error_step"),
        error_type=result.get("error_type"),
        summary=result.get("summary", ""),
        hint=result.get("hint", ""),
        correct_answer=result.get("correct_answer", ""),
        answer_matches_expected=result.get("answer_matches_expected"),
        rechecks=cast(int, check.rechecks or 0),
        flashcard_added=flashcard_added,
        created_at=as_utc(check.created_at),        # type: ignore
        updated_at=as_utc(check.updated_at),        # type: ignore
    )


def _apply_grading(check: SolutionCheck, grading: dict) -> None:
    check.steps = grading["steps"]                  # type: ignore
    check.verdict = grading["verdict"]              # type: ignore
    check.score = grading["score"]                  # type: ignore
    check.result = {                                # type: ignore
        k: grading[k] for k in (
            "first_error_step", "error_type", "summary", "hint",
            "correct_answer", "answer_matches_expected",
        )
    }


def _get_check(db: Session, check_id: int, user_id: int) -> SolutionCheck:
    check = db.query(SolutionCheck).filter(
        SolutionCheck.check_id == check_id, SolutionCheck.user_id == user_id
    ).first()
    if not check:
        raise HTTPException(status_code=404, detail="Solution check not found")
    return check


def _image_path(check: SolutionCheck):
    if not check.stored_path:
        return None
    root = upload_module.UPLOAD_DIR.resolve()
    path = (root / str(check.stored_path)).resolve()
    if root not in path.parents or not path.exists():
        return None
    return path


def _read_image(check: SolutionCheck) -> bytes:
    path = _image_path(check)
    if path is None:
        raise HTTPException(status_code=404, detail="The original photo is no longer stored.")
    return path.read_bytes()


def _clean_optional(value: str | None, limit: int) -> str:
    return (value or "").strip()[:limit]


@router.post("/check", response_model=SolutionCheckOut)
def check_solution(
    file: UploadFile = File(...),
    problem: str = Form(default="", max_length=2000),
    expected_answer: str = Form(default="", max_length=255),
    topic: str = Form(default="", max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Please upload a JPEG, PNG or WebP photo of your working.")
    image_bytes = read_upload(file, MAX_IMAGE_BYTES, "Photo")
    if mime == "image/jpg":
        mime = "image/jpeg"

    problem = _clean_optional(problem, 2000)
    expected_answer = _clean_optional(expected_answer, 255)
    topic = _clean_optional(topic, 200)

    try:
        reading = transcribe_solution(image_bytes, mime, problem)
        if not reading["legible"]:
            raise HTTPException(
                status_code=422,
                detail="Couldn't read any working in this photo. Retake it in good light, "
                       "hold the camera straight above the page and fill the frame with your working.",
            )
        problem = problem or reading["problem"]
        grading = grade_solution(
            image_bytes, mime, problem, reading["steps"], reading["final_answer"],
            expected_answer, topic,
        )
    except SolutionError as e:
        raise HTTPException(status_code=502, detail=str(e))

    user_id = cast(int, current_user.user_id)
    check = SolutionCheck(
        user_id=user_id,
        topic=topic or None,
        problem=problem or None,
        expected_answer=expected_answer or None,
        final_answer=reading["final_answer"] or None,
        filename=(file.filename or "solution")[:255],
        mime_type=mime,
        rechecks=0,
        created_at=utcnow(),
    )
    _apply_grading(check, grading)
    db.add(check)
    db.flush()      # assigns check_id

    # Keep the photo so the student can review it next to the marking
    stored = upload_module.UPLOAD_DIR / str(user_id) / "solutions" / f"{check.check_id}{ALLOWED_TYPES[mime]}"
    try:
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_bytes(image_bytes)
        check.stored_path = str(stored.relative_to(upload_module.UPLOAD_DIR))   # type: ignore
        db.commit()
    except Exception:
        db.rollback()
        if stored.exists():
            stored.unlink()
        raise

    db.refresh(check)
    return _out(check)


@router.post("/{check_id}/recheck", response_model=SolutionCheckOut)
def recheck_solution(
    check_id: int,
    request: SolutionRecheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check = _get_check(db, check_id, cast(int, current_user.user_id))
    if (check.rechecks or 0) >= MAX_RECHECKS:
        raise HTTPException(status_code=429, detail=f"You can re-check a solution at most {MAX_RECHECKS} times.")
    image_bytes = _read_image(check)

    steps = request.steps[:MAX_STEPS]
    problem = request.problem if request.problem is not None else (check.problem or "")
    final_answer = request.final_answer if request.final_answer is not None else (check.final_answer or "")

    try:
        grading = grade_solution(
            image_bytes, cast(str, check.mime_type), cast(str, problem), steps, cast(str, final_answer),
            cast(str, check.expected_answer or ""), cast(str, check.topic or ""), confirmed=True,
        )
    except SolutionError as e:
        raise HTTPException(status_code=502, detail=str(e))

    check.problem = problem or None                 # type: ignore
    check.final_answer = final_answer or None       # type: ignore
    _apply_grading(check, grading)
    check.rechecks = (check.rechecks or 0) + 1      # type: ignore
    check.updated_at = utcnow()                     # type: ignore
    db.commit()
    db.refresh(check)
    return _out(check)


@router.post("/{check_id}/flashcard", response_model=SolutionCheckOut)
def save_mistake_flashcard(check_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Turns the first mistake into a 'spot the mistake' flashcard."""
    user_id = cast(int, current_user.user_id)
    check = _get_check(db, check_id, user_id)
    result: dict = check.result or {}               # type: ignore
    idx = result.get("first_error_step")
    steps: list[dict] = check.steps or []           # type: ignore
    if idx is None or not (0 <= idx < len(steps)):
        raise HTTPException(status_code=400, detail="This solution has no mistake to save.")

    step = steps[idx]
    problem = (check.problem or "this problem")     # type: ignore
    if len(problem) > 250:
        problem = problem[:247] + "…"
    front = f"Spot the mistake — {problem}\nStep: {step['text']}"
    back_parts = [step.get("comment") or "This step is wrong."]
    if step.get("correction"):
        back_parts.append(f"Correct: {step['correction']}")
    added = add_cards(
        db, user_id, [{"front": front, "back": "\n".join(back_parts)}],
        source="solution", topic=cast(str, check.topic) if check.topic else None,
    )
    db.commit()
    return _out(check, flashcard_added=bool(added))


@router.get("/history", response_model=list[SolutionSummary])
def solution_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    checks = db.query(SolutionCheck).filter(
        SolutionCheck.user_id == current_user.user_id
    ).order_by(SolutionCheck.created_at.desc()).limit(30).all()
    out = []
    for c in checks:
        title = (c.problem or c.filename or "Solution").strip()    # type: ignore
        title = " ".join(title.split())
        out.append(SolutionSummary(
            check_id=c.check_id,                    # type: ignore
            title=title if len(title) <= 80 else title[:77] + "…",
            topic=c.topic,                          # type: ignore
            verdict=c.verdict,                      # type: ignore
            score=c.score,                          # type: ignore
            created_at=as_utc(c.created_at),        # type: ignore
        ))
    return out


@router.get("/{check_id}", response_model=SolutionCheckOut)
def get_solution(check_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _out(_get_check(db, check_id, cast(int, current_user.user_id)))


@router.get("/{check_id}/image")
def get_solution_image(check_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check = _get_check(db, check_id, cast(int, current_user.user_id))
    path = _image_path(check)
    if path is None:
        raise HTTPException(status_code=404, detail="The original photo is no longer stored.")
    return FileResponse(path, media_type=cast(str, check.mime_type))


@router.delete("/{check_id}")
def delete_solution(check_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check = _get_check(db, check_id, cast(int, current_user.user_id))
    path = _image_path(check)
    db.delete(check)
    db.commit()
    if path is not None:
        path.unlink(missing_ok=True)
    return {"message": "Deleted"}
