"""Claude host-registry semantic guard contracts (Refresh 3/4 TDD)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_compaction.claude_registry import (
    ClaudeRegistryError,
    ClaudeRegistryGuard,
)


def _write_registry(
    path: Path,
    *,
    startups: int = 30,
    target: Path | None = None,
    trusted: bool = True,
    existing_value: str = "BODY-MUST-NOT-PERSIST",
) -> dict[str, object]:
    projects: dict[str, object] = {
        r"C:\existing-project": {
            "hasTrustDialogAccepted": True,
            "privateValue": existing_value,
        }
    }
    if target is not None:
        projects[str(target)] = {
            "hasTrustDialogAccepted": trusted,
            "sessionMetrics": {"cost": 1.25},
        }
    value: dict[str, object] = {
        "numStartups": startups,
        "projects": projects,
        "cachedFeature": {"enabled": True, "privateValue": existing_value},
    }
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return value


def test_allowed_startup_then_manual_trust_is_semantically_valid(tmp_path: Path):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    baseline = _write_registry(registry)
    guard = ClaudeRegistryGuard.capture(registry, repository)

    startup = dict(baseline)
    startup["numStartups"] = 31
    registry.write_text(json.dumps(startup, separators=(",", ":")), encoding="utf-8")
    partial = guard.validate_current(final=False)

    projects = dict(startup["projects"])
    projects[str(repository.resolve())] = {
        "hasTrustDialogAccepted": True,
        "sessionMetrics": {"cost": 3.5},
    }
    trusted = {**startup, "projects": projects}
    registry.write_text(json.dumps(trusted, sort_keys=True), encoding="utf-8")
    final = guard.validate_current(final=True)

    assert partial.change_names == ("num_startups",)
    assert final.change_names == ("num_startups", "target_project_trust")
    assert final.target_trusted is True


def test_manifest_and_observation_are_content_free(tmp_path: Path):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    baseline = _write_registry(registry)
    guard = ClaudeRegistryGuard.capture(registry, repository)
    projects = dict(baseline["projects"])
    projects[str(repository.resolve())] = {"hasTrustDialogAccepted": True}
    registry.write_text(
        json.dumps({**baseline, "numStartups": 31, "projects": projects}),
        encoding="utf-8",
    )

    serialized = json.dumps(
        {
            "manifest": guard.manifest.to_dict(),
            "observation": guard.validate_current(final=True).to_dict(),
        },
        sort_keys=True,
    )

    assert "BODY-MUST-NOT-PERSIST" not in serialized
    assert str(repository) not in serialized
    assert str(registry) not in serialized
    assert "existing-project" not in serialized
    assert len(guard.manifest.manifest_sha256) == 64


def test_semantic_drift_reports_only_sorted_closed_categories(tmp_path: Path):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    value = _write_registry(registry)
    guard = ClaudeRegistryGuard.capture(registry, repository)
    value["cachedFeature"] = {"enabled": False}
    value["projects"][r"C:\existing-project"]["privateValue"] = "changed"
    registry.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ClaudeRegistryError) as drift:
        guard.validate_current(final=False)

    assert drift.value.code == "registry_semantic_drift"
    assert drift.value.changed_field_categories == (
        "existing_project_state",
        "feature_state",
    )


@pytest.mark.parametrize(
    ("field_name", "expected_category"),
    (
        ("clientDataCacheSlots", "cache_state"),
        ("oauthAccount", "authentication_metadata"),
        ("cachedGrowthBookFeatures", "feature_state"),
        ("usageHistory", "usage_state"),
        ("hasSeenOnboarding", "ui_state"),
    ),
)
def test_known_protected_field_families_use_closed_categories(
    tmp_path: Path, field_name: str, expected_category: str
):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    value = _write_registry(registry)
    value[field_name] = {"state": "before"}
    registry.write_text(json.dumps(value), encoding="utf-8")
    guard = ClaudeRegistryGuard.capture(registry, repository)
    value[field_name] = {"state": "after"}
    registry.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ClaudeRegistryError) as drift:
        guard.validate_current(final=False)

    assert drift.value.changed_field_categories == (expected_category,)


def test_unknown_field_identity_value_and_fingerprint_never_leave_error(tmp_path: Path):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    field_name = "SECRET-FIELD-NAME"
    before = "PRIVATE-BEFORE-VALUE"
    after = "PRIVATE-AFTER-VALUE"
    value = _write_registry(registry)
    value[field_name] = before
    registry.write_text(json.dumps(value), encoding="utf-8")
    guard = ClaudeRegistryGuard.capture(registry, repository)
    value[field_name] = after
    registry.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ClaudeRegistryError) as drift:
        guard.validate_current(final=False)

    serialized = json.dumps(
        {
            "code": drift.value.code,
            "categories": drift.value.changed_field_categories,
            "message": str(drift.value),
        },
        sort_keys=True,
    )
    assert drift.value.changed_field_categories == ("protected_top_level",)
    assert field_name not in serialized
    assert before not in serialized
    assert after not in serialized
    assert guard.manifest.semantic_sha256 not in serialized


def test_final_rejection_retains_protected_drift_categories_without_changing_code(
    tmp_path: Path,
):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    value = _write_registry(registry)
    guard = ClaudeRegistryGuard.capture(registry, repository)
    value["cachedFeature"] = {"enabled": False}
    registry.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ClaudeRegistryError) as rejected:
        guard.validate_current(final=True)

    assert rejected.value.code == "target_project_missing"
    assert rejected.value.changed_field_categories == ("feature_state",)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value, _repo: value.update(numStartups=32),
        lambda value, _repo: value.update(cachedFeature={"enabled": False}),
        lambda value, _repo: value["projects"][r"C:\existing-project"].update(
            privateValue="changed"
        ),
    ),
)
def test_unapproved_semantic_delta_is_rejected_and_never_reverted(
    tmp_path: Path, mutation
):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    value = _write_registry(registry)
    guard = ClaudeRegistryGuard.capture(registry, repository)
    value["numStartups"] = 31
    mutation(value, repository)
    changed = json.dumps(value, sort_keys=True)
    registry.write_text(changed, encoding="utf-8")

    with pytest.raises(ClaudeRegistryError):
        guard.validate_current(final=False)

    assert registry.read_text(encoding="utf-8") == changed


@pytest.mark.parametrize("trusted", (False, None))
def test_final_state_requires_exact_new_trusted_project(tmp_path: Path, trusted):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    value = _write_registry(registry)
    guard = ClaudeRegistryGuard.capture(registry, repository)
    value["numStartups"] = 31
    if trusted is not None:
        value["projects"][str(repository.resolve())] = {
            "hasTrustDialogAccepted": trusted
        }
    registry.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ClaudeRegistryError):
        guard.validate_current(final=True)


def test_preexisting_target_or_malformed_registry_refuses_capture(tmp_path: Path):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    _write_registry(registry, target=repository.resolve())
    with pytest.raises(ClaudeRegistryError):
        ClaudeRegistryGuard.capture(registry, repository)

    registry.write_text('{"numStartups":30,"numStartups":31}', encoding="utf-8")
    with pytest.raises(ClaudeRegistryError):
        ClaudeRegistryGuard.capture(registry, repository)


def test_missing_registry_refuses_capture_without_creating_it(tmp_path: Path):
    registry = tmp_path / ".claude.json"
    repository = tmp_path / "allowed-repo"
    repository.mkdir()

    with pytest.raises(ClaudeRegistryError):
        ClaudeRegistryGuard.capture(registry, repository)

    assert not registry.exists()
