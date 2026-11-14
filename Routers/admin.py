# routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, as_utc
from models import User
from auth import get_current_user
from models import Note, QuizDetail, TutorSession, UploadedMaterial, RoleEnum
from schemas import RoleUpdate

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
            "role": getattr(u.role, "value", u.role),
            "registered_date": as_utc(u.registered_date)
            # never return password_hash
        }
        for u in users
    ]

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    
    return {
        "total_users": db.query(User).count(),
        "total_notes": db.query(Note).count(),
        "total_quizzes": db.query(QuizDetail).filter(QuizDetail.submitted_at.isnot(None)).count(),
        "total_sessions": db.query(TutorSession).count(),
        "total_uploads": db.query(UploadedMaterial).count()
    }


@router.patch("/users/{user_id}/role")
def set_role(user_id: int, request: RoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Make a user a teacher, or a student again. Admin accounts are managed with create_admin.py."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if getattr(user.role, "value", str(user.role)) == "admin":
        raise HTTPException(status_code=400, detail="Admin accounts can't be changed here — use create_admin.py --demote.")
    user.role = RoleEnum(request.role)      # type: ignore
    db.commit()
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": request.role,
        "message": f"{user.username} is now a {request.role}. They'll see the change after logging in again.",
    }
