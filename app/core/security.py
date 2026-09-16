import base64
import hashlib
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings


# ── Password helpers ──────────────────────────────────────────

def _pre_hash(password: str) -> bytes:
    """Pre-hash password to bypass bcrypt's 72 byte limit and return as bytes."""
    pre_hashed = base64.b64encode(hashlib.sha256(password.encode('utf-8')).digest()).decode('ascii')
    return pre_hashed.encode('utf-8')

def hash_password(password: str) -> str:
    safe_password_bytes = _pre_hash(password)
    hashed_bytes = bcrypt.hashpw(safe_password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    safe_password_bytes = _pre_hash(plain)
    hashed_bytes = hashed.encode('utf-8')
    try:
        return bcrypt.checkpw(safe_password_bytes, hashed_bytes)
    except ValueError:
        return False


# ── JWT helpers ───────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    """
    Returns the payload dict if valid, None if expired or tampered.
    Never raises — callers check for None.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None