from typing import cast
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import AnalyticsResponse, TopicAverage
from auth import get_current_user
from Services.learning_loop import PASS_MARK, recent_average, submitted_quizzes_by_topic

router = APIRouter(prefix="/analytics", tags=["Analytics"])

STRONG_THRESHOLD = PASS_MARK   # >= 70% recent average = strong topic

@router.get("", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db),  current_user: User = Depends(get_current_user)):
    """
    Strong / weak topics based on the average of each topic's LAST 3 submitted
    quizzes (case-insensitive topic grouping). Using recent attempts — not the
    all-time average — lets a topic turn strong once the student recovers.
    """
    strong = []
    weak = []
    breakdown = []

    for quizzes in submitted_quizzes_by_topic(db, cast(int, current_user.user_id)).values():
        topic = cast(str, quizzes[-1].topic)                       # latest spelling of the topic
        avg_score = recent_average([float(q.score_percentage) for q in quizzes])   # type: ignore

        breakdown.append(TopicAverage(topic=topic, average_score=avg_score))
        (strong if avg_score >= STRONG_THRESHOLD else weak).append(topic)

    return AnalyticsResponse(
        strong=strong,
        weak=weak,
        topic_breakdown=breakdown
    )
