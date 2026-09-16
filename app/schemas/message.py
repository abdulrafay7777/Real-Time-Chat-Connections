# app/schemas/message.py

from pydantic import BaseModel
from datetime import datetime


class MessageResponse(BaseModel):
    id: str
    room_id: str
    user_id: str
    username: str
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    messages: list[MessageResponse]