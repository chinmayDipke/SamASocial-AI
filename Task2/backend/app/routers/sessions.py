"""Session lifecycle."""

from __future__ import annotations

from fastapi import APIRouter, status

from ..schemas import SessionInfo
from ..sessions import store
from .deps import SessionDep

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
async def create_session() -> SessionInfo:
    session = await store.create()
    return session.to_info()


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(session: SessionDep) -> SessionInfo:
    return session.to_info()


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session: SessionDep) -> None:
    await store.delete(session.id)
