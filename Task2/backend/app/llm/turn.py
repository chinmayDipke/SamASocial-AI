"""One user message, start to finish.

This is the architecture of the app in one file, and its shape is deliberate: a turn
costs at most two LLM calls, and they have different jobs.

The first call is cheap and structured (`llm/intake.read_turn`): it reads the slots
out of what was said and decides what this turn is -- ask, generate, refine or
answer. Nothing is generated yet, so a misread costs a question rather than a
rewritten course.

The second call is the expensive one, and which one it is depends on that decision.
Only two of the four branches touch the plan, and both of them work from the plan as
it currently stands -- inline edits included -- so nothing the mentor typed is
overwritten by a model that never saw it.

Everything is yielded as `(event, payload)` pairs for the SSE router to frame, which
keeps HTTP concerns out of here and makes the sequence readable: the mentor sees a
status, then the reply streaming, then the plan, then the plan again with its links
checked.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..config import get_settings
from ..resources.links import verify_links
from ..schemas import CoursePlan
from ..sessions import Session
from .client import stream_text
from .intake import Action, read_turn
from .planner import PlanUnavailable, RefinementRejected, build_plan, refine_plan
from .prompts import (
    ACK_SYSTEM,
    ANSWER_SYSTEM,
    ASK_SYSTEM,
    NEED_MORE_INTAKE_REPLY,
    PLAN_READY_REPLY,
    build_ack_input,
    build_answer_input,
    build_ask_input,
    describe_slots,
    render_transcript,
)

logger = logging.getLogger(__name__)

# A stream event: (event name, JSON-serialisable payload).
StreamEvent = tuple[str, dict]


def _plan_event(plan: CoursePlan) -> StreamEvent:
    return ("plan", {"plan": plan.model_dump(mode="json")})


async def _stream_reply(system: str, user: str, sink: list[str]) -> AsyncIterator[StreamEvent]:
    """Stream one conversational reply, collecting it for the session history."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    async for text in stream_text(get_settings().llm_chat_model, messages):
        sink.append(text)
        yield ("token", {"text": text})


async def _say(text: str, sink: list[str]) -> AsyncIterator[StreamEvent]:
    """Send a reply we wrote ourselves, so the UI treats it like any other."""
    sink.append(text)
    yield ("token", {"text": text})


async def _publish(plan: CoursePlan) -> AsyncIterator[StreamEvent]:
    """Emit the plan, then emit it again once its resource links have been checked."""
    yield _plan_event(plan)

    resources = plan.resources
    if not get_settings().verify_resource_links or not resources:
        return

    yield ("status", {"stage": "checking-links", "detail": f"Checking {len(resources)} links"})
    await verify_links(resources)
    yield _plan_event(plan)


def _resolve_action(action: Action, session: Session, missing: list[str]) -> Action:
    """Have the last word on what this turn does, from state rather than opinion.

    The read step is a model, and a model can ask for a plan of a course with no
    subject or offer to edit a plan that does not exist. State knows better.
    """
    if action == "generate" and "subject" in missing:
        return "ask"  # No subject means no course to plan; ask instead of inventing one.
    if action == "ask" and not missing:
        return "generate"  # Nothing left to ask about, so the honest move is to draft.
    if action in ("refine", "answer") and session.plan is None:
        return "ask" if missing else "generate"
    return action


async def run_turn(session: Session, message: str) -> AsyncIterator[StreamEvent]:
    """Run one turn of the conversation, yielding SSE events as they happen."""
    settings = get_settings()
    history = [
        {"role": m.role, "content": m.content}
        for m in session.recent_messages(settings.max_history_messages)
    ]
    transcript = render_transcript(history)
    reply: list[str] = []

    yield ("status", {"stage": "thinking", "detail": "Reading what you asked for"})
    read = await read_turn(session, message, transcript)
    session.intake = read.intake
    if read.intake_changed:
        yield ("intake", {"intake": session.intake.model_dump(mode="json")})

    missing = session.intake.missing
    action = _resolve_action(read.action, session, missing)

    if action == "ask":
        async for event in _stream_reply(
            ASK_SYSTEM,
            build_ask_input(session.intake, transcript, message, missing[0]),
            reply,
        ):
            yield event

    elif action == "answer" and session.plan is not None:
        async for event in _stream_reply(
            ANSWER_SYSTEM,
            build_answer_input(session.plan, transcript, message),
            reply,
        ):
            yield event

    elif action == "generate":
        yield ("status", {"stage": "drafting", "detail": "Shaping the modules"})
        async for event in _stream_reply(
            ACK_SYSTEM,
            build_ack_input(session.intake, transcript, message, session.plan),
            reply,
        ):
            yield event
        try:
            async with session.plan_lock:
                plan = await build_plan(session.intake, transcript)
                session.plan = plan
        except PlanUnavailable as exc:
            session.record_turn(message, "".join(reply))
            yield ("error", {"detail": str(exc)})
            yield ("done", {})
            return
        async for event in _publish(plan):
            yield event

    elif action == "refine" and session.plan is not None:
        yield ("status", {"stage": "refining", "detail": "Applying your change"})
        async for event in _stream_reply(
            ACK_SYSTEM,
            build_ack_input(session.intake, transcript, message, session.plan),
            reply,
        ):
            yield event
        try:
            # The lock is held across the call: a plan PUT that landed halfway through
            # would be overwritten by the result a moment later, so making it wait is
            # the honest behaviour rather than a silently lost edit.
            async with session.plan_lock:
                plan = await refine_plan(session.plan, message, transcript, read.target)
                session.plan = plan
        except RefinementRejected as exc:
            # The mentor's plan is untouched; say so, in the reply itself, and send the
            # plan back unchanged so the UI cannot be left showing a half-applied edit.
            # Blank line first: this note follows the acknowledgement already sent.
            async for event in _say(f"\n\n{exc}", reply):
                yield event
            session.record_turn(message, "".join(reply))
            yield _plan_event(session.plan)
            yield ("done", {})
            return
        except PlanUnavailable as exc:
            session.record_turn(message, "".join(reply))
            yield ("error", {"detail": str(exc)})
            yield ("done", {})
            return
        async for event in _publish(plan):
            yield event

    if not reply:
        # Every branch above either streamed something or bailed out, so this only
        # fires when the model returned an empty stream -- and silence is not an answer.
        fallback = (
            PLAN_READY_REPLY
            if session.plan is not None
            else NEED_MORE_INTAKE_REPLY.format(slots=describe_slots(missing or ["subject"]))
        )
        async for event in _say(fallback, reply):
            yield event

    session.record_turn(message, "".join(reply).strip())
    yield ("done", {})
