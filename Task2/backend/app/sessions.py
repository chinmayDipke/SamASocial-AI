"""In-memory session store.

A planning conversation lasts as long as the mentor is at their desk, so the store
deliberately stays in-process: no database to provision for a demo, and no schema
migration every time the plan model grows a field. Everything the rest of the app
touches goes through `SessionStore`, so putting Redis or Postgres behind it later
is a change to this file alone.

The `plan_lock` is the one piece of real concurrency control. A chat-driven
refinement and a mentor's inline PUT can arrive at the same moment, and both
rewrite the whole plan -- without the lock the later write silently reverts the
earlier one.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from .config import get_settings
from .schemas import ChatMessage, CoursePlan, Intake, SessionInfo


class SessionNotFound(KeyError):
    """Raised when a session id is unknown or has expired."""


@dataclass(slots=True)
class Session:
    id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    messages: list[ChatMessage] = field(default_factory=list)
    intake: Intake = field(default_factory=Intake)
    plan: CoursePlan | None = None
    # Serialises whole-plan writes: see the module docstring.
    plan_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def recent_messages(self, limit: int) -> list[ChatMessage]:
        return self.messages[-limit:]

    def record_turn(self, message: str, reply: str) -> None:
        """Append the exchange, so the next turn can resolve "make that simpler"."""
        self.messages.append(ChatMessage(role="user", content=message))
        self.messages.append(ChatMessage(role="assistant", content=reply))

    def to_info(self) -> SessionInfo:
        return SessionInfo(
            id=self.id,
            created_at=self.created_at,
            messages=list(self.messages),
            intake=self.intake,
            plan=self.plan,
        )


class SessionStore:
    """Process-wide session registry with TTL eviction and a hard size cap."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> Session:
        settings = get_settings()
        async with self._lock:
            self._evict_expired()
            if len(self._sessions) >= settings.max_sessions:
                oldest = min(self._sessions.values(), key=lambda s: s.last_seen)
                del self._sessions[oldest.id]
            session = Session(id=uuid.uuid4().hex)
            self._sessions[session.id] = session
            return session

    async def get(self, session_id: str) -> Session:
        async with self._lock:
            self._evict_expired()
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFound(session_id)
            session.last_seen = datetime.now(UTC)
            return session

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    def _evict_expired(self) -> None:
        ttl = timedelta(minutes=get_settings().session_ttl_minutes)
        cutoff = datetime.now(UTC) - ttl
        for session_id in [sid for sid, s in self._sessions.items() if s.last_seen < cutoff]:
            del self._sessions[session_id]


store = SessionStore()
