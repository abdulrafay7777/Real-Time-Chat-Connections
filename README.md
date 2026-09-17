# LiveChat — Real-time Chat API

A production-structured real-time messaging backend built with FastAPI and WebSockets. Messages are delivered instantly to all connected clients in a room, persisted to PostgreSQL, and protected by JWT authentication and rate limiting.

Built as a portfolio project to demonstrate async Python, WebSocket protocol, stateful connection management, and layered backend architecture.

---

## Why this exists

HTTP is request-response — the client asks, the server answers, connection closes. For a chat application that means either polling (thousands of wasted requests per minute) or long-polling (constantly recreating connections). Neither scales cleanly.

WebSockets solve this by upgrading the initial HTTP request into a persistent, full-duplex connection. The server can push data the moment it arrives — no polling, no reconnection overhead, millisecond latency.

This project implements that pattern end-to-end: authentication, room management, real-time delivery, message persistence, presence tracking, and abuse prevention.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Clients                         │
│         Browser A          Browser B                │
│       (Room: general)    (Room: general)            │
└────────────┬─────────────────────┬──────────────────┘
             │  ws:// + JWT token  │
             ▼                     ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI  (single Uvicorn worker)        │
│                                                     │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────┐ │
│  │   Routers   │  │ ConnectionManager│  │Services│ │
│  │ auth·rooms  │  │ rooms: dict of   │  │ auth   │ │
│  │ ws·history  │  │ active WebSocket  │  │ room   │ │
│  └─────────────┘  │ connections      │  │message │ │
│                   └──────────────────┘  └────────┘ │
│                                                     │
│         Pydantic schemas · SQLAlchemy models        │
│              JWT security · DB session              │
└───────────────────────────┬─────────────────────────┘
                            │ async ORM
                            ▼
┌─────────────────────────────────────────────────────┐
│                     PostgreSQL                      │
│                                                     │
│    users      rooms     room_members    messages    │
│  id·email·  id·name·   room_id·        id·room·    │
│  hash·user  owner·desc  user_id        user·text   │
└─────────────────────────────────────────────────────┘
```

### How a message travels

1. Client sends text over an open WebSocket connection
2. FastAPI receives it in the async message loop
3. Rate limiter checks the user hasn't exceeded 20 messages/60s
4. Message is persisted to PostgreSQL
5. `ConnectionManager` broadcasts to every other connection in the same room
6. All recipients receive the message in milliseconds

The `ConnectionManager` is an in-memory singleton — a dictionary mapping room IDs to lists of active WebSocket objects. Because the app runs as a single Uvicorn worker, all connections share the same memory space and the manager can broadcast directly without any external message broker.

---

## Tech stack

| Technology | Role | Why |
|---|---|---|
| FastAPI | Web framework | Native async support, automatic OpenAPI docs, clean dependency injection |
| WebSockets | Real-time transport | Persistent connection allows server push — eliminates polling |
| PostgreSQL | Primary database | ACID compliance, reliable persistence for message history |
| SQLAlchemy (async) | ORM | Type-safe queries, async session management, clean model definitions |
| asyncpg | PostgreSQL driver | Fully async, significantly faster than psycopg2 for concurrent workloads |
| python-jose | JWT handling | Industry-standard token creation and verification |
| passlib + bcrypt | Password hashing | bcrypt's adaptive cost factor makes brute-force attacks expensive |
| Pydantic | Data validation | Automatic request validation and response serialization |
| Pydantic-settings | Config management | Typed environment variable loading with early failure on missing config |

---

## Project structure

```
realtime-chat-api/
├── app/
│   ├── main.py                      # App entry point, lifespan, router registration
│   ├── dependencies.py              # Shared FastAPI dependencies (get_current_user)
│   ├── core/
│   │   ├── config.py                # Settings loaded from .env via pydantic-settings
│   │   └── security.py              # JWT encode/decode, password hashing
│   ├── db/
│   │   ├── base.py                  # Async engine, session factory, Base class
│   │   └── models.py                # SQLAlchemy models: User, Room, RoomMember, Message
│   ├── routers/
│   │   ├── auth.py                  # POST /auth/register, POST /auth/login
│   │   ├── rooms.py                 # Room CRUD and membership
│   │   ├── ws.py                    # WebSocket endpoint — core of the project
│   │   └── history.py               # GET /history/{room_id} — paginated message history
│   ├── services/
│   │   ├── connection_manager.py    # In-memory WebSocket connection registry
│   │   ├── auth_service.py          # Auth business logic
│   │   ├── room_service.py          # Room business logic
│   │   ├── message_service.py       # Message persistence
│   │   └── rate_limiter.py          # Sliding window rate limiter
│   └── schemas/
│       ├── auth.py                  # RegisterRequest, LoginRequest, TokenResponse
│       ├── room.py                  # RoomCreateRequest, RoomResponse
│       └── message.py               # MessageResponse, HistoryResponse
├── chat_client.html                 # Self-contained browser demo client
├── .env                             # Environment variables (never commit this)
├── requirements.txt
└── README.md
```

---

## Running locally

### Prerequisites

- Python 3.11+
- PostgreSQL 16

### 1. Clone and set up environment

```bash
git clone https://github.com/yourusername/realtime-chat-api.git
cd realtime-chat-api

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 2. Create the database

```bash
psql -U postgres
```

```sql
CREATE USER chat WITH PASSWORD 'secret';
CREATE DATABASE chatdb OWNER chat;
GRANT ALL PRIVILEGES ON DATABASE chatdb TO chat;
\q
```

### 3. Configure environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+asyncpg://chat:secret@localhost:5432/chatdb
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 4. Start the server

```bash
uvicorn app.main:app --reload
```

Tables are created automatically on startup.

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`

### 5. Open the demo client

Open `chat_client.html` in two separate browser tabs. Register two users, create a room, join from both tabs, and send messages.

---

## API reference

### Auth

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/auth/register` | Create a new user account | None |
| POST | `/auth/login` | Login and receive JWT | None |

**Register**
```json
POST /auth/register
{
  "username": "rafay",
  "email": "rafay@example.com",
  "password": "securepassword"
}
```

**Login**
```json
POST /auth/login
{
  "email": "rafay@example.com",
  "password": "securepassword"
}

Response:
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

### Rooms

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/rooms/` | Create a new room | Required |
| GET | `/rooms/` | List all rooms | Required |
| GET | `/rooms/{room_id}` | Get room details | Required |
| POST | `/rooms/{room_id}/join` | Join a room | Required |

### WebSocket

```
ws://localhost:8000/ws/{room_id}?token=<JWT>
```

JWT is passed as a query parameter because browsers cannot set custom headers during a WebSocket upgrade request.

**Inbound** (client → server): plain text string, max 200 characters

**Outbound** (server → client): JSON with a `type` field

```json
// Regular message
{
  "type": "message",
  "id": "uuid",
  "username": "rafay",
  "user_id": "uuid",
  "text": "hello",
  "room_id": "uuid",
  "timestamp": "2026-09-17T10:30:00Z"
}

// System announcement
{
  "type": "system",
  "text": "alice joined the room",
  "timestamp": "2026-09-17T10:30:00Z"
}

// Presence update (sent on connection)
{
  "type": "presence",
  "online_users": ["rafay", "alice"]
}

// Error
{
  "type": "error",
  "text": "Slow down — you can send more messages in 45s",
  "code": "rate_limited"
}
```

### History

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/history/{room_id}?limit=50` | Fetch message history (max 100) | Required |

---

## Rate limiting

Implemented as a sliding window algorithm — in-memory, no external dependencies.

| Endpoint | Limit | Key |
|---|---|---|
| WebSocket messages | 20 per 60 seconds | user_id |
| POST /auth/login | 5 per 60 seconds | client IP |
| POST /auth/register | 5 per 60 seconds | client IP |

A rate-limited WebSocket message returns an error frame — the connection stays open. A rate-limited HTTP request returns HTTP 429 with a `Retry-After` header.

---

## Key engineering decisions

**Single-worker, in-memory ConnectionManager**
The `ConnectionManager` is a module-level singleton — a `defaultdict` mapping room IDs to lists of active WebSocket objects. This is the simplest correct architecture for a single process. The trade-off is horizontal scaling: two workers can't share in-memory state.

**The scaling path:** moving the store to Redis Pub/Sub would decouple workers — each worker subscribes to a room channel and Redis fans out messages across all of them. This is a deliberate next step, not an oversight.

**JWT via query parameter on WebSocket**
Browsers cannot set `Authorization` headers during a WebSocket upgrade. The token travels as `?token=...`, is verified before `websocket.accept()` is called, and is never needed again for that session. Connections that fail verification are closed with code `1008` (Policy Violation) before being accepted.

**`expire_on_commit=False` on async sessions**
SQLAlchemy's default behavior expires ORM attributes after a commit, triggering a lazy load on next access. In async code that lazy load happens outside an active session and raises an error. Disabling expiry keeps attributes accessible after commit — the correct pattern for async SQLAlchemy.

**Sliding window over fixed window rate limiting**
A fixed window resets at a hard boundary — a user could send the full quota at 11:59:59 and again at 12:00:00, effectively doubling the rate for a brief window. A sliding window looks at the last N seconds from right now, so the limit is accurately enforced at all times.

---

## What I'd build next

- **Refresh tokens** — current JWTs expire and disconnect the user; refresh tokens would renew silently in the background
- **Redis Pub/Sub** — enables multiple Uvicorn workers to share connection state, making the app horizontally scalable
- **pytest suite** — async tests covering auth, room management, WebSocket lifecycle, and rate limiter logic
- **Leave room endpoint** — users can currently join but not leave a room
- **Cursor-based pagination** on history — current `limit` parameter doesn't support fetching older messages
- **Message reactions** — emoji reactions stored as a separate table, broadcast as a new message type
