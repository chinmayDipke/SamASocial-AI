"""The read step: what did the mentor just tell us, and what do they want?

Every turn opens with this one cheap structured call, and it does two jobs at once
because they need the same context: it fills the intake slots from what was said,
and it decides whether this turn asks a question, drafts a plan, edits the plan or
just answers. Splitting them into two calls would double the latency of every turn
to re-send the same conversation.

The rules on top of the model's answer all point the same way -- a routing step must
never be able to lose information:

- slots are merged, not replaced, so a model that forgets a field cannot unset it;
- `target` is kept only if it names something the plan really contains;
- an unusable answer falls back to a decision derived from the session state, which
  is always safe even if it is sometimes unambitious.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from ..config import get_settings
from ..schemas import CoursePlan, Intake
from ..sessions import Session
from .client import StructuredOutputError, request_json
from .prompts import READ_TURN_SYSTEM, build_read_turn_input

logger = logging.getLogger(__name__)

Action = Literal["ask", "generate", "refine", "answer"]
ACTIONS: tuple[Action, ...] = ("ask", "generate", "refine", "answer")

# Written out rather than derived from the Pydantic models: providers reject keywords
# like minItems, and this stays inside the portable subset. Unknown slots come back as
# empty strings rather than null, because strict json_schema modes dislike nullables.
INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "audience": {"type": "string"},
        "duration": {"type": "string"},
        "goals": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject", "audience", "duration", "goals"],
    "additionalProperties": False,
}

READ_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "intake": INTAKE_SCHEMA,
        "action": {"type": "string", "enum": list(ACTIONS)},
        "target": {"type": "string"},
    },
    "required": ["intake", "action", "target"],
    "additionalProperties": False,
}


class IntakeDraft(BaseModel):
    """The model's view of the slots. Empty means "still unknown", never "cleared"."""

    subject: str = ""
    audience: str = ""
    duration: str = ""
    goals: list[str] = Field(default_factory=list)


class TurnReadDraft(BaseModel):
    intake: IntakeDraft = Field(default_factory=IntakeDraft)
    action: str = "ask"
    target: str = ""


@dataclass(slots=True)
class TurnRead:
    """What the turn pipeline needs to know before it does anything."""

    intake: Intake
    action: Action
    target: str | None
    # True when a slot changed, so the caller knows to emit an `intake` frame.
    intake_changed: bool


def merge_intake(current: Intake, draft: IntakeDraft) -> tuple[Intake, bool]:
    """Fold the draft into what is known, keeping anything the draft left empty.

    A mentor can still correct a slot -- a non-empty value always wins -- but a model
    that drops `audience` from its answer cannot un-tick the checklist.
    """
    goals = [goal.strip() for goal in draft.goals if goal.strip()]
    merged = Intake(
        subject=draft.subject.strip() or current.subject,
        audience=draft.audience.strip() or current.audience,
        duration=draft.duration.strip() or current.duration,
        goals=goals or current.goals,
    )
    return merged, merged != current


def fallback_action(intake: Intake, plan: CoursePlan | None) -> Action:
    """Route from session state alone, for when the read call gives us nothing.

    With a plan in hand this answers rather than refines: answering a question badly
    costs a sentence, whereas editing a plan on a guess costs the mentor's work.
    """
    if plan is not None:
        return "answer"
    return "generate" if intake.is_complete else "ask"


def _clean_target(target: str, plan: CoursePlan | None) -> str | None:
    """Keep the target only if it names a module or lesson that actually exists."""
    candidate = target.strip()
    if not candidate or plan is None:
        return None
    known = {module.id for module in plan.modules} | {
        lesson.id for module in plan.modules for lesson in module.lessons
    }
    return candidate if candidate in known else None


def _as_action(value: str) -> Action | None:
    """Accept only the four actions the pipeline knows how to run."""
    for action in ACTIONS:
        if value == action:
            return action
    return None


async def read_turn(session: Session, message: str, transcript: str) -> TurnRead:
    """Slot-fill and route in one call. Never raises: a bad read degrades to a guess.

    The transcript is passed in rather than rendered here: the caller has already
    built it for the reply prompt, and both calls of a turn must read the same
    conversation.
    """
    settings = get_settings()
    messages = [
        {"role": "system", "content": READ_TURN_SYSTEM},
        {
            "role": "user",
            "content": build_read_turn_input(
                session.intake, transcript, message, session.plan
            ),
        },
    ]

    try:
        payload = await request_json(
            settings.condense_model, messages, READ_TURN_SCHEMA, "read_turn"
        )
        draft = TurnReadDraft.model_validate(payload)
    except (StructuredOutputError, ValueError) as exc:
        logger.info("Turn read failed, falling back to session state: %s", exc)
        action = fallback_action(session.intake, session.plan)
        return TurnRead(intake=session.intake, action=action, target=None, intake_changed=False)

    intake, changed = merge_intake(session.intake, draft.intake)
    action = _as_action(draft.action) or fallback_action(intake, session.plan)

    # A plan cannot be edited or discussed before it exists, and the mentor is not
    # asking for a redraft of something they have not seen.
    if session.plan is None and action in ("refine", "answer"):
        action = "generate" if intake.is_complete else "ask"

    return TurnRead(
        intake=intake,
        action=action,
        target=_clean_target(draft.target, session.plan),
        intake_changed=changed,
    )
