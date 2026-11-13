"""
Exam planner.

POST   /planner/extract                    syllabus PDF / text → topics (with weak-topic info), nothing saved
POST   /planner/plans                      topics + exam date + hours → day-by-day plan
GET    /planner/plans                      the user's plans
GET    /planner/plans/{id}                 one plan
PATCH  /planner/plans/{id}/items/{item}    tick a session done / not done
POST   /planner/plans/{id}/replan          fell behind? rebuild from today (past + ticks are kept)
GET    /planner/plans/{id}/ics             calendar file (.ics) for Google / Outlook / Apple Calendar
DELETE /planner/plans/{id}
"""
import re
from datetime import date, timedelta
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from auth import get_current_user
from database import get_db, utcnow, as_utc
from models import ExamPlan, User
from schemas import (
    SyllabusExtractResponse, PlanTopicOut, PlanCreate, PlanOut, PlanSummary, PlanProgress,
    PlanItemUpdate, ReplanRequest,
)
from Routers.upload import read_upload, extract_pdf_pages, MAX_PDF_BYTES
from Services.study_planner import (
    extract_topics, weigh_topics, history_scores, build_schedule, replan, PlanError,
)
from Services.ics_export import plan_to_ics

router = APIRouter(prefix="/planner", tags=["Exam planner"])

MAX_SYLLABUS_TEXT = 20000
MAX_DAYS_AHEAD = 366
MAX_PLANS = 20


# ── helpers ───────────────────────────────────────────────────────────────────

def _progress(days: list[dict]) -> PlanProgress:
    items = [it for d in days for it in d.get("items", [])]
    return PlanProgress(
        done_minutes=sum(it["minutes"] for it in items if it.get("done")),
        total_minutes=sum(it["minutes"] for it in items),
        done_items=sum(1 for it in items if it.get("done")),
        total_items=len(items),
    )


def _out(plan: ExamPlan) -> PlanOut:
    days: list[dict] = plan.days        # type: ignore
    return PlanOut(
        plan_id=cast(int, plan.plan_id),
        exam_name=cast(str, plan.exam_name),
        exam_date=plan.exam_date,                   # type: ignore
        start_date=plan.start_date,                 # type: ignore
        minutes_per_day=cast(int, plan.minutes_per_day),
        rest_days=plan.rest_days or [],             # type: ignore
        topics=plan.topics,                         # type: ignore
        days=days,                                  # type: ignore
        syllabus_filename=plan.syllabus_filename,   # type: ignore
        progress=_progress(days),
        created_at=as_utc(plan.created_at),         # type: ignore
        updated_at=as_utc(plan.updated_at),         # type: ignore
    )


def _get_plan(db: Session, plan_id: int, user_id: int) -> ExamPlan:
    plan = db.query(ExamPlan).filter(ExamPlan.plan_id == plan_id, ExamPlan.user_id == user_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


def _check_today(today: date) -> None:
    """The client sends its local date; allow a day either way for time zones."""
    server = utcnow().date()
    if abs((today - server).days) > 1:
        raise HTTPException(status_code=400, detail="Your device's date looks wrong. Check it and try again.")


def _with_minutes(topics: list[dict], alloc: dict[str, int]) -> list[dict]:
    return [{**t, "minutes": int(alloc.get(t["topic"], 0))} for t in topics]


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/extract", response_model=SyllabusExtractResponse)
def extract_syllabus(
    file: UploadFile | None = File(default=None),
    text: str = Form(default="", max_length=MAX_SYLLABUS_TEXT),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename = None
    if file is not None and file.filename:
        filename = file.filename
        lower = filename.lower()
        if lower.endswith(".pdf") or file.content_type == "application/pdf":
            syllabus = "\n".join(extract_pdf_pages(read_upload(file, MAX_PDF_BYTES, "Syllabus")))
        elif lower.endswith(".txt") or file.content_type == "text/plain":
            syllabus = read_upload(file, MAX_SYLLABUS_TEXT * 4, "Syllabus").decode("utf-8", errors="replace")
        else:
            raise HTTPException(status_code=400, detail="Upload the syllabus as a PDF or .txt file, or paste it.")
    else:
        syllabus = text
    if len(syllabus.strip()) < 20:
        raise HTTPException(status_code=400, detail="Upload a syllabus PDF or paste the syllabus text (at least a few topics).")

    try:
        extracted = extract_topics(syllabus)
    except PlanError as e:
        raise HTTPException(status_code=502, detail=str(e))

    weighted = weigh_topics(extracted["topics"], history_scores(db, cast(int, current_user.user_id)))
    return SyllabusExtractResponse(
        exam_name=extracted["exam_name"],
        topics=[PlanTopicOut(**t) for t in weighted],
        syllabus_filename=filename,
    )


@router.post("/plans", response_model=PlanOut)
def create_plan(request: PlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = cast(int, current_user.user_id)
    _check_today(request.start_date)
    if request.exam_date <= request.start_date:
        raise HTTPException(status_code=400, detail="The exam date must be after today.")
    if (request.exam_date - request.start_date).days > MAX_DAYS_AHEAD:
        raise HTTPException(status_code=400, detail="Plans can cover at most one year.")
    if db.query(ExamPlan).filter(ExamPlan.user_id == user_id).count() >= MAX_PLANS:
        raise HTTPException(status_code=400, detail=f"You can keep up to {MAX_PLANS} plans. Delete an old one first.")

    # duplicate topic names would share one time budget — keep the first
    seen, topics = set(), []
    for t in request.topics:
        if t.topic.lower() not in seen:
            seen.add(t.topic.lower())
            topics.append(t.model_dump())

    weighted = weigh_topics(topics, history_scores(db, user_id))
    rest = sorted(set(request.rest_days))
    try:
        days, alloc = build_schedule(weighted, request.start_date, request.exam_date, request.minutes_per_day, rest)
    except PlanError as e:
        raise HTTPException(status_code=400, detail=str(e))

    plan = ExamPlan(
        user_id=user_id,
        exam_name=request.exam_name,
        exam_date=request.exam_date,
        start_date=request.start_date,
        minutes_per_day=request.minutes_per_day,
        rest_days=rest,
        topics=_with_minutes(weighted, alloc),
        days=days,
        syllabus_filename=request.syllabus_filename,
        created_at=utcnow(),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _out(plan)


@router.get("/plans", response_model=list[PlanSummary])
def list_plans(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plans = db.query(ExamPlan).filter(
        ExamPlan.user_id == current_user.user_id
    ).order_by(ExamPlan.exam_date, ExamPlan.plan_id).all()
    return [
        PlanSummary(
            plan_id=p.plan_id,                      # type: ignore
            exam_name=p.exam_name,                  # type: ignore
            exam_date=p.exam_date,                  # type: ignore
            topics=len(p.topics or []),             # type: ignore
            progress=_progress(p.days or []),       # type: ignore
            created_at=as_utc(p.created_at),        # type: ignore
        )
        for p in plans
    ]


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _out(_get_plan(db, plan_id, cast(int, current_user.user_id)))


@router.patch("/plans/{plan_id}/items/{item_id}", response_model=PlanOut)
def update_item(
    plan_id: int, item_id: str, request: PlanItemUpdate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    plan = _get_plan(db, plan_id, cast(int, current_user.user_id))
    days = [{**d, "items": [dict(it) for it in d.get("items", [])]} for d in plan.days]   # type: ignore
    item = next((it for d in days for it in d["items"] if it["id"] == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Session not found in this plan")
    item["done"] = request.done
    plan.days = days                                # type: ignore
    flag_modified(plan, "days")
    plan.updated_at = utcnow()                      # type: ignore
    db.commit()
    db.refresh(plan)
    return _out(plan)


@router.post("/plans/{plan_id}/replan", response_model=PlanOut)
def replan_plan(plan_id: int, request: ReplanRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = cast(int, current_user.user_id)
    plan = _get_plan(db, plan_id, user_id)
    _check_today(request.today)
    if request.today >= plan.exam_date:             # type: ignore
        raise HTTPException(status_code=400, detail="The exam day has arrived — there's nothing left to re-plan. Good luck!")

    topics: list[dict] = plan.topics                # type: ignore
    alloc = {t["topic"]: int(t.get("minutes", 0)) for t in topics}
    # weak/strong may have changed since the plan was made — re-weigh with the latest scores
    base = [{"unit": t.get("unit", ""), "topic": t["topic"], "size": t.get("size", 2)} for t in topics]
    weighted = weigh_topics(base, history_scores(db, user_id))
    try:
        days, new_alloc = replan(
            plan.days, weighted, alloc, request.today, plan.exam_date,     # type: ignore
            cast(int, plan.minutes_per_day), plan.rest_days or [],         # type: ignore
        )
    except PlanError as e:
        raise HTTPException(status_code=400, detail=str(e))

    plan.days = days                                # type: ignore
    plan.topics = _with_minutes(weighted, new_alloc)    # type: ignore
    flag_modified(plan, "days")
    flag_modified(plan, "topics")
    plan.updated_at = utcnow()                      # type: ignore
    db.commit()
    db.refresh(plan)
    return _out(plan)


@router.get("/plans/{plan_id}/ics")
def export_ics(
    plan_id: int,
    start_time: str = Query(default="18:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = _get_plan(db, plan_id, cast(int, current_user.user_id))
    ics = plan_to_ics(cast(int, plan.plan_id), cast(str, plan.exam_name), plan.days, start_time)   # type: ignore
    slug = re.sub(r"[^A-Za-z0-9]+", "-", cast(str, plan.exam_name)).strip("-")[:40] or "exam"
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="study-plan-{slug}.ics"'},
    )


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plan = _get_plan(db, plan_id, cast(int, current_user.user_id))
    db.delete(plan)
    db.commit()
    return {"message": "Plan deleted"}
