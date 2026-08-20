"""The refinement guard, and the JSON extraction every structured call goes through."""

from __future__ import annotations

import json

import pytest

from app.llm.client import extract_json
from app.llm.planner import check_refinement
from app.schemas import CoursePlan, Lesson, Module


def plan(module_count: int, lessons_each: int = 2) -> CoursePlan:
    return CoursePlan(
        title="Course",
        modules=[
            Module(
                id=f"m{index}",
                title=f"Module {index}",
                lessons=[
                    Lesson(id=f"m{index}-l{n}", title=f"Lesson {n}")
                    for n in range(1, lessons_each + 1)
                ],
            )
            for index in range(1, module_count + 1)
        ],
    )


def drop_module(original: CoursePlan, module_id: str) -> CoursePlan:
    kept = [m for m in original.modules if m.id != module_id]
    return original.model_copy(update={"modules": kept})


def test_an_untouched_plan_passes() -> None:
    original = plan(4)

    assert check_refinement(original, original, "make module 2 simpler") is None


def test_an_edit_inside_a_module_passes() -> None:
    original = plan(4)
    edited = original.model_copy(
        update={
            "modules": [
                m.model_copy(update={"title": "Module 2, gentler"}) if m.id == "m2" else m
                for m in original.modules
            ]
        }
    )

    assert check_refinement(original, edited, "make module 2 simpler") is None


def test_an_empty_plan_is_refused() -> None:
    gutted = plan(4).model_copy(update={"modules": []})

    problem = check_refinement(plan(4), gutted, "make module 2 simpler")

    assert problem is not None
    assert "no modules" in problem


def test_a_module_lost_without_being_asked_for_is_refused() -> None:
    original = plan(4)

    problem = check_refinement(original, drop_module(original, "m3"), "add a project to module 1")

    assert problem is not None
    assert "Module 3" in problem


def test_a_module_the_mentor_asked_to_remove_may_go() -> None:
    original = plan(4)

    assert check_refinement(original, drop_module(original, "m3"), "remove module 3") is None


def test_a_collapse_is_refused_even_when_removal_was_requested() -> None:
    """Asking to drop module 3 is not permission to keep one module out of five."""
    original = plan(5)
    survivor = original.model_copy(update={"modules": original.modules[:1]})

    problem = check_refinement(original, survivor, "drop module 3")

    assert problem is not None
    assert "1 of your 5 modules" in problem


def test_lessons_gutted_without_a_request_is_refused() -> None:
    original = plan(3, lessons_each=4)
    thinned = original.model_copy(
        update={"modules": [m.model_copy(update={"lessons": m.lessons[:1]}) for m in original.modules]}
    )

    problem = check_refinement(original, thinned, "add a capstone project")

    assert problem is not None
    assert "12 lessons down to 3" in problem


@pytest.mark.parametrize(
    "raw",
    [
        '{"title": "Course"}',
        '```json\n{"title": "Course"}\n```',
        '```\n{"title": "Course"}\n```',
        'Here is the plan you asked for:\n\n{"title": "Course"}\n\nHope that helps!',
        '  \n{"title": "Course"}\n',
    ],
)
def test_json_survives_fences_and_chatter(raw: str) -> None:
    assert extract_json(raw) == {"title": "Course"}


def test_nested_braces_are_not_truncated() -> None:
    payload = {"modules": [{"lessons": [{"title": "Loops"}]}]}

    assert extract_json(f"Sure!\n{json.dumps(payload)}") == payload


def test_output_with_no_object_at_all_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        extract_json("I could not build that plan.")
