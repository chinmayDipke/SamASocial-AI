"""Reading, editing and exporting the plan directly.

The mentor edits the plan in place in the UI, so the write side takes the whole plan
rather than a patch: the browser already holds the authoritative document, and a
field-level PATCH API for a nested tree would be a lot of surface for no gain. Ids
are re-derived from the previous plan on the way in, so a mentor cannot rename an id
by editing a title, and a refinement arriving a moment later still recognises every
row.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from ..schemas import CoursePlan, PlanConflict, PlanUpdateRequest, assign_ids
from ..sessions import Session
from .deps import SessionDep

router = APIRouter(prefix="/api/sessions/{session_id}/plan", tags=["plan"])

_NO_PLAN = (
    "There is no course plan in this session yet. Tell the assistant what you want to "
    "teach and it will draft one."
)

_STALE_PLAN = (
    "The assistant changed this plan while you were editing it, so your copy was out "
    "of date and this edit was not saved. What you see now is the current plan -- make "
    "the change again on it."
)


def _require_plan(session: Session) -> CoursePlan:
    if session.plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_PLAN)
    return session.plan


def _filename(plan: CoursePlan) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", plan.title.lower()).strip("-")
    return f"{slug or 'course-plan'}.json"


@router.put(
    "",
    response_model=CoursePlan,
    responses={status.HTTP_409_CONFLICT: {"model": PlanConflict}},
)
async def update_plan(
    session: SessionDep, payload: PlanUpdateRequest
) -> CoursePlan | JSONResponse:
    """Save an inline edit, unless the plan moved on while it was being typed.

    `version` is the precondition, and it is the whole reason the field exists. The
    browser echoes back the version it was last given, so a value behind the stored
    one means a refinement landed in between: writing anyway would push a document
    built on the older plan over the top of the newer one, and the mentor would lose
    a whole refinement to save one field. Equal is the normal case -- every
    click-to-edit save is an edit of exactly the version it was handed.
    """
    async with session.plan_lock:
        previous = _require_plan(session)
        if payload.plan.version < previous.version:
            conflict = PlanConflict(detail=_STALE_PLAN, plan=previous)
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=conflict.model_dump(mode="json"),
            )
        plan = assign_ids(payload.plan, previous=previous)
        session.plan = plan.model_copy(
            update={
                "version": max(previous.version, payload.plan.version) + 1,
                "updated_at": datetime.now(UTC),
            }
        )
        return session.plan


@router.get("/export")
async def export_plan(session: SessionDep) -> Response:
    """The plan as a downloadable JSON file, for whatever system consumes it next."""
    plan = _require_plan(session)
    body = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{_filename(plan)}"'},
    )
