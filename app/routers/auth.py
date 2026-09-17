# app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.db.models import User
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.rate_limiter import auth_limiter

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    request: Request,
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    # rate limit by IP
    client_ip = request.client.host
    if not auth_limiter.is_allowed(client_ip):
        retry = auth_limiter.retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {retry}s",
            headers={"Retry-After": str(retry)}
        )

    # check username taken
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    # check email taken
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password)
    )
    db.add(user)
    await db.flush()   # gets the generated id without full commit
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    # rate limit by IP
    client_ip = request.client.host
    if not auth_limiter.is_allowed(client_ip):
        retry = auth_limiter.retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {retry}s",
            headers={"Retry-After": str(retry)}
        )

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_access_token({"sub": user.id, "username": user.username})
    return TokenResponse(access_token=token)