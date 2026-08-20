"""The intake checklist and the rules that stop a routing step losing information."""

from __future__ import annotations

import pytest

from app.llm.intake import IntakeDraft, fallback_action, merge_intake
from app.schemas import CoursePlan, Intake, Module


def draft(**fields: object) -> IntakeDraft:
    return IntakeDraft.model_validate(fields)


def test_a_new_intake_is_missing_everything_in_asking_order() -> None:
    assert Intake().missing == ["subject", "audience", "duration", "goals"]
    assert Intake().is_complete is False


def test_a_full_intake_is_complete() -> None:
    intake = Intake(
        subject="Python for data analysis",
        audience="Year 9, no prior coding",
        duration="6 weeks, one 90-minute session",
        goals=["Clean a messy CSV"],
    )

    assert intake.missing == []
    assert intake.is_complete is True


@pytest.mark.parametrize("value", ["", "   "])
def test_whitespace_does_not_fill_a_slot(value: str) -> None:
    assert "subject" in Intake(subject=value).missing


def test_an_empty_goal_does_not_fill_the_goals_slot() -> None:
    assert "goals" in Intake(goals=["", "  "]).missing


def test_a_slot_the_model_forgot_is_not_unset() -> None:
    """The read step must not be able to un-tick the checklist."""
    current = Intake(subject="Algebra", audience="Year 8", goals=["Solve for x"])

    merged, changed = merge_intake(current, draft(subject="Algebra"))

    assert merged.audience == "Year 8"
    assert merged.goals == ["Solve for x"]
    assert changed is False


def test_the_mentor_can_still_correct_a_slot() -> None:
    current = Intake(subject="Algebra", audience="Year 8")

    merged, changed = merge_intake(current, draft(audience="Adult evening class"))

    assert merged.audience == "Adult evening class"
    assert merged.subject == "Algebra"
    assert changed is True


def test_blank_goals_are_dropped_before_they_reach_the_checklist() -> None:
    merged, _ = merge_intake(Intake(), draft(goals=["Read a stack trace", "  ", ""]))

    assert merged.goals == ["Read a stack trace"]


def test_fallback_asks_while_the_brief_is_incomplete() -> None:
    assert fallback_action(Intake(subject="Algebra"), None) == "ask"


def test_fallback_generates_once_the_brief_is_complete() -> None:
    complete = Intake(subject="Algebra", audience="Year 8", duration="6 weeks", goals=["x"])

    assert fallback_action(complete, None) == "generate"


def test_fallback_never_edits_a_plan_on_a_guess() -> None:
    """Answering badly costs a sentence; editing on a guess costs the mentor's work."""
    plan = CoursePlan(title="Algebra", modules=[Module(id="m1", title="Foundations")])

    assert fallback_action(Intake(), plan) == "answer"
