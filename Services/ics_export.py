"""
Exam plan → iCalendar (.ics) file (RFC 5545), written by hand — no extra dependency.

Study sessions are timed events in "floating" local time (no time zone), so
10:00 on the plan is 10:00 wherever the student's calendar is. The exam itself
is an all-day event with a reminder the evening before.
"""
from datetime import datetime, date, timedelta, timezone

KIND_LABELS = {
    "learn": "Learn",
    "practice": "Practice",
    "review": "Quick review",
    "revise": "Revise",
    "quiz": "Quiz yourself",
    "mock": "Mock test",
}
BREAK_MINUTES = 10


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        .replace("\r\n", "\\n").replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Lines longer than 75 octets are split, continuation lines start with a space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not parts else 74
        if len(current) + len(b) > limit:
            parts.append(current.decode("utf-8"))
            current = b""
        current += b
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _local(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def plan_to_ics(
    plan_id: int, exam_name: str, days: list[dict], start_time: str = "18:00",
    include_done: bool = False,
) -> str:
    hour, minute = (int(x) for x in start_time.split(":"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Multimodal AI Study Assistant//Exam Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(f'Study plan: {exam_name}')}",
    ]

    for day in days:
        d = date.fromisoformat(day["date"])
        if day.get("exam"):
            lines += [
                "BEGIN:VEVENT",
                f"UID:plan-{plan_id}-exam@study-assistant",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                f"SUMMARY:{_escape(f'📝 EXAM: {exam_name}')}",
                "TRANSP:TRANSPARENT",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape(f'{exam_name} exam tomorrow — sleep well!')}",
                "TRIGGER:-PT6H",
                "END:VALARM",
                "END:VEVENT",
            ]
            continue

        clock = datetime(d.year, d.month, d.day, hour, minute)
        first = True
        for item in day.get("items", []):
            minutes = int(item.get("minutes", 0))
            if minutes <= 0:
                continue
            start = clock
            end = start + timedelta(minutes=minutes)
            clock = end + timedelta(minutes=BREAK_MINUTES)
            if item.get("done") and not include_done:
                continue
            label = KIND_LABELS.get(item.get("kind", ""), "Study")
            summary = f"{label}: {item['topic']}" if item.get("kind") != "mock" else f"Mock test — {exam_name}"
            lines += [
                "BEGIN:VEVENT",
                f"UID:plan-{plan_id}-{item['id']}@study-assistant",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{_local(start)}",
                f"DTEND:{_local(end)}",
                f"SUMMARY:{_escape(summary)}",
                f"DESCRIPTION:{_escape(f'{minutes} min · {exam_name} study plan')}",
                "CATEGORIES:Study",
            ]
            if first:       # one reminder per study day
                lines += [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{_escape('Study time: ' + summary)}",
                    "TRIGGER:-PT10M",
                    "END:VALARM",
                ]
                first = False
            lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
