"""In-memory session store.

The spec asks for conversation memory that lasts "for the duration of the
session", so this deliberately stays in-process: no database to provision for a
demo. Everything the rest of the app needs goes through `SessionStore`, so
swapping in Redis or Postgres later is a change to this file alone.

Both retrieval indexes live on the *session*, not the source, so a question is
always answered across every loaded source at once.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from .config import get_settings
from .retrieval.bm25 import BM25Index
from .retrieval.embeddings import VectorIndex
from .schemas import ChatMessage, Chunk, SourceKind, SourceStatus, SourceSummary


class SessionNotFound(KeyError):
    """Raised when a session id is unknown or has expired."""


@dataclass(slots=True)
class Source:
    id: str
    ref: str
    kind: SourceKind
    title: str
    status: SourceStatus = SourceStatus.PROCESSING
    url: str | None = None
    summary: str | None = None
    error: str | None = None
    chunk_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_summary(self) -> SourceSummary:
        return SourceSummary(
            id=self.id,
            ref=self.ref,
            kind=self.kind,
            title=self.title,
            status=self.status,
            url=self.url,
            chunk_count=self.chunk_count,
            summary=self.summary,
            error=self.error,
            created_at=self.created_at,
        )


@dataclass(slots=True)
class Session:
    id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    sources: dict[str, Source] = field(default_factory=dict)
    chunks: dict[str, Chunk] = field(default_factory=dict)
    bm25: BM25Index = field(default_factory=BM25Index)
    vectors: VectorIndex = field(default_factory=VectorIndex)
    messages: list[ChatMessage] = field(default_factory=list)
    # Serialises index mutations so two concurrent uploads cannot interleave.
    index_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Derived out-of-scope baseline, recomputed whenever the corpus changes.
    scope_baseline: float | None = None
    scope_baseline_chunks: int = 0

    @property
    def ready_sources(self) -> list[Source]:
        return [s for s in self.sources.values() if s.status is SourceStatus.READY]

    def next_ref(self) -> str:
        return f"S{len(self.sources) + 1}"

    def source_for_chunk(self, chunk_id: str) -> Source | None:
        chunk = self.chunks.get(chunk_id)
        return self.sources.get(chunk.source_id) if chunk else None

    def register_chunks(self, chunks: list[Chunk]) -> None:
        """Add chunks to the keyword index and the chunk lookup table."""
        for chunk in chunks:
            self.chunks[chunk.id] = chunk
            self.bm25.add(chunk.id, chunk.text)
        # The corpus changed, so the derived scope baseline is stale.
        self.scope_baseline = None

    def recent_messages(self, limit: int) -> list[ChatMessage]:
        return self.messages[-limit:]


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
