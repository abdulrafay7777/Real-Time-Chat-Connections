# app/routers/ws.py

import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db, AsyncSessionLocal
from app.db.models import Room, RoomMember, Message
from app.core.security import decode_token
from app.services.connection_manager import manager

router = APIRouter()


async def get_room_or_close(websocket: WebSocket, room_id: str) -> Room | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Room).where(Room.id == room_id))
        return result.scalar_one_or_none()


async def is_member(user_id: str, room_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RoomMember).where(
                RoomMember.room_id == room_id,
                RoomMember.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None


async def save_message(user_id: str, room_id: str, text: str) -> Message:
    async with AsyncSessionLocal() as db:
        msg = Message(room_id=room_id, user_id=user_id, text=text)
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg


@router.websocket("/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
):
    # ── Step 1: verify JWT from query param ──────────────────
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008)
        return

    user_id: str = payload.get("sub")
    username: str = payload.get("username")

    # ── Step 2: verify room exists ───────────────────────────
    room = await get_room_or_close(websocket, room_id)
    if not room:
        await websocket.close(code=1008)
        return

    # ── Step 3: verify user is a member ─────────────────────
    if not await is_member(user_id, room_id):
        await websocket.close(code=1008)
        return

    # ── Step 4: accept + announce ────────────────────────────
    await manager.connect(websocket, room_id, username)
    await manager.broadcast_system(
        f"{username} joined the room",
        room_id
    )

    # ── Step 5: send current online users to new connection ──
    await websocket.send_text(json.dumps({
        "type": "presence",
        "online_users": manager.get_online_users(room_id)
    }))

    # ── Step 6: message loop ─────────────────────────────────
    try:
        while True:
            data = await websocket.receive_text()

            # rate limit: max 200 chars per message
            if len(data) > 200:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "text": "Message too long (max 200 chars)"
                }))
                continue

            # persist
            msg = await save_message(user_id, room_id, data)

            # build outgoing payload
            outgoing = {
                "type": "message",
                "id": msg.id,
                "user_id": user_id,
                "username": username,
                "text": data,
                "room_id": room_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # send back to sender (confirmation)
            await websocket.send_text(json.dumps(outgoing))

            # broadcast to everyone else
            await manager.broadcast(outgoing, room_id, exclude=websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        await manager.broadcast_system(
            f"{username} left the room",
            room_id
        )