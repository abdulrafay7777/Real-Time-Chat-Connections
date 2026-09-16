# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.base import engine, Base
from app.routers import auth, rooms, ws, history


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Real-time Chat API", version="1.0.0", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])
app.include_router(history.router, prefix="/history", tags=["history"])


@app.get("/health")
async def health():
    return {"status": "ok"}