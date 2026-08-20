"""Shared route dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status

from ..sessions import Session, SessionNotFound, store


async def resolve_session(
    session_id: Annotated[str, Path(min_length=8, max_length=64)],
) -> Session:
    try:
        return await store.get(session_id)
    except SessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This session has expired or does not exist. Start a new one.",
        ) from exc


SessionDep = Annotated[Session, Depends(resolve_session)]
