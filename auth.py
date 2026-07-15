#auth.py
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt 
from jose.exceptions import JWTError
from datetime import datetime, timedelta

from database import get_db
from models import User
from schemas import RegisterRequest, LoginRequest, TokenResponse
from dotenv import load_dotenv
import os
from fastapi import status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm    

load_dotenv()
secret_key = os.getenv("SECRET_KEY")

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    if not secret_key:
        raise ValueError("SECRET_KEY missing")
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)

@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if username already exists
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed = pwd_context.hash(request.password)  # hash the password from request

    new_user = User(
    username=request.username,
    password_hash=hashed,
    role="student",
    registered_date=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    return {"msg": "Registered successfully"}

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first() 
    
    if not user or not pwd_context.verify(form_data.password, str(user.password_hash)):
        raise HTTPException(status_code=400, detail="Invalid credentials")
        
    #password_hash_str = str(user.password_hash)
    # if not user or not pwd_context.verify(form_data.password, password_hash_str):
    #     raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependency that extracts and validates the JWT from the Authorization header.
    Returns the User object if valid, raises 401 otherwise.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        # Step 1 — Decode the JWT
        if not secret_key:
            raise ValueError("SECRET_KEY missing")
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub") or ""

        if username is None:
            raise credentials_exception

    except JWTError:
        # Invalid signature, expired token, malformed token, etc.
        raise credentials_exception

    # Step 2 — Look up the user in MySQL
    user = db.query(User).filter(User.username == username).first()

    if user is None:
        raise credentials_exception

    return user

# @router.get("/profile")
# def get_profile(current_user: User = Depends(get_current_user)):
#     return {
#         "username": current_user.username,
#         "student_class": current_user.student_class,
#         "role": current_user.role,
#         "registered_date": current_user.registered_date
#     }