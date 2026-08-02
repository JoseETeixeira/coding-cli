"""The registry census must stay read-only and agree with the guard it advises."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from context_compaction.claude_registry import _field_category
from context_compaction.registry_census import (
    _changed,
    _read_with_retry,
    _snapshot,
    run_census,
)


def _registry(tmp_path: Path, **overrides: object) -> Path:
    body: dict[str, object] = {
        "numStartups": 30,
        "projects": {"C:\\repo\\other": {"hasTrustDialogAccepted": True}},
        "cachedGrowthBookFeaturesAt": 1_754_000_000_000,
        "cachedGrowthBookFeatures": {"flag": True},
        "oauthAccount": {"accountUuid": "unchanged"},
        "theme": "dark",
    }
    body.update(overrides)
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / ".claude.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_census_reports_the_growthbook_timestamp_the_guard_rejects(tmp_path: Path):
    """The identified Task 10 blocker, reproduced offline against the guard's helpers."""
    before = _snapshot(_registry(tmp_path / "a", **{}), "")
    after = _snapshot(
        _registry(tmp_path / "b", cachedGrowthBookFeaturesAt=1_754_000_999_999), ""
    )

    changed = _changed(before[1], after[1])

    assert changed == ["cachedGrowthBookFeaturesAt"]
    assert _field_category(changed[0]).value == "feature_state"
    assert before[0] != after[0]  # protected semantic hash moved -> guard rejects


def test_census_ignores_the_exempt_startup_counter(tmp_path: Path):
    """ADR 0013 allows `numStartups`; a census that flagged it would be lying."""
    before = _snapshot(_registry(tmp_path / "a"), "")
    after = _snapshot(_registry(tmp_path / "b", numStartups=31), "")

    assert _changed(before[1], after[1]) == []
    assert before[0] == after[0]
    assert after[2] - before[2] == 1


def test_census_exempts_the_allowlisted_target_project_subtree(tmp_path: Path):
    """A newly trusted target is the approved delta, not drift."""
    target = str(tmp_path / "repo")
    before = _snapshot(_registry(tmp_path / "a"), target)
    after = _snapshot(
        _registry(
            tmp_path / "b",
            projects={
                "C:\\repo\\other": {"hasTrustDialogAccepted": True},
                target: {"hasTrustDialogAccepted": True},
            },
        ),
        target,
    )

    assert _changed(before[1], after[1]) == []
    assert before[0] == after[0]


def test_census_survives_a_torn_read(tmp_path: Path):
    """The host rewrites this file while we poll; half a document is expected."""
    path = tmp_path / ".claude.json"
    path.write_text('{"numStartups": 30, "proj', encoding="utf-8")

    assert _read_with_retry(path, "", attempts=2, pause=0.0) is None


def test_census_is_read_only_and_reports_clean_when_nothing_moves(tmp_path: Path):
    registry = _registry(tmp_path)
    before = hashlib.sha256(registry.read_bytes()).hexdigest()

    result = run_census(registry, "", duration=0.3, interval=0.05)

    assert result["clean"] is True
    assert result["observations"] == []
    assert hashlib.sha256(registry.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [".claude.json"]
