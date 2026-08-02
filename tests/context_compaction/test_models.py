"""TDD contract for versioned context-compaction data models."""

from __future__ import annotations

from dataclasses import fields

import pytest

from context_compaction.models import (
    ActionRecord,
    ActionStatus,
    BudgetLimits,
    DegradedReason,
    DiagnosticEvent,
    GateState,
    Host,
    HookEvent,
    ToolClass,
    Trigger,
)


def test_budget_limits_reject_boolean_values():
    with pytest.raises(ValueError):
        BudgetLimits(reentry_chars=True)


def test_hook_event_rejects_unknown_internal_fields():
    with pytest.raises(ValueError, match="unknown fields"):
        HookEvent.from_dict(
            {
                "host": "codex",
                "host_version": "0.145.0",
                "event_name": "PreCompact",
                "cwd": "C:/repo",
                "unexpected": "poison",
            }
        )


def test_hook_event_has_typed_host_and_trigger():
    event = HookEvent.from_dict(
        {
            "host": "claude",
            "host_version": "2.1.220",
            "event_name": "PreCompact",
            "cwd": "C:/repo",
            "trigger": "manual",
        }
    )

    assert event.host is Host.CLAUDE
    assert event.trigger is Trigger.MANUAL


def test_action_record_serializes_metadata_only():
    action = ActionRecord(
        action_id="a1",
        tool_class=ToolClass.EXTERNAL_SIDE_EFFECT,
        tool_name="github.create_pull_request",
        input_fingerprint="0" * 64,
        status=ActionStatus.AWAITING_APPROVAL,
        started_at="2026-08-01T00:00:00Z",
    )

    serialized = action.to_dict()
    assert serialized["status"] == "awaiting_approval"
    assert set(serialized) == {
        "action_id",
        "tool_class",
        "tool_name",
        "input_fingerprint",
        "status",
        "started_at",
        "finished_at",
    }


def test_diagnostic_schema_cannot_hold_sensitive_bodies():
    names = {field.name for field in fields(DiagnosticEvent)}
    assert not names.intersection(
        {"path", "task_text", "summary", "command", "tool_output", "memory_text", "source", "diff"}
    )


def test_diagnostic_schema_holds_only_closed_registry_categories():
    event = DiagnosticEvent(
        event_id="event-1",
        host=Host.CLAUDE,
        host_version="2.1.220",
        trigger="startup",
        repository_fingerprint="0" * 64,
        outcome="rejected",
        changed_field_categories=("cache_state", "protected_top_level"),
    )

    assert event.to_dict()["changed_field_categories"] == [
        "cache_state",
        "protected_top_level",
    ]


@pytest.mark.parametrize(
    "categories",
    (
        ("invented_category",),
        ("ui_state", "cache_state"),
        ("cache_state", "cache_state"),
    ),
)
def test_diagnostic_schema_rejects_unknown_unsorted_or_duplicate_categories(
    categories: tuple[str, ...],
):
    with pytest.raises(ValueError, match="changed_field_categories"):
        DiagnosticEvent(
            event_id="event-1",
            host=Host.CLAUDE,
            host_version="2.1.220",
            trigger="startup",
            repository_fingerprint="0" * 64,
            outcome="rejected",
            changed_field_categories=categories,
        )


def test_closed_state_and_reason_vocabularies():
    assert GateState("validation_required") is GateState.VALIDATION_REQUIRED
    assert DegradedReason("state_stale") is DegradedReason.STATE_STALE
    with pytest.raises(ValueError):
        DegradedReason("invented_reason")
