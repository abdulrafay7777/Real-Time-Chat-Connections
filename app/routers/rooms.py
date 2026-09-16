# app/routers/rooms.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.db.models import Room, RoomMember
from app.schemas.room import RoomCreateRequest, RoomResponse, RoomListResponse
from app.dependencies import get_current_user
from app.db.models import User

router = APIRouter()


@router.post("/", response_model=RoomResponse, status_code=201)
async def create_room(
    payload: RoomCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # check room name taken
    result = await db.execute(select(Room).where(Room.name == payload.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Room name already exists")

    room = Room(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id
    )
    db.add(room)
    await db.flush()

    # creator automatically becomes a member
    member = RoomMember(room_id=room.id, user_id=current_user.id)
    db.add(member)

    return room


@router.post("/{room_id}/join", status_code=200)
async def join_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # check room exists
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # check already a member
    result = await db.execute(
        select(RoomMember).where(
            RoomMember.room_id == room_id,
            RoomMember.user_id == current_user.id
        )
    )
    if result.scalar_one_or_none():
        return {"detail": "Already a member"}

    member = RoomMember(room_id=room_id, user_id=current_user.id)
    db.add(member)
    return {"detail": "Joined successfully"}


@router.get("/", response_model=RoomListResponse)
async def list_rooms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room))
    rooms = result.scalars().all()
    return RoomListResponse(rooms=rooms)


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(room_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room