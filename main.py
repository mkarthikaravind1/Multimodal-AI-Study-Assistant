from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
import groq

from database import engine, Base
from auth import router as auth_router
from Routers.lessons import router as lessons_router
import models  # ensures models are registered with Base
from Routers.quiz import router as quiz_router
from Routers.analytics import router as analytics_router
from Routers.tutor import router as tutor_router
from Routers.upload import router as upload_router
from fastapi.middleware.cors import CORSMiddleware
from Routers.admin import router as admin_router

# Creates tables in MySQL if they don't exist yet
Base.metadata.create_all(bind=engine)


def _ensure_quiz_submitted_at_column():
    """
    create_all() never adds columns to tables that already exist.
    Adds quiz_details.submitted_at once, and marks old quizzes that were
    actually answered as submitted so their scores still count in analytics.
    """
    columns = {c["name"] for c in inspect(engine).get_columns("quiz_details")}
    if "submitted_at" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE quiz_details ADD COLUMN submitted_at DATETIME NULL"))
        conn.execute(text(
            "UPDATE quiz_details SET submitted_at = attempted_at "
            "WHERE correct_answers + incorrect_answers > 0"
        ))


_ensure_quiz_submitted_at_column()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React's default Vite port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Any Groq failure (rate limit, timeout, outage) becomes a clear error
# instead of a raw 500 with a stack trace.
@app.exception_handler(groq.RateLimitError)
async def groq_rate_limit_handler(request: Request, exc: groq.RateLimitError):
    return JSONResponse(
        status_code=429,
        content={"detail": "The AI service is busy (rate limit reached). Please wait a moment and try again."},
    )


@app.exception_handler(groq.APIError)
async def groq_error_handler(request: Request, exc: groq.APIError):
    print(f"[Groq error] {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=502,
        content={"detail": "The AI service failed to respond. Please try again."},
    )


app.include_router(auth_router)
app.include_router(lessons_router)
app.include_router(quiz_router)
app.include_router(analytics_router)
app.include_router(tutor_router)
app.include_router(upload_router)
app.include_router(admin_router)
