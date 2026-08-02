"""TDD contract for bounded context allocation."""

from __future__ import annotations

import pytest

from context_compaction.budget import (
    BudgetCategory,
    allocate_categories,
    estimate_tokens,
    truncate_text,
)


def test_estimator_is_conservative_for_ascii_runs_and_non_ascii():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2
    assert estimate_tokens("é") == 1
    assert estimate_tokens("abcdéabcd") == 3


def test_exact_limit_is_included_without_truncation():
    result = allocate_categories(
        [BudgetCategory("status", "abcd", priority=0)],
        max_chars=4,
        max_tokens=1,
    )

    assert result.text == "abcd"
    assert result.used_chars == 4
    assert result.estimated_tokens == 1
    assert result.included_categories == ("status",)
    assert result.omitted_categories == ()
    assert result.truncated is False


def test_required_category_truncates_at_both_limits():
    result = allocate_categories(
        [BudgetCategory("goal", "abcdefghij", priority=0, required=True)],
        max_chars=5,
        max_tokens=2,
    )

    assert len(result.text) <= 5
    assert estimate_tokens(result.text) <= 2
    assert result.included_categories == ("goal",)
    assert result.omitted_categories == ()
    assert result.truncated is True


def test_priority_wins_over_input_order_and_omissions_are_explicit():
    result = allocate_categories(
        [
            BudgetCategory("optional", "1234", priority=20),
            BudgetCategory("authority", "abcd", priority=0),
        ],
        max_chars=4,
        max_tokens=1,
    )

    assert result.text == "abcd"
    assert result.included_categories == ("authority",)
    assert result.omitted_categories == ("optional",)
    assert result.truncated is True


def test_all_non_ascii_is_token_bounded():
    assert truncate_text("界界界界", max_chars=10, max_tokens=2) == "界界"


@pytest.mark.parametrize(
    "name",
    ["raw_tool_output", "transcript_body", "source_body", "full_diff", "secret"],
)
def test_sensitive_categories_are_rejected(name):
    with pytest.raises(ValueError, match="forbidden budget category"):
        BudgetCategory(name, "must not serialize", priority=1)


def test_allocation_is_deterministic():
    categories = [
        BudgetCategory("goal", "same", priority=1),
        BudgetCategory("task", "same", priority=1),
    ]
    assert allocate_categories(categories).to_dict() == allocate_categories(categories).to_dict()
