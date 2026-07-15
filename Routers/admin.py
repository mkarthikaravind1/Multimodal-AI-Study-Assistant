# routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth import get_current_user
from models import Note, QuizDetail, TutorSession, UploadedMaterial

router = APIRouter(prefix="/admin", tags=["Admin"])

def require_admin(current_user: User = Depends(get_current_user)):
    """Dependency that blocks non-admin users."""
    if current_user.role.value != "admin" if hasattr(current_user.role, 'value') else str(current_user.role) != "admin":
        raise HTTPException(status_code=403,detail="Admin access required")
    return current_user

@router.get("/users")
def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = db.query(User).all()
    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "student_class": u.student_class,
            "role": u.role,
            "registered_date": u.registered_date
            # never return password_hash
        }
        for u in users
    ]

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    
    return {
        "total_users": db.query(User).count(),
        "total_notes": db.query(Note).count(),
        "total_quizzes": db.query(QuizDetail).count(),
        "total_sessions": db.query(TutorSession).count(),
        "total_uploads": db.query(UploadedMaterial).count()
    }