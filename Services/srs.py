"""
Spaced repetition — the SM-2 algorithm (SuperMemo 2), as used by Anki.

Each review is rated with one of four buttons, mapped to SM-2 quality grades:
    again → 1   (forgot)        hard → 3   good → 4   easy → 5

Rules (per SM-2):
  • quality < 3  → the card "lapses": repetitions reset to 0 and it comes back
                   in RELEARN_MINUTES (still today), ease factor unchanged.
  • quality >= 3 → repetitions += 1 and the next interval is
                       1st success: 1 day   2nd success: 6 days
                       after that : previous interval × ease factor
                   then the ease factor is updated:
                       EF' = EF + (0.1 − (5 − q) × (0.08 + (5 − q) × 0.02)),  minimum 1.3
Small, documented tweaks (as in Anki):
  • "easy" on a brand-new card jumps straight to 4 days, and "easy"
    intervals get a ×1.3 bonus — so Easy is always visibly longer than Good.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

RATINGS = {"again": 1, "hard": 3, "good": 4, "easy": 5}
RELEARN_MINUTES = 10
MIN_EASE = 1.3
EASY_BONUS = 1.3
MAX_INTERVAL_DAYS = 365


@dataclass
class CardState:
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0


@dataclass
class Scheduled:
    ease_factor: float
    interval_days: int          # 0 = relearning today
    repetitions: int
    lapses: int
    due_at: datetime


def schedule(state: CardState, rating: str, now: datetime) -> Scheduled:
    if rating not in RATINGS:
        raise ValueError(f"rating must be one of {list(RATINGS)}")
    q = RATINGS[rating]
    ease = float(state.ease_factor)

    if q < 3:
        return Scheduled(
            ease_factor=ease,
            interval_days=0,
            repetitions=0,
            lapses=state.lapses + 1,
            due_at=now + timedelta(minutes=RELEARN_MINUTES),
        )

    repetitions = state.repetitions + 1
    if repetitions == 1:
        interval = 4 if rating == "easy" else 1
    elif repetitions == 2:
        interval = 6
    else:
        interval = round(max(state.interval_days, 1) * ease)
    if rating == "easy" and repetitions > 1:
        interval = round(interval * EASY_BONUS)
    interval = max(1, min(interval, MAX_INTERVAL_DAYS))

    ease = max(MIN_EASE, ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))

    return Scheduled(
        ease_factor=round(ease, 2),
        interval_days=interval,
        repetitions=repetitions,
        lapses=state.lapses,
        due_at=now + timedelta(days=interval),
    )


def describe_delay(delta: timedelta) -> str:
    """timedelta → short label for the review buttons: '10m', '1d', '6d', '3mo', '1.2y'."""
    minutes = delta.total_seconds() / 60
    if minutes < 60:
        return f"{max(1, round(minutes))}m"
    if minutes < 60 * 24:
        return f"{round(minutes / 60)}h"
    days = minutes / (60 * 24)
    if days < 30:
        return f"{round(days)}d"
    if days < 365:
        return f"{round(days / 30)}mo"
    return f"{days / 365:.1f}y"


def previews(state: CardState, now: datetime) -> dict[str, str]:
    """What each button would do, e.g. {'again': '10m', 'hard': '1d', 'good': '1d', 'easy': '4d'}."""
    return {r: describe_delay(schedule(state, r, now).due_at - now) for r in RATINGS}
