# app/services/connection_manager.py

import json
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # room_id -> list of (websocket, username) tuples
        self.rooms: dict[str, list[tuple[WebSocket, str]]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, room_id: str, username: str):
        await websocket.accept()
        self.rooms[room_id].append((websocket, username))

    def disconnect(self, websocket: WebSocket, room_id: str):
        self.rooms[room_id] = [
            (ws, user) for ws, user in self.rooms[room_id]
            if ws != websocket
        ]
        # clean up empty rooms
        if not self.rooms[room_id]:
            del self.rooms[room_id]

    async def broadcast(self, message: dict, room_id: str, exclude: WebSocket = None):
        """Send a message to every connection in the room except the sender."""
        payload = json.dumps(message)
        dead = []

        for ws, username in self.rooms.get(room_id, []):
            if ws == exclude:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                # connection dropped without a clean disconnect
                dead.append((ws, username))

        # clean up dead connections
        for item in dead:
            self.rooms[room_id].remove(item)

    async def broadcast_system(self, text: str, room_id: str):
        """For join/leave announcements — no sender to exclude."""
        message = {
            "type": "system",
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.broadcast(message, room_id)

    def get_online_users(self, room_id: str) -> list[str]:
        return [username for _, username in self.rooms.get(room_id, [])]


# singleton — one instance shared across the entire app
manager = ConnectionManager()