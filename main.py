import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import groq

from auth import router as auth_router
from Routers.lessons import router as lessons_router
from Routers.quiz import router as quiz_router
from Routers.analytics import router as analytics_router
from Routers.tutor import router as tutor_router
from Routers.upload import router as upload_router
from fastapi.middleware.cors import CORSMiddleware
from Routers.admin import router as admin_router
from Routers.learning import router as learning_router
from Routers.viva import router as viva_router
from Routers.flashcards import router as flashcards_router
from Routers.solutions import router as solutions_router
from Routers.planner import router as planner_router
from Routers.maps import router as maps_router
from Routers.classes import router as classes_router

load_dotenv()

# The database schema is managed by Alembic (see migrations/).
# Create / update tables with:   python -m alembic upgrade head

app = FastAPI()

# Comma-separated list in .env, e.g. ALLOWED_ORIGINS=http://localhost:5173,https://myapp.vercel.app
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
app.include_router(learning_router)
app.include_router(viva_router)
app.include_router(flashcards_router)
app.include_router(solutions_router)
app.include_router(planner_router)
app.include_router(maps_router)
app.include_router(classes_router)
