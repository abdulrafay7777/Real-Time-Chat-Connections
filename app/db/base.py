# app/db/base.py

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


# Engine — one per application, reused across all requests
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,       # set True temporarily if you want to see SQL queries
    pool_size=10,
    max_overflow=20
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False   # important — explained below
)


# Base class all models inherit from
class Base(DeclarativeBase):
    pass


# Dependency — used in FastAPI route functions
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise