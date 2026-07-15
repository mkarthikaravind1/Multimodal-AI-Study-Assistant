from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import QuizDetail, User
from schemas import AnalyticsResponse, TopicAverage
from auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])

STRONG_THRESHOLD = 70.0   # >= 70% average = strong topic

@router.get("", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db),  current_user: User = Depends(get_current_user)):

    # Step 1 & 2 — Group by topic, calculate average score
    results = db.query(QuizDetail.topic,func.avg(QuizDetail.score_percentage)
    ).filter(
        QuizDetail.user_id == current_user.user_id
    ).group_by(
        QuizDetail.topic
    ).all()

    # Step 3 — Split into strong/weak based on threshold
    strong = []
    weak = []
    breakdown = []

    for topic, avg_score in results:
        avg_score = round(float(avg_score), 2)   # Decimal → float, round to 2 places

        breakdown.append(TopicAverage(topic=topic, average_score=avg_score))

        if avg_score >= STRONG_THRESHOLD:
            strong.append(topic)
        else:
            weak.append(topic)

    # Step 4 — Return response
    return AnalyticsResponse(
        strong=strong,
        weak=weak,
        topic_breakdown=breakdown
    )