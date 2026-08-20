"""The inline-edit endpoint, and the precondition that makes it safe.

`PUT /plan` is what every click-to-edit save runs through, and it has two jobs that
pull against each other: it must apply an ordinary edit without ceremony, and it must
refuse one built on a plan the assistant has since rewritten. `version` is what tells
those two apart, so both directions are asserted here -- a normal save is the path
the whole feature depends on, and a stale save is the path that used to lose a
refinement.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.routers.plan import export_plan, update_plan
from app.schemas import CoursePlan, Lesson, Module, PlanUpdateRequest
from app.sessions import Session


def a_plan(*, version: int = 1, title: str = "Python for beginners") -> CoursePlan:
    return CoursePlan(
        title=title,
        version=version,
        modules=[
            Module(
                id="m1",
                title="Foundations",
                lessons=[Lesson(id="m1-l1", title="Variables")],
            )
        ],
    )


def a_session(plan: CoursePlan | None) -> Session:
    session = Session(id="s" * 32)
    session.plan = plan
    return session


def put(session: Session, plan: CoursePlan) -> CoursePlan | JSONResponse:
    return asyncio.run(update_plan(session, PlanUpdateRequest(plan=plan)))


def test_an_ordinary_edit_applies_and_bumps_the_version() -> None:
    stored = a_plan(version=4)
    session = a_session(stored)

    edited = stored.model_copy(update={"title": "Python, gently"})
    result = put(session, edited)

    assert isinstance(result, CoursePlan)
    assert result.title == "Python, gently"
    assert result.version == 5
    assert session.plan is not None and session.plan.title == "Python, gently"


def test_an_edit_of_the_current_version_is_never_a_conflict() -> None:
    """Equal is the normal case: the browser edits exactly the version it was handed."""
    for version in (1, 2, 17):
        session = a_session(a_plan(version=version))

        result = put(session, a_plan(version=version, title="Renamed"))

        assert isinstance(result, CoursePlan), f"version {version} was refused"
        assert result.version == version + 1


def test_an_edit_built_on_an_overtaken_plan_is_refused() -> None:
    """The assistant refined to version 6 while the mentor was typing on version 4."""
    refined = a_plan(version=6, title="Python, restructured")
    session = a_session(refined)

    result = put(session, a_plan(version=4, title="A title typed on the old plan"))

    assert isinstance(result, JSONResponse)
    assert result.status_code == 409
    # The refinement is untouched -- that is the whole point of refusing.
    assert session.plan is not None
    assert session.plan.title == "Python, restructured"
    assert session.plan.version == 6


def test_the_refusal_carries_the_plan_the_browser_needs_to_recover() -> None:
    import json

    session = a_session(a_plan(version=6, title="Python, restructured"))

    result = put(session, a_plan(version=4))

    assert isinstance(result, JSONResponse)
    body = json.loads(bytes(result.body))
    assert set(body) == {"detail", "plan"}
    assert body["plan"]["title"] == "Python, restructured"
    assert body["plan"]["version"] == 6
    # Written for the mentor, not for a log.
    assert "out of date" in body["detail"]


def test_ids_are_re_derived_so_a_renamed_module_keeps_its_identity() -> None:
    stored = a_plan(version=1)
    session = a_session(stored)

    renamed = stored.model_copy(
        update={"modules": [stored.modules[0].model_copy(update={"title": "Groundwork"})]}
    )
    result = put(session, renamed)

    assert isinstance(result, CoursePlan)
    assert result.modules[0].id == "m1"
    assert result.modules[0].lessons[0].id == "m1-l1"


def test_editing_a_session_with_no_plan_says_so() -> None:
    session = a_session(None)

    with pytest.raises(HTTPException) as raised:
        put(session, a_plan())

    assert raised.value.status_code == 404
    assert "no course plan" in str(raised.value.detail).lower()


def test_the_export_is_named_after_the_course() -> None:
    session = a_session(a_plan(title="Python for Beginners!"))

    response = asyncio.run(export_plan(session))

    assert response.headers["content-disposition"] == (
        'attachment; filename="python-for-beginners.json"'
    )
