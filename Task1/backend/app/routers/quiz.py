"""Quiz mode endpoint (bonus feature)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from ..llm.quiz import QuizUnavailable, generate_quiz
from ..schemas import QuizResponse
from .deps import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["quiz"])


@router.post("/quiz", response_model=QuizResponse)
async def create_quiz(
    session: SessionDep,
    count: int = Query(default=5, ge=1, le=10),
) -> QuizResponse:
    try:
        return QuizResponse(questions=await generate_quiz(session, count))
    except QuizUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Quiz generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The quiz could not be generated right now. Please try again.",
        ) from exc
