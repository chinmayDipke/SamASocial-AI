"""Turning a brief into a course plan, and edits into a revised one.

The JSON Schema below is written by hand rather than generated from the Pydantic
models, for the same reason Task 1 does it: providers reject perfectly legal
keywords like `minItems`, so this stays inside the portable subset that every
OpenAI-compatible endpoint accepts. Validation is still Pydantic's job, so a plan
that does not fit the model is rejected rather than shown half-formed.

Refinement is the delicate half. The mentor has been editing this plan by hand, so
the input is whatever the plan currently is -- their edits included -- and the
output is only accepted if it still contains the work they did not ask to lose. That
check is `check_refinement`, and it is deliberately pure and boring: a guard that
needs an API call to decide is a guard that fails when the API does.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from pydantic import BaseModel, Field, ValidationError

from ..config import get_settings
from ..schemas import (
    AssessmentKind,
    CoursePlan,
    Intake,
    Level,
    Module,
    ResourceKind,
    assign_ids,
)
from .client import StructuredOutputError, request_json
from .intake import INTAKE_SCHEMA, IntakeDraft, merge_intake
from .prompts import (
    PLANNER_SYSTEM,
    REFINE_SYSTEM,
    REFINEMENT_KEPT_REPLY,
    SYLLABUS_SYSTEM,
    build_plan_input,
    build_refine_input,
    build_syllabus_input,
)

logger = logging.getLogger(__name__)

# Requests that legitimately shrink a plan. Anything outside this list losing a
# module is treated as the model going off the rails, not as the mentor's intent.
_REMOVAL_REQUEST = re.compile(
    r"\b(remove|removing|delete|deleting|drop|dropping|cut|cutting|merge|merging|"
    r"combine|combining|consolidate|omit|skip|scrap|shorten|shorter|condense|trim|"
    r"fewer|less)\b",
    re.IGNORECASE,
)

RESOURCE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "kind": {"type": "string", "enum": [kind.value for kind in ResourceKind]},
        "url": {"type": "string"},
        "provider": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["id", "title", "kind", "url", "provider", "note"],
    "additionalProperties": False,
}

LESSON_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "level": {"type": "string", "enum": [level.value for level in Level]},
        "duration_minutes": {"type": "integer"},
        "resources": {"type": "array", "items": RESOURCE_SCHEMA},
    },
    "required": ["id", "title", "summary", "level", "duration_minutes", "resources"],
    "additionalProperties": False,
}

ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "kind": {"type": "string", "enum": [kind.value for kind in AssessmentKind]},
        "description": {"type": "string"},
    },
    "required": ["title", "kind", "description"],
    "additionalProperties": False,
}

MODULE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "objectives": {"type": "array", "items": {"type": "string"}},
        "prerequisites": {"type": "array", "items": {"type": "string"}},
        "lessons": {"type": "array", "items": LESSON_SCHEMA},
        "assessment": ASSESSMENT_SCHEMA,
    },
    "required": ["id", "title", "objectives", "prerequisites", "lessons", "assessment"],
    "additionalProperties": False,
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subject": {"type": "string"},
        "audience": {"type": "string"},
        "duration": {"type": "string"},
        "outcomes": {"type": "array", "items": {"type": "string"}},
        "modules": {"type": "array", "items": MODULE_SCHEMA},
    },
    "required": ["title", "subject", "audience", "duration", "outcomes", "modules"],
    "additionalProperties": False,
}

# The syllabus path answers both questions at once: what the document says the course
# is, and what it looks like restructured. One call, because the document is the
# expensive part of the prompt and sending it twice buys nothing.
SYLLABUS_SCHEMA = {
    "type": "object",
    "properties": {"intake": INTAKE_SCHEMA, "plan": PLAN_SCHEMA},
    "required": ["intake", "plan"],
    "additionalProperties": False,
}


class PlanUnavailable(RuntimeError):
    """Raised when no usable plan came back. The message is shown to the mentor."""


class RefinementRejected(RuntimeError):
    """Raised when a refinement would have destroyed work. Message is shown as the reply."""


class SyllabusDraft(BaseModel):
    intake: IntakeDraft = Field(default_factory=IntakeDraft)
    plan: CoursePlan


def _parse_plan(payload: dict, what: str) -> CoursePlan:
    try:
        plan = CoursePlan.model_validate(payload)
    except ValidationError as exc:
        logger.info("%s did not validate: %s", what, exc)
        raise PlanUnavailable(
            "The plan that came back was not usable. Please try that again."
        ) from exc
    return _trim(plan)


def _trim(plan: CoursePlan) -> CoursePlan:
    """Enforce the size caps and drop resources that are not really links.

    Models occasionally write "N/A" or a bare title into `url`. Those cannot be
    checked and cannot be opened, so they are removed here rather than shown with an
    honest-looking badge -- unlike a real URL that fails verification, which stays
    visible and clearly marked.
    """
    settings = get_settings()
    modules: list[Module] = []
    for module in plan.modules[: settings.max_modules]:
        lessons = []
        for lesson in module.lessons[: settings.max_lessons_per_module]:
            usable = [
                resource
                for resource in lesson.resources
                if resource.url.strip().lower().startswith(("http://", "https://"))
            ]
            lessons.append(lesson.model_copy(update={"resources": usable}))
        modules.append(module.model_copy(update={"lessons": lessons}))
    return plan.model_copy(update={"modules": modules})


def _stamp(plan: CoursePlan, version: int) -> CoursePlan:
    return plan.model_copy(update={"version": version, "updated_at": datetime.now(UTC)})


def _name_modules(titles: list[str]) -> str:
    quoted = [f'"{title}"' for title in titles]
    if len(quoted) == 1:
        return quoted[0]
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"


def check_refinement(previous: CoursePlan, candidate: CoursePlan, request: str) -> str | None:
    """Describe how a refinement destroyed work, or return None if it is safe to keep.

    Refinement is the one operation that can lose a mentor's afternoon: the model is
    handed the whole plan and asked to hand it back changed, and a model having a bad
    day hands back three modules out of eight. So the result is checked against the
    plan it came from, and anything that lost work nobody asked to lose is refused.

    "Asked to lose" is read from the request text, which is crude but honest: shrinking
    is allowed when the mentor used a shrinking word, and even then a plan that keeps
    fewer than half its modules is treated as a collapse rather than an edit. Call this
    after ids have been assigned, so survival is decided by id rather than by title.
    """
    if not candidate.modules:
        return "had no modules left in it"

    invited = bool(_REMOVAL_REQUEST.search(request))
    kept_ids = {module.id for module in candidate.modules}
    lost = [module.title for module in previous.modules if module.id not in kept_ids]

    if lost and not invited:
        return f"dropped {_name_modules(lost)}"

    if lost and len(previous.modules) >= 3 and len(kept_ids) * 2 < len(previous.modules):
        return f"kept only {len(candidate.modules)} of your {len(previous.modules)} modules"

    before = sum(len(module.lessons) for module in previous.modules)
    after = sum(len(module.lessons) for module in candidate.modules)
    if before >= 4 and after * 2 < before and not invited:
        return f"cut the plan from {before} lessons down to {after}"

    return None


async def build_plan(intake: Intake, transcript: str) -> CoursePlan:
    """Draft a first course plan from the intake and the conversation behind it."""
    settings = get_settings()
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {
            "role": "user",
            "content": build_plan_input(
                intake, transcript, settings.max_modules, settings.max_lessons_per_module
            ),
        },
    ]

    try:
        payload = await request_json(
            settings.llm_chat_model, messages, PLAN_SCHEMA, "course_plan"
        )
    except StructuredOutputError as exc:
        raise PlanUnavailable(
            "The course plan did not come back in a usable form. Please ask again -- "
            "if it keeps happening, a different LLM_CHAT_MODEL will handle this better."
        ) from exc

    plan = _parse_plan(payload, "course_plan")
    if not plan.modules:
        raise PlanUnavailable(
            "The plan came back empty. Tell me a little more about the course and I will "
            "try again."
        )
    return _stamp(assign_ids(plan), version=1)


async def refine_plan(
    current: CoursePlan,
    request: str,
    transcript: str,
    target: str | None = None,
) -> CoursePlan:
    """Apply one requested change to the plan as it stands, including inline edits.

    The input is the *current* plan, so a mentor's hand edits go into the prompt and
    come back out. If the result fails `check_refinement`, this raises and the caller
    keeps the plan it already had.
    """
    settings = get_settings()
    messages = [
        {"role": "system", "content": REFINE_SYSTEM},
        {
            "role": "user",
            "content": build_refine_input(
                current,
                request,
                transcript,
                target,
                settings.max_modules,
                settings.max_lessons_per_module,
            ),
        },
    ]

    try:
        payload = await request_json(
            settings.llm_chat_model, messages, PLAN_SCHEMA, "refined_plan"
        )
    except StructuredOutputError as exc:
        raise RefinementRejected(
            REFINEMENT_KEPT_REPLY.format(detail="was not valid JSON")
        ) from exc

    candidate = assign_ids(_parse_plan(payload, "refined_plan"), previous=current)
    problem = check_refinement(current, candidate, request)
    if problem:
        logger.warning("Refinement rejected: it %s", problem)
        raise RefinementRejected(REFINEMENT_KEPT_REPLY.format(detail=problem))

    return _stamp(candidate, version=current.version + 1)


async def plan_from_syllabus(text: str) -> tuple[Intake, CoursePlan]:
    """Read an existing syllabus into a brief and a restructured plan, in one call."""
    settings = get_settings()
    messages = [
        {"role": "system", "content": SYLLABUS_SYSTEM},
        {
            "role": "user",
            "content": build_syllabus_input(
                text, settings.max_modules, settings.max_lessons_per_module
            ),
        },
    ]

    try:
        payload = await request_json(
            settings.llm_chat_model, messages, SYLLABUS_SCHEMA, "syllabus_plan"
        )
        draft = SyllabusDraft.model_validate(payload)
    except (StructuredOutputError, ValidationError) as exc:
        raise PlanUnavailable(
            "This syllabus could not be restructured into a plan. It may be mostly "
            "tables or scanned pages -- try pasting the text into the chat instead."
        ) from exc

    plan = _trim(draft.plan)
    if not plan.modules:
        raise PlanUnavailable(
            "No course structure could be read out of that document. Tell me about the "
            "course in the chat and I will build the plan from there."
        )

    intake, _ = merge_intake(Intake(), draft.intake)
    return intake, _stamp(assign_ids(plan), version=1)
