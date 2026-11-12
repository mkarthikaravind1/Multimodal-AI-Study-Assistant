#auth.py
import os
import time
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock

from fastapi import HTTPException, Depends, APIRouter, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import bcrypt
from jose import jwt
from jose.exceptions import JWTError
from dotenv import load_dotenv

from database import get_db, utcnow
from models import User
from schemas import RegisterRequest, TokenResponse

load_dotenv()
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    # Fail at startup instead of a 500 on the first login
    raise RuntimeError("SECRET_KEY is not set. Add a long random string to your .env file (see .env.example).")

router = APIRouter()
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# ── Simple in-memory login rate limit ───────────────────────────────────────
# Max 5 failed attempts per username per 5 minutes. In-memory is fine for a
# single server process; use Redis if you ever run multiple workers.
MAX_FAILED_LOGINS = 5
FAILED_LOGIN_WINDOW_SECONDS = 5 * 60
_failed_logins: dict[str, deque] = defaultdict(deque)
_failed_logins_lock = Lock()


def _recent_failures(key: str) -> deque:
    attempts = _failed_logins[key]
    cutoff = time.monotonic() - FAILED_LOGIN_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return attempts


# ── Password hashing (bcrypt directly — passlib is unmaintained and crashes
#    with bcrypt >= 4.1). Hashes are the standard $2b$ format, so passwords
#    hashed by the old passlib code still verify. bcrypt only uses the first
#    72 bytes, and bcrypt 5 raises on longer input, so we truncate explicitly.
def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("utf-8"))
    except ValueError:      # malformed hash in the database
        return False


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)   # type: ignore


@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if username already exists
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed = hash_password(request.password)

    new_user = User(
        username=request.username,
        password_hash=hashed,
        role="student",
        registered_date=utcnow()
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Two people registered the same name at the same moment
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already taken")
    return {"msg": "Registered successfully"}


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    key = form_data.username.strip().lower()

    with _failed_logins_lock:
        if len(_recent_failures(key)) >= MAX_FAILED_LOGINS:
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Please wait 5 minutes and try again."
            )

    user = db.query(User).filter(User.username == form_data.username.strip()).first()

    if not user or not verify_password(form_data.password, str(user.password_hash)):
        with _failed_logins_lock:
            _recent_failures(key).append(time.monotonic())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with _failed_logins_lock:
        _failed_logins.pop(key, None)       # successful login clears the counter

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
        # Step 1 — Decode the JWT (also rejects expired tokens)
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])   # type: ignore
    except JWTError:
        # Invalid signature, expired token, malformed token, etc.
        raise credentials_exception

    username = payload.get("sub")
    if not username:
        raise credentials_exception

    # Step 2 — Look up the user in MySQL
    user = db.query(User).filter(User.username == username).first()

    if user is None:
        raise credentials_exception

    return user
