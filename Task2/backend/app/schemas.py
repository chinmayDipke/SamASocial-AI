"""Wire and domain models -- the contract the backend, the model and the UI share.

`CoursePlan` is the whole product: it is what the model fills in, what the mentor
edits field by field, what streams to the browser and what exports as JSON. Two
consequences shape everything below.

First, every editable row needs a stable identity. The UI keys rows off `id` and
PUTs the whole plan back, so ids are short readable slugs (`m1`, `m1-l2`,
`m1-l2-r1`) assigned by `assign_ids()` on the server. The model never invents
them: it is asked for content, not identity, and the ids it echoes back are only
honoured when they match something that already exists.

Second, the model's output must validate *without* ids. Id fields therefore
default to empty and are filled in immediately after parsing, which keeps one set
of models for drafts, stored plans and inline edits alike.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, Field

# The four things the assistant must learn before it can plan a course. Order is
# the order the intake asks about them, so the checklist reads top to bottom.
INTAKE_SLOTS = ("subject", "audience", "duration", "goals")


class Level(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ResourceKind(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"
    DOCS = "documentation"
    EXERCISE = "exercise"


class AssessmentKind(StrEnum):
    QUIZ = "quiz"
    PROJECT = "project"
    ASSIGNMENT = "assignment"


class LinkStatus(StrEnum):
    VERIFIED = "verified"
    UNREACHABLE = "unreachable"
    UNCHECKED = "unchecked"


class Resource(BaseModel):
    """One publicly available thing a learner can open, plus what we know about it."""

    id: str = ""
    title: str
    kind: ResourceKind = ResourceKind.ARTICLE
    url: str
    # The platform it lives on (YouTube, MDN, Kaggle...). Stated separately so the UI
    # can show provenance without parsing the URL, and so the allow-list is checkable.
    provider: str = ""
    note: str = ""
    # Filled in by resources/links.py after the plan is built; never by the model.
    link_status: LinkStatus = LinkStatus.UNCHECKED


class Lesson(BaseModel):
    id: str = ""
    title: str
    summary: str = ""
    level: Level = Level.BEGINNER
    duration_minutes: int = 60
    resources: list[Resource] = Field(default_factory=list)


class Assessment(BaseModel):
    title: str
    kind: AssessmentKind = AssessmentKind.QUIZ
    description: str = ""


class Module(BaseModel):
    id: str = ""
    title: str
    objectives: list[str] = Field(default_factory=list)
    # Topics a learner should already be comfortable with. Earlier modules of this
    # same course count, which is what makes the sequence legible to a mentor.
    prerequisites: list[str] = Field(default_factory=list)
    lessons: list[Lesson] = Field(default_factory=list)
    assessment: Assessment | None = None


class CoursePlan(BaseModel):
    title: str
    subject: str = ""
    audience: str = ""
    duration: str = ""
    outcomes: list[str] = Field(default_factory=list)
    modules: list[Module] = Field(default_factory=list)
    # Bumped on every refinement and every inline edit, so the UI can tell a stale
    # optimistic update from a fresh one.
    version: int = 1
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def resources(self) -> list[Resource]:
        """Every resource in the plan, in reading order."""
        return [r for module in self.modules for lesson in module.lessons for r in lesson.resources]


class Intake(BaseModel):
    """What the assistant has learned so far. Drives the checklist in the UI."""

    subject: str | None = None
    audience: str | None = None
    duration: str | None = None
    goals: list[str] = Field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        """Slot names still unfilled, in the order the intake should ask about them."""
        filled = {
            "subject": bool((self.subject or "").strip()),
            "audience": bool((self.audience or "").strip()),
            "duration": bool((self.duration or "").strip()),
            "goals": any(goal.strip() for goal in self.goals),
        }
        return [slot for slot in INTAKE_SLOTS if not filled[slot]]

    @property
    def is_complete(self) -> bool:
        return not self.missing


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionInfo(BaseModel):
    """Everything the UI needs to rehydrate itself after a reload."""

    id: str
    created_at: datetime
    messages: list[ChatMessage]
    intake: Intake
    plan: CoursePlan | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class PlanUpdateRequest(BaseModel):
    """An inline edit: the mentor's whole plan, exactly as the UI has it."""

    plan: CoursePlan


class PlanConflict(BaseModel):
    """A refused inline edit: why it was refused, and the plan the server now holds.

    The plan travels with the message because the browser needs it to recover: the
    only useful thing it can do with a rejected edit is show what the plan actually
    became, and asking for it in a second request would race the next refinement.
    """

    detail: str
    plan: CoursePlan


class Identified(Protocol):
    """The shape the id reconciler needs: something with an id and a display title."""

    id: str
    title: str


def assign_ids(plan: CoursePlan, previous: CoursePlan | None = None) -> CoursePlan:
    """Return `plan` with server-assigned ids, reusing the previous plan's where it can.

    Stability matters more than tidiness here. A refinement returns the whole plan
    while the UI is still rendering the old one: if ids churn, every row remounts, a
    half-typed inline edit is lost, and a two-word change looks like a rewrite. So an
    item keeps its old id whenever it is recognisably the same item -- matched first
    on an id the previous plan really contained, then on its title, or on its URL for
    a resource, since that is what identifies a resource.

    Anything unrecognised gets the lowest free ordinal at its level. Ids the model
    made up are discarded: an id nothing on the server issued is not an identity.
    """
    previous_modules = previous.modules if previous else []
    module_ids = _reconcile_ids(plan.modules, previous_modules, "m")
    modules: list[Module] = []

    for module, module_id in zip(plan.modules, module_ids, strict=True):
        was = _module_with_id(previous_modules, module_id)
        previous_lessons = was.lessons if was else []
        lesson_ids = _reconcile_ids(module.lessons, previous_lessons, f"{module_id}-l")
        lessons: list[Lesson] = []

        for lesson, lesson_id in zip(module.lessons, lesson_ids, strict=True):
            lesson_was = _lesson_with_id(previous_lessons, lesson_id)
            previous_resources = lesson_was.resources if lesson_was else []
            resource_ids = _reconcile_ids(
                lesson.resources, previous_resources, f"{lesson_id}-r", key=_resource_key
            )
            resources = [
                resource.model_copy(update={"id": resource_id})
                for resource, resource_id in zip(lesson.resources, resource_ids, strict=True)
            ]
            lessons.append(lesson.model_copy(update={"id": lesson_id, "resources": resources}))

        modules.append(module.model_copy(update={"id": module_id, "lessons": lessons}))

    return plan.model_copy(update={"modules": modules})


def _resource_key(resource: Identified) -> str:
    """Two resources are the same resource when they point at the same place."""
    url = getattr(resource, "url", "")
    return url.strip().lower() or resource.title.strip().casefold()


def _title_key(item: Identified) -> str:
    return item.title.strip().casefold()


def _reconcile_ids(
    items: Sequence[Identified],
    previous: Sequence[Identified],
    prefix: str,
    key: Callable[[Identified], str] = _title_key,
) -> list[str]:
    """Match items to ids from `previous`, then fill the gaps with fresh ordinals."""
    known = {item.id for item in previous if item.id}
    by_key: dict[str, str] = {}
    for item in previous:
        if item.id:
            by_key.setdefault(key(item), item.id)

    claimed: list[str | None] = []
    used: set[str] = set()
    for item in items:
        match: str | None = None
        if item.id and item.id in known and item.id not in used:
            match = item.id
        else:
            candidate = by_key.get(key(item))
            if candidate and candidate not in used:
                match = candidate
        if match:
            used.add(match)
        claimed.append(match)

    settled: list[str] = []
    ordinal = 1
    for existing in claimed:
        if existing is not None:
            settled.append(existing)
            continue
        while f"{prefix}{ordinal}" in used:
            ordinal += 1
        fresh = f"{prefix}{ordinal}"
        used.add(fresh)
        settled.append(fresh)

    return settled


def _module_with_id(modules: Sequence[Module], module_id: str) -> Module | None:
    return next((module for module in modules if module.id == module_id), None)


def _lesson_with_id(lessons: Sequence[Lesson], lesson_id: str) -> Lesson | None:
    return next((lesson for lesson in lessons if lesson.id == lesson_id), None)
