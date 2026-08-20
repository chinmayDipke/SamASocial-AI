"""The SSE wire contract, pinned frame by frame.

The browser is the only consumer of `run_turn`, and it reads these events by name and
reaches into each payload by key -- `frontend/lib/types.ts` declares the union it
switches on. Nothing else in the stack notices if a name or a key drifts: the backend
stays ruff-clean, the frontend stays type-clean, and the app silently stops updating.
So the names, the keys and their order are asserted here rather than trusted.

No key and no network: the two model calls and the link check are stubbed, because
what is under test is the shape of the stream, not what the model puts in it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

import pytest

from app.config import get_settings
from app.llm import turn as turn_module
from app.llm.intake import TurnRead
from app.llm.planner import RefinementRejected
from app.schemas import CoursePlan, Intake, Lesson, LinkStatus, Module, Resource
from app.sessions import Session

# Every event name and payload key the frontend's `StreamFrame` union declares.
FRAME_KEYS = {
    "status": {"stage", "detail"},
    "token": {"text"},
    "intake": {"intake"},
    "plan": {"plan"},
    "done": set(),
    "error": {"detail"},
}

STAGES = {"thinking", "drafting", "refining", "checking-links"}

COMPLETE = Intake(
    subject="Python for data analysis",
    audience="Adults, no coding background",
    duration="6 weeks, two 90-minute sessions",
    goals=["Clean a messy CSV"],
)


def a_plan(*, with_resource: bool = True) -> CoursePlan:
    resources = (
        [Resource(id="m1-l1-r1", title="Docs", url="https://docs.python.org/3/")]
        if with_resource
        else []
    )
    return CoursePlan(
        title="Python for data analysis",
        modules=[
            Module(
                id="m1",
                title="Foundations",
                lessons=[Lesson(id="m1-l1", title="Reading a CSV", resources=resources)],
            )
        ],
    )


@pytest.fixture(autouse=True)
def _fresh_settings() -> object:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> object:
    """Replace both model calls and the link check, so a turn runs offline."""

    async def stream_text(model: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        for piece in ("Drafting ", "that now."):
            yield piece

    async def verify_links(resources: Sequence[Resource]) -> None:
        for resource in resources:
            resource.link_status = LinkStatus.VERIFIED

    monkeypatch.setattr(turn_module, "stream_text", stream_text)
    monkeypatch.setattr(turn_module, "verify_links", verify_links)
    return monkeypatch


def set_read(monkeypatch: pytest.MonkeyPatch, read: TurnRead) -> None:
    async def read_turn(session: Session, message: str, transcript: str) -> TurnRead:
        return read

    monkeypatch.setattr(turn_module, "read_turn", read_turn)


def drive(session: Session, message: str) -> list[tuple[str, dict]]:
    async def run() -> list[tuple[str, dict]]:
        return [event async for event in turn_module.run_turn(session, message)]

    return asyncio.run(run())


def names(events: list[tuple[str, dict]]) -> list[str]:
    return [name for name, _ in events]


def payloads(events: list[tuple[str, dict]], name: str) -> list[dict]:
    return [payload for event, payload in events if event == name]


def assert_wire_contract(events: list[tuple[str, dict]]) -> None:
    """Every frame is one the frontend knows, carrying exactly the keys it reads."""
    for name, payload in events:
        assert name in FRAME_KEYS, f"unknown SSE event '{name}'"
        assert set(payload) == FRAME_KEYS[name], f"'{name}' payload keys drifted"
    for payload in payloads(events, "status"):
        assert payload["stage"] in STAGES, payload["stage"]
        assert isinstance(payload["detail"], str)
    assert names(events)[-1] == "done", "a turn must always close with done"


def test_an_intake_question_streams_status_then_tokens(stub: pytest.MonkeyPatch) -> None:
    session = Session(id="s" * 32)
    set_read(stub, TurnRead(intake=Intake(), action="ask", target=None, intake_changed=True))

    events = drive(session, "I want to teach something")

    assert_wire_contract(events)
    assert names(events) == ["status", "intake", "token", "token", "done"]
    assert payloads(events, "status")[0]["stage"] == "thinking"
    assert set(payloads(events, "intake")[0]["intake"]) == {
        "subject",
        "audience",
        "duration",
        "goals",
    }


def test_a_generated_plan_is_published_then_republished_with_link_status(
    stub: pytest.MonkeyPatch,
) -> None:
    """The second `plan` frame is the whole point of checking links server-side."""
    session = Session(id="s" * 32)
    set_read(stub, TurnRead(intake=COMPLETE, action="generate", target=None, intake_changed=False))

    async def build_plan(
        intake: Intake, transcript: str, previous: CoursePlan | None = None
    ) -> CoursePlan:
        return a_plan()

    stub.setattr(turn_module, "build_plan", build_plan)

    events = drive(session, "go ahead")

    assert_wire_contract(events)
    assert names(events) == [
        "status",
        "status",
        "token",
        "token",
        "plan",
        "status",
        "plan",
        "done",
    ]
    assert [p["stage"] for p in payloads(events, "status")] == [
        "thinking",
        "drafting",
        "checking-links",
    ]

    first, second = payloads(events, "plan")
    # The frontend indexes straight into these; a renamed key is a silent failure.
    assert set(first["plan"]) == {
        "title",
        "subject",
        "audience",
        "duration",
        "outcomes",
        "modules",
        "version",
        "updated_at",
    }
    module = first["plan"]["modules"][0]
    assert set(module) == {
        "id",
        "title",
        "objectives",
        "prerequisites",
        "lessons",
        "assessment",
    }
    lesson = module["lessons"][0]
    assert set(lesson) == {"id", "title", "summary", "level", "duration_minutes", "resources"}
    assert set(lesson["resources"][0]) == {
        "id",
        "title",
        "kind",
        "url",
        "provider",
        "note",
        "link_status",
    }
    assert lesson["resources"][0]["link_status"] == "unchecked"
    assert second["plan"]["modules"][0]["lessons"][0]["resources"][0]["link_status"] == "verified"


def test_a_plan_with_no_resources_is_published_once(stub: pytest.MonkeyPatch) -> None:
    """No links means no link-checking frames -- and no phantom `checking-links` stage."""
    session = Session(id="s" * 32)
    set_read(stub, TurnRead(intake=COMPLETE, action="generate", target=None, intake_changed=False))

    async def build_plan(
        intake: Intake, transcript: str, previous: CoursePlan | None = None
    ) -> CoursePlan:
        return a_plan(with_resource=False)

    stub.setattr(turn_module, "build_plan", build_plan)

    events = drive(session, "go ahead")

    assert_wire_contract(events)
    assert names(events) == ["status", "status", "token", "token", "plan", "done"]


def test_a_rejected_refinement_returns_the_untouched_plan_and_no_error_frame(
    stub: pytest.MonkeyPatch,
) -> None:
    """The mentor's plan survives, so the UI must be sent it rather than an error."""
    session = Session(id="s" * 32)
    session.intake = COMPLETE
    session.plan = a_plan()
    set_read(stub, TurnRead(intake=COMPLETE, action="refine", target="m1", intake_changed=False))

    async def refine_plan(
        current: CoursePlan, request: str, transcript: str, target: str | None = None
    ) -> CoursePlan:
        raise RefinementRejected("dropped everything")

    stub.setattr(turn_module, "refine_plan", refine_plan)

    events = drive(session, "make it shorter")

    assert_wire_contract(events)
    assert "error" not in names(events)
    assert payloads(events, "plan")[-1]["plan"]["modules"][0]["id"] == "m1"
    assert session.plan is not None and len(session.plan.modules) == 1


def test_a_turn_is_recorded_in_the_history_it_will_be_asked_about_next(
    stub: pytest.MonkeyPatch,
) -> None:
    session = Session(id="s" * 32)
    set_read(stub, TurnRead(intake=Intake(), action="ask", target=None, intake_changed=False))

    drive(session, "teach me teaching")

    assert [m.role for m in session.messages] == ["user", "assistant"]
    assert session.messages[0].content == "teach me teaching"
    assert session.messages[1].content == "Drafting that now."


def test_sse_frames_are_shaped_the_way_the_browser_parses_them() -> None:
    """The frontend splits on a blank line and slices off `event:` / `data:`."""
    from app.routers.chat import sse_frame

    frame = sse_frame("status", {"stage": "thinking", "detail": "Reading"})

    assert frame.endswith("\n\n")
    head, body = frame.rstrip("\n").split("\n")
    assert head == "event: status"
    assert body.startswith("data: ")


def test_a_finished_plan_is_never_regenerated_just_because_intake_is_complete(
    stub: pytest.MonkeyPatch,
) -> None:
    """The mentor's plan is not collateral damage for a misrouted turn.

    `_resolve_action` promotes `ask` to `generate` once there is nothing left to ask
    about. That is right on the first pass and catastrophic on the tenth: the read
    step only has to misjudge one conversational message for the whole course -- and
    every hand edit in it -- to be rebuilt from scratch. `generate` has no equivalent
    of the refinement guard, so the block has to happen here.
    """
    session = Session(id="s" * 32)
    session.intake = COMPLETE
    session.plan = a_plan()
    before = session.plan

    set_read(stub, TurnRead(intake=COMPLETE, action="ask", target=None, intake_changed=False))
    events = drive(session, "so what do you think of all this?")

    assert session.plan is before, "the existing plan was replaced"
    assert not [e for e in events if e[0] == "plan"], "an answer must not publish a plan"


def test_with_no_plan_yet_a_complete_intake_still_drafts_one(stub: pytest.MonkeyPatch) -> None:
    """The guard above must not break the first draft, which is the normal path."""
    session = Session(id="s" * 32)
    session.intake = COMPLETE

    async def build_plan(
        intake: Intake, transcript: str, previous: CoursePlan | None = None
    ) -> CoursePlan:
        return a_plan(with_resource=False)

    stub.setattr(turn_module, "build_plan", build_plan)
    set_read(stub, TurnRead(intake=COMPLETE, action="ask", target=None, intake_changed=False))
    events = drive(session, "that is everything")

    assert session.plan is not None
    assert [e for e in events if e[0] == "plan"]


def test_an_explicit_restart_carries_the_version_forward(stub: pytest.MonkeyPatch) -> None:
    """Starting over is allowed; silently resetting the version number is not.

    The browser is still holding the old version, so a count that restarts at 1 would
    let an edit already queued there pass the PUT precondition and land on the plan
    that just replaced it.
    """
    session = Session(id="s" * 32)
    session.intake = COMPLETE
    session.plan = a_plan().model_copy(update={"version": 7})

    async def build_plan(
        intake: Intake, transcript: str, previous: CoursePlan | None = None
    ) -> CoursePlan:
        # Mirrors the real signature: the version is derived from what came before.
        return a_plan(with_resource=False).model_copy(
            update={"version": previous.version + 1 if previous else 1}
        )

    stub.setattr(turn_module, "build_plan", build_plan)
    set_read(stub, TurnRead(intake=COMPLETE, action="generate", target=None, intake_changed=False))
    drive(session, "scrap that, plan me a different course instead")

    assert session.plan is not None
    assert session.plan.version == 8, "an explicit regeneration must not reset the version"
