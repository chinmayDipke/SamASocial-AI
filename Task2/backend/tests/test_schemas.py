"""Server-assigned ids.

The UI keys every editable row off its id and PUTs the whole plan back, so these
tests are really about one promise: an item that survives a refinement keeps the id
it had. Cases are the ones a model actually produces -- ids invented, ids omitted,
ids echoed back, items reordered, items inserted.
"""

from __future__ import annotations

from app.schemas import CoursePlan, Lesson, Module, Resource, assign_ids


def plan(*modules: Module) -> CoursePlan:
    return CoursePlan(title="Course", modules=list(modules))


def module(title: str, *lessons: Lesson, module_id: str = "") -> Module:
    return Module(id=module_id, title=title, lessons=list(lessons))


def lesson(title: str, *resources: Resource, lesson_id: str = "") -> Lesson:
    return Lesson(id=lesson_id, title=title, resources=list(resources))


def resource(title: str, url: str) -> Resource:
    return Resource(title=title, url=url)


def module_ids(assigned: CoursePlan) -> list[str]:
    return [m.id for m in assigned.modules]


def test_a_fresh_plan_is_numbered_from_one() -> None:
    assigned = assign_ids(
        plan(
            module("Foundations", lesson("Variables", resource("Docs", "https://a.dev"))),
            module("Control flow", lesson("Loops"), lesson("Branches")),
        )
    )

    assert module_ids(assigned) == ["m1", "m2"]
    assert [le.id for le in assigned.modules[0].lessons] == ["m1-l1"]
    assert [r.id for r in assigned.modules[0].lessons[0].resources] == ["m1-l1-r1"]
    assert [le.id for le in assigned.modules[1].lessons] == ["m2-l1", "m2-l2"]


def test_ids_the_model_invented_are_discarded() -> None:
    """Nothing on the server issued "module-two", so it is not an identity."""
    assigned = assign_ids(plan(module("Foundations", module_id="module-two")))

    assert module_ids(assigned) == ["m1"]


def test_surviving_items_keep_their_ids_when_a_module_is_inserted() -> None:
    first = assign_ids(plan(module("Foundations"), module("Control flow")))
    refined = assign_ids(
        plan(
            module("Foundations", module_id="m1"),
            module("Warm-up"),
            module("Control flow", module_id="m2"),
        ),
        previous=first,
    )

    assert module_ids(refined) == ["m1", "m3", "m2"]


def test_a_module_is_recognised_by_title_when_the_model_drops_the_id() -> None:
    first = assign_ids(plan(module("Foundations"), module("Control flow")))
    refined = assign_ids(
        plan(module("control FLOW "), module("Foundations")),
        previous=first,
    )

    assert module_ids(refined) == ["m2", "m1"]


def test_lesson_and_resource_ids_are_kept_inside_a_surviving_module() -> None:
    first = assign_ids(
        plan(module("Foundations", lesson("Variables", resource("Docs", "https://a.dev"))))
    )
    refined = assign_ids(
        plan(
            module(
                "Foundations",
                lesson("Setting up"),
                lesson("Variables", resource("Docs, revisited", "https://a.dev")),
                module_id="m1",
            )
        ),
        previous=first,
    )

    lessons = refined.modules[0].lessons
    assert [le.id for le in lessons] == ["m1-l2", "m1-l1"]
    # The resource moved and was renamed, but it is still the same URL.
    assert lessons[1].resources[0].id == "m1-l1-r1"


def test_a_repeated_id_is_only_honoured_once() -> None:
    first = assign_ids(plan(module("Foundations")))
    refined = assign_ids(
        plan(module("Foundations", module_id="m1"), module("Copy", module_id="m1")),
        previous=first,
    )

    assert module_ids(refined) == ["m1", "m2"]


def test_the_plan_round_trips_through_json() -> None:
    original = assign_ids(
        plan(module("Foundations", lesson("Variables", resource("Docs", "https://a.dev"))))
    )

    restored = CoursePlan.model_validate(original.model_dump(mode="json"))

    assert restored == original
    assert [r.id for r in restored.resources] == ["m1-l1-r1"]
