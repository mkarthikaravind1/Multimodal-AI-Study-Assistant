from fastapi import FastAPI
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

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React's default Vite port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.include_router(auth_router)
app.include_router(lessons_router)
app.include_router(quiz_router)
app.include_router(analytics_router)
app.include_router(tutor_router)
app.include_router(upload_router)
app.include_router(admin_router)