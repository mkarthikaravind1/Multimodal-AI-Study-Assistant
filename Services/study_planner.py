"""
Exam planner.

  syllabus text ──LLM──▶ topics [{unit, topic, size}]          (extract_topics)
  topics + quiz/viva history ──▶ weights (weak topics get more time)   (weigh_topics)
  weights + dates + hours ──▶ day-by-day plan                    (build_schedule)

Only the topic list comes from the model. The schedule itself is plain,
deterministic Python, so it is testable and never invents dates.

Schedule shape (stored in exam_plans.days):
  [{"date": "2026-11-20", "rest": false, "exam": false,
    "items": [{"id": "2026-11-20-1", "topic": "Heaps", "kind": "learn",
               "minutes": 60, "done": false}]}]
  kind: learn | practice | review | revise | quiz | mock
"""
import os
import re
import json
from datetime import date, timedelta
from groq import Groq
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from models import VivaSession
from Services.learning_loop import recent_average, submitted_quizzes_by_topic

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MAX_SYLLABUS_CHARS = 14000
MAX_TOPICS = 40
MAX_TOPIC_CHARS = 120

BLOCK = 15                      # minutes — every session is a multiple of this
MAX_CHUNK = 90                  # longest single sitting on one topic
REVIEW_MINUTES = 15
REVIEW_OFFSETS = (1, 3, 7, 21)  # spaced reviews, in study days after a topic is finished
LEARNING_SHARE = 0.8            # of each learning day; the rest is room for spaced reviews
SIZE_MINUTES = {1: 60, 2: 120, 3: 180}
MAX_SCALE = 2.0                 # with lots of time, spread the work instead of inflating it


class PlanError(Exception):
    """Input that can't be turned into a plan, or unusable model output."""


# ── 1. syllabus → topics ──────────────────────────────────────────────────────

def _clean_name(value) -> str:
    text = " ".join(str(value or "").split())
    text = re.sub(r"^[\-•*\d.)\s]+", "", text)        # list bullets / numbering
    return text[:MAX_TOPIC_CHARS].strip(" .;:,")


def clean_topics(raw) -> list[dict]:
    """Validated [{unit, topic, size}] — de-duplicated, sizes clamped to 1-3."""
    if not isinstance(raw, list):
        return []
    topics, seen = [], set()
    for item in raw:
        if isinstance(item, str):
            item = {"topic": item}
        if not isinstance(item, dict):
            continue
        name = _clean_name(item.get("topic") or item.get("name"))
        if len(name) < 2 or name.lower() in seen:
            continue
        try:
            size = int(item.get("size", 2))
        except (TypeError, ValueError):
            size = 2
        seen.add(name.lower())
        topics.append({
            "unit": _clean_name(item.get("unit"))[:MAX_TOPIC_CHARS],
            "topic": name,
            "size": max(1, min(3, size)),
        })
    return topics[:MAX_TOPICS]


def extract_topics(syllabus_text: str) -> dict:
    """
    Returns {"exam_name": str, "topics": [{unit, topic, size}]}.
    size: 1 = small (about an hour), 2 = medium, 3 = large / hard.
    """
    prompt = f"""
    Below is a course syllabus / exam portion. List the topics a student must study,
    in syllabus order, grouped by unit.

    Rules:
    - One entry per teachable topic (merge tiny sub-points into their topic;
      split a huge unit into its main topics). At most {MAX_TOPICS} topics.
    - "unit": the unit / module / chapter it belongs to ("" if none).
    - "size": how much study it needs — 1 small (about an hour), 2 medium, 3 large or hard.
    - Skip admin text: marks, textbooks, course outcomes, lab lists, reference books.
    - "exam_name": the subject / course name if the syllabus says it, else "".

    Syllabus:
    \"\"\"{syllabus_text[:MAX_SYLLABUS_CHARS]}\"\"\"

    Return JSON exactly like:
    {{"exam_name": "Data Structures", "topics": [{{"unit": "Unit 1: Trees", "topic": "Binary search trees", "size": 2}}]}}
    """
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You turn syllabi into clean study topic lists. Respond with JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2500,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.choices[0].message.content or "")
    except json.JSONDecodeError as e:
        raise PlanError("The AI couldn't read the syllabus. Please try again.") from e
    if not isinstance(data, dict):
        raise PlanError("The AI couldn't read the syllabus. Please try again.")

    topics = clean_topics(data.get("topics"))
    if not topics:
        raise PlanError("No study topics were found in this syllabus. Check the file, or type the topics in.")
    return {"exam_name": _clean_name(data.get("exam_name"))[:200], "topics": topics}


# ── 2. weak topics from the student's own history ─────────────────────────────

_STOPWORDS = {
    "a", "an", "the", "of", "and", "in", "on", "to", "for", "with", "its", "their",
    "introduction", "intro", "basics", "basic", "fundamentals", "concepts", "concept",
    "overview", "part", "unit", "chapter", "notes", "simplified", "fix", "up",
}


def _tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in _STOPWORDS:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]                                      # trees → tree
        out.add(w)
    return out


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb)
    if not overlap:
        return 0.0
    score = overlap / max(len(ta), len(tb))
    if ta <= tb or tb <= ta:
        score = max(score, 0.75)        # "Trees" ↔ "Binary search trees"
    return score


def history_scores(db: Session, user_id: int) -> dict[str, float]:
    """{topic: score %} from recent quizzes (last 3 attempts) and finished vivas."""
    scores: dict[str, list[float]] = {}
    for quizzes in submitted_quizzes_by_topic(db, user_id).values():
        topic = str(quizzes[-1].topic)
        scores.setdefault(topic, []).append(recent_average([float(q.score_percentage) for q in quizzes]))  # type: ignore
    vivas = db.query(VivaSession).filter(
        VivaSession.user_id == user_id, VivaSession.completed_at.isnot(None)
    ).all()
    for v in vivas:
        if v.max_score:
            scores.setdefault(str(v.topic), []).append(100.0 * float(v.total_score or 0) / float(v.max_score))  # type: ignore
    return {t: round(sum(s) / len(s), 1) for t, s in scores.items()}


def status_for(score: float | None) -> tuple[str, float]:
    """(status, time weight)"""
    if score is None:
        return "new", 1.0
    if score < 50:
        return "weak", 2.0
    if score < 70:
        return "weak", 1.6
    if score < 85:
        return "ok", 1.0
    return "strong", 0.6


def weigh_topics(topics: list[dict], scores: dict[str, float]) -> list[dict]:
    """Adds score / matched_topic / status / weight to each topic (copies)."""
    out = []
    for t in topics:
        best, best_sim = None, 0.0
        for name in scores:
            s = similarity(t["topic"], name)
            if s > best_sim:
                best, best_sim = name, s
        score = scores[best] if best is not None and best_sim >= 0.5 else None
        status, weight = status_for(score)
        out.append({
            **t,
            "score": score,
            "matched_topic": best if score is not None else None,
            "status": status,
            "weight": weight,
        })
    return out


# ── 3. the schedule ───────────────────────────────────────────────────────────

def _floor_block(minutes: float) -> int:
    return int(minutes // BLOCK) * BLOCK


def _round_block(minutes: float) -> int:
    return int(round(minutes / BLOCK)) * BLOCK


def build_schedule(
    topics: list[dict],
    start: date,
    exam: date,
    minutes_per_day: int,
    rest_weekdays: list[int] | None = None,
    learned: dict[str, float] | None = None,
) -> tuple[list[dict], dict[str, int]]:
    """
    topics: weighted topics (weigh_topics), in syllabus order.
    rest_weekdays: 0 = Monday … 6 = Sunday — no study on those days.
    learned: {topic: fraction already studied 0-1} — used when re-planning.
    Returns (days, {topic: learning minutes allocated}).
    """
    if exam <= start:
        raise PlanError("The exam date must be after the start date.")
    if not topics:
        raise PlanError("Add at least one topic.")
    rest = set(rest_weekdays or [])
    learned = learned or {}

    all_dates = [start + timedelta(days=i) for i in range((exam - start).days)]
    study_dates = [d for d in all_dates if d.weekday() not in rest]
    if not study_dates:                       # every day is a rest day — ignore the rest days
        study_dates, rest = all_dates, set()

    n = len(study_dates)
    revision_count = 0 if n <= 2 else max(1, min(5, round(n * 0.2)))
    learning_dates = study_dates[: n - revision_count] if n > 2 else []
    revision_dates = study_dates[n - revision_count:] if n > 2 else study_dates

    days = {d: [] for d in study_dates}
    used = {d: 0 for d in study_dates}
    counter = {d: 0 for d in study_dates}

    def add(d: date, topic: str, kind: str, minutes: int) -> None:
        counter[d] += 1
        days[d].append({
            "id": f"{d.isoformat()}-{counter[d]}", "topic": topic, "kind": kind,
            "minutes": int(minutes), "done": False,
        })
        used[d] += minutes

    weights = {t["topic"]: float(t.get("weight", 1.0)) for t in topics}

    # ── learning phase: each topic's time ∝ size × weight, in syllabus order ──
    alloc: dict[str, int] = {}
    finished_at: dict[str, int] = {}
    if learning_dates:
        daily_cap = max(BLOCK, _floor_block(minutes_per_day * LEARNING_SHARE))
        need = {
            t["topic"]: SIZE_MINUTES.get(int(t.get("size", 2)), 120) * weights[t["topic"]]
            * max(0.0, 1.0 - float(learned.get(t["topic"], 0.0)))
            for t in topics
        }
        need = {k: v for k, v in need.items() if v >= BLOCK}
        total_need = sum(need.values())
        if total_need:
            capacity = len(learning_dates) * daily_cap
            scale = min(MAX_SCALE, capacity / total_need)
            alloc = {k: max(BLOCK if scale < 0.5 else 30, _round_block(v * scale)) for k, v in need.items()}
            # spread evenly instead of cramming the first days
            target = min(daily_cap, max(BLOCK, -(-sum(alloc.values()) // len(learning_dates) // BLOCK) * BLOCK))

            day_i = 0
            for t in topics:
                name = t["topic"]
                remaining = alloc.get(name, 0)
                first = True
                while remaining > 0 and day_i < len(learning_dates):
                    d = learning_dates[day_i]
                    room = target - used[d]
                    # don't open a topic with a 15-minute scrap at the end of a day
                    if room < BLOCK or (room < 30 and remaining >= 30):
                        day_i += 1
                        continue
                    chunk = max(BLOCK, _floor_block(min(remaining, MAX_CHUNK, room)))
                    add(d, name, "learn" if first else "practice", chunk)
                    remaining -= chunk
                    first = False
                    finished_at[name] = day_i
                # out of learning days: whatever is left is covered in revision
                if remaining > 0:
                    alloc[name] -= remaining

            # spaced reviews after each topic is finished
            for name, f in finished_at.items():
                for off in REVIEW_OFFSETS:
                    j = f + off
                    if j < len(learning_dates):
                        d = learning_dates[j]
                        if used[d] + REVIEW_MINUTES <= minutes_per_day:
                            add(d, name, "review", REVIEW_MINUTES)

    # ── revision phase: weak topics first and longest; last day = mock test ──
    by_weight = sorted(topics, key=lambda t: -weights[t["topic"]])
    weak = [t["topic"] for t in by_weight if t.get("status") == "weak"]

    mock_day = revision_dates[-1] if len(revision_dates) >= 2 or (n > 2) else None
    plain_revision = [d for d in revision_dates if d != mock_day]

    if plain_revision:
        pool = len(plain_revision) * minutes_per_day
        total_w = sum(weights.values()) or 1.0
        shares = []
        for t in by_weight:
            name = t["topic"]
            share = _round_block(pool * weights[name] / total_w)
            if share >= BLOCK:
                shares.append((name, share))
        di = 0
        for name, share in shares:
            if name in weak and share >= 45:
                parts = [("quiz", 20 if share < 60 else 30), ("revise", None)]
            else:
                parts = [("revise", None)]
            left = share
            for kind, minutes in parts:
                m = minutes if minutes is not None else left
                while m >= BLOCK and di < len(plain_revision):
                    d = plain_revision[di]
                    room = minutes_per_day - used[d]
                    if room < BLOCK:
                        di += 1
                        continue
                    chunk = _floor_block(min(m, room, MAX_CHUNK))
                    add(d, name, kind, chunk)
                    m -= chunk
                    left -= chunk
                if di >= len(plain_revision):
                    break

    if mock_day is not None:
        mock = max(BLOCK, _floor_block(min(180, minutes_per_day * 0.6)))
        add(mock_day, "Full syllabus", "mock", mock)
        for name in (weak or [t["topic"] for t in by_weight])[:3]:
            room = minutes_per_day - used[mock_day]
            if room < BLOCK:
                break
            add(mock_day, name, "revise", _floor_block(min(30, room)))

    out = []
    for d in all_dates:
        out.append({
            "date": d.isoformat(),
            "rest": d not in days,
            "exam": False,
            "items": days.get(d, []),
        })
    out.append({"date": exam.isoformat(), "rest": False, "exam": True, "items": []})
    return out, alloc


def learned_fractions(days: list[dict], alloc: dict[str, int]) -> dict[str, float]:
    """How much of each topic's learning time is ticked off (for re-planning)."""
    done: dict[str, int] = {}
    for day in days:
        for it in day.get("items", []):
            if it.get("done") and it.get("kind") in ("learn", "practice"):
                done[it["topic"]] = done.get(it["topic"], 0) + int(it.get("minutes", 0))
    return {t: min(1.0, done.get(t, 0) / a) for t, a in alloc.items() if a}


def replan(
    old_days: list[dict], topics: list[dict], alloc: dict[str, int], today: date,
    exam: date, minutes_per_day: int, rest_weekdays: list[int],
) -> tuple[list[dict], dict[str, int]]:
    """
    Keeps the past exactly as it was and rebuilds today → exam from what is
    still left to learn. Learning time already ticked off isn't scheduled again.
    """
    learned = learned_fractions(old_days, alloc)
    new_days, new_alloc = build_schedule(topics, today, exam, minutes_per_day, rest_weekdays, learned)
    past = [d for d in old_days if d["date"] < today.isoformat() and not d.get("exam")]
    # remember the original allocation (plus anything new) for later re-plans
    merged_alloc = {**new_alloc, **{k: v for k, v in alloc.items()}}
    return past + new_days, merged_alloc
