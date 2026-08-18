"""Session lifecycle."""

from __future__ import annotations

from fastapi import APIRouter, status

from ..schemas import SessionInfo
from ..sessions import Session, store
from .deps import SessionDep

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def to_info(session: Session) -> SessionInfo:
    return SessionInfo(
        session_id=session.id,
        created_at=session.created_at,
        sources=[source.to_summary() for source in session.sources.values()],
        message_count=len(session.messages),
    )


@router.post("", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
async def create_session() -> SessionInfo:
    return to_info(await store.create())


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(session: SessionDep) -> SessionInfo:
    return to_info(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session: SessionDep) -> None:
    await store.delete(session.id)
