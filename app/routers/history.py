# app/routers/history.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.base import get_db
from app.db.models import Message, Room, RoomMember, User
from app.schemas.message import MessageResponse, HistoryResponse
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/{room_id}", response_model=HistoryResponse)
async def get_history(
    room_id: str,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # check room exists
    result = await db.execute(select(Room).where(Room.id == room_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Room not found")

    # check membership
    result = await db.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == current_user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this room")

    # fetch messages with user info
    result = await db.execute(
        select(Message)
        .options(joinedload(Message.user))
        .where(Message.room_id == room_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()

    return HistoryResponse(
        messages=[
            MessageResponse(
                id=m.id,
                room_id=m.room_id,
                user_id=m.user_id,
                username=m.user.username,
                text=m.text,
                created_at=m.created_at
            )
            for m in reversed(messages)   # oldest first
        ]
    )