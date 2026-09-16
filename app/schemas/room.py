# app/schemas/room.py

from pydantic import BaseModel
from datetime import datetime


class RoomCreateRequest(BaseModel):
    name: str
    description: str | None = None


class RoomResponse(BaseModel):
    id: str
    name: str
    description: str | None
    owner_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RoomListResponse(BaseModel):
    rooms: list[RoomResponse]