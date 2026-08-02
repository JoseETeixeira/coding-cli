"""Isolated activation and rollback contracts."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from context_compaction import cli as cli_module
from context_compaction.activation import (
    ActivationError,
    ActivationManager,
    ActivationState,
)
from context_compaction.adapters import ToolCapability
from context_compaction.cli import build_parser
from context_compaction.models import DegradedReason, Host
from context_compaction.repository import repository_fingerprint
from context_compaction.storage import StateStore

ROOT = Path(__file__).parents[2]


def _capabilities() -> tuple[ToolCapability, ...]:
    return (
        ToolCapability("Bash", write_capable=True, hook_observable=True),
        ToolCapability("apply_patch", write_capable=True, hook_observable=True),
        ToolCapability("Read", write_capable=False, hook_observable=True),
    )


def _manager(tmp_path: Path, *, versions=None) -> tuple[ActivationManager, Path, Path]:
    codex_home = tmp_path / "codex-home"
    app_data = tmp_path / "app-data"
    bin_dir = tmp_path / "bin"
    codex_home.mkdir()
    app_data.mkdir()
    bin_dir.mkdir()
    codex_exe = bin_dir / "codex.exe"
    claude_exe = bin_dir / "claude.exe"
    python_exe = bin_dir / "python.exe"
    codex_exe.write_bytes(b"synthetic codex executable")
    claude_exe.write_bytes(b"synthetic claude executable")
    python_exe.write_bytes(b"synthetic python executable")
    (tmp_path / "claude.json").write_text(
        json.dumps(
            {
                "numStartups": 10,
                "projects": {
                    r"C:\existing-project": {"hasTrustDialogAccepted": True}
                },
            }
        ),
        encoding="utf-8",
    )
    if os.name == "nt":
        resources = tmp_path / "codex-resources"
        resources.mkdir()
        (resources / "codex-windows-sandbox-setup.exe").write_bytes(b"setup")
        (resources / "codex-command-runner.exe").write_bytes(b"runner")
    detected = versions or {Host.CODEX: "0.145.0", Host.CLAUDE: "2.1.220"}
    manager = ActivationManager(
        source_root=ROOT,
        codex_home=codex_home,
        app_data=app_data,
        executables={Host.CODEX: codex_exe, Host.CLAUDE: claude_exe},
        version_provider=lambda host, _path: detected[host],
        python_executable=python_exe,
        claude_registry=tmp_path / "claude.json",
    )
    return manager, codex_home, app_data


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "allowed-repo"
    repository.mkdir()
    return repository


def _codex_trust_state(target: Path, *, enabled: bool | None = None) -> str:
    value = "[hooks.state]\n\n"
    for index, event in enumerate(
        (
            "pre_tool_use",
            "post_tool_use",
            "pre_compact",
            "post_compact",
            "session_start",
        ),
        start=1,
    ):
        value += (
            f"[hooks.state.'{target}:{event}:0:0']\n"
            f'trusted_hash = "sha256:{index:064x}"\n\n'
        )
        if index == 1 and enabled is not None:
            value = value[:-1] + f"enabled = {str(enabled).lower()}\n\n"
    return value


def test_plan_is_read_only_and_names_exact_codex_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manager, codex_home, app_data = _manager(tmp_path)
    repo = _repository(tmp_path)
    base = codex_home / "config.toml"
    base.write_text("# unrelated comment\nmodel = 'existing'\n", encoding="utf-8")
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    plan = manager.plan(
        Host.CODEX,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert after == before
    assert plan.state is ActivationState.READY
    assert [item.path.name for item in plan.files] == [
        "context-pilot.config.toml",
        "codex.allowlist.json",
    ]
    assert all(item.mutation == "create" for item in plan.files)
    assert len(plan.plan_sha256) == 64
    profile = plan.files[0].content
    assert "model_auto_compact_token_limit = 64000" in profile
    assert 'model_auto_compact_token_limit_scope = "body_after_prefix"' in profile
    assert "tool_output_token_limit = 12000" in profile
    assert 'web_search = "disabled"' in profile
    assert "apps = false" in profile
    assert "browser_use = false" in profile
    assert "browser_use_external = false" in profile
    assert "browser_use_full_cdp_access = false" in profile
    assert "computer_use = false" in profile
    assert "image_generation = false" in profile
    assert "in_app_browser = false" in profile
    assert "skill_mcp_dependency_install = false" in profile
    assert "PreCompact" in profile and "SessionStart" in profile
    assert profile.count("--expected-event") == 10
    for event in ("PreCompact", "PostCompact", "SessionStart", "PreToolUse", "PostToolUse"):
        assert profile.count(f"--expected-event {event}") == 2
    if os.name == "nt":
        resource_path = str(tmp_path / "codex-resources")
        assert tuple(map(str, plan.launch.path_prepend)) == (resource_path,)
        assert plan.launch.environment == {}
        monkeypatch.setenv("PATH", "ambient-path-may-change")
        repeated = manager.plan(
            Host.CODEX,
            repo,
            task_slug="pilot-task",
            capabilities=_capabilities(),
            hook_trusted=True,
        )
        assert repeated.plan_sha256 == plan.plan_sha256
    assert base.read_text(encoding="utf-8") == "# unrelated comment\nmodel = 'existing'\n"
    assert not (app_data / "context-compaction").exists()


def test_codex_enable_is_approved_idempotent_and_preserves_base(tmp_path: Path):
    manager, codex_home, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    base = codex_home / "config.toml"
    original = "# keep this comment\n[mcp_servers.existing]\ncommand='keep'\n"
    base.write_text(original, encoding="utf-8")
    plan = manager.plan(
        Host.CODEX, repo, task_slug="pilot-task", capabilities=_capabilities(), hook_trusted=True
    )

    with pytest.raises(ActivationError, match="approved plan hash"):
        manager.enable(plan, approved_plan_hash="0" * 64)
    result = manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    repeated = manager.enable(
        manager.plan(
            Host.CODEX,
            repo,
            task_slug="pilot-task",
            capabilities=_capabilities(),
            hook_trusted=True,
        ),
        approved_plan_hash=manager.plan(
            Host.CODEX,
            repo,
            task_slug="pilot-task",
            capabilities=_capabilities(),
            hook_trusted=True,
        ).plan_sha256,
    )

    assert result.state is ActivationState.ENABLED_UNOBSERVED
    assert repeated.state is ActivationState.ENABLED_UNOBSERVED
    assert base.read_text(encoding="utf-8") == original
    assert (codex_home / "context-pilot.config.toml").is_file()


@pytest.mark.parametrize("enabled", (None, True))
def test_codex_normal_hook_trust_suffix_stays_owned_without_synthesizing_trust(
    tmp_path: Path, enabled: bool | None
):
    manager, codex_home, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CODEX,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    target = codex_home / "context-pilot.config.toml"
    generated = target.read_text(encoding="utf-8")
    assert "[hooks.state]" not in generated

    target.write_text(
        generated + _codex_trust_state(target, enabled=enabled), encoding="utf-8"
    )

    trusted = manager.plan(
        Host.CODEX,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    status = manager.status(Host.CODEX, repository_root=repo)
    assert trusted.state is ActivationState.ENABLED_UNOBSERVED
    assert trusted.files[0].mutation == "none"
    assert trusted.degraded_reasons == ()
    assert manager.run(trusted, launcher=lambda _args, _env: 0) == 0
    assert status["state"] == "enabled_unobserved"
    assert status["owned_target_count"] == 2
    assert status["drifted_target_count"] == 0

    result = manager.disable(Host.CODEX)
    assert result.changed_target_count == 2
    assert not target.exists()


@pytest.mark.parametrize(
    "corruption",
    (
        lambda value: value.replace("session_start", "unknown_event"),
        lambda value: value.replace("sha256:000", "sha256:ABC", 1),
        lambda value: value + "unexpected = true\n",
        lambda value: value.replace("enabled = true", "enabled = false"),
    ),
)
def test_codex_hook_trust_suffix_rejects_non_host_shape(tmp_path: Path, corruption):
    manager, codex_home, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CODEX,
        repo,
        task_slug=None,
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    target = codex_home / "context-pilot.config.toml"
    generated = target.read_text(encoding="utf-8")
    target.write_text(
        generated + corruption(_codex_trust_state(target, enabled=True)),
        encoding="utf-8",
    )

    conflict = manager.plan(
        Host.CODEX,
        repo,
        task_slug=None,
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    assert conflict.state is ActivationState.CONFLICT
    with pytest.raises(ActivationError, match="drifted"):
        manager.disable(Host.CODEX)


def test_claude_overlay_and_launcher_are_process_local(tmp_path: Path):
    manager, _, app_data = _manager(tmp_path)
    repo = _repository(tmp_path)
    user_settings = tmp_path / "claude-home" / "settings.json"
    user_settings.parent.mkdir()
    original = json.dumps({"hooks": {"Stop": [{"keep": True}]}, "theme": "dark"}, indent=2)
    user_settings.write_text(original, encoding="utf-8")

    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)

    overlay_path = app_data / "context-compaction" / "claude-context-pilot.settings.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert overlay["autoCompactEnabled"] is True
    assert set(overlay["hooks"]) == {
        "PreCompact",
        "PostCompact",
        "SessionStart",
        "PreToolUse",
        "PostToolUse",
    }
    for event, registrations in overlay["hooks"].items():
        assert registrations[0]["hooks"][0]["command"].endswith(
            f"--expected-event {event}"
        )
    assert user_settings.read_text(encoding="utf-8") == original
    assert "--settings" in plan.launch.arguments
    assert "--append-system-prompt-file" in plan.launch.arguments
    assert plan.launch.environment == {
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "100000",
        "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80",
    }


def test_generated_hook_entry_runs_from_unrelated_repository_and_denies_inventory_drift(
    tmp_path: Path,
):
    codex_home = tmp_path / "codex-home"
    app_data = tmp_path / "app-data"
    bin_dir = tmp_path / "bin"
    codex_home.mkdir()
    app_data.mkdir()
    bin_dir.mkdir()
    claude_exe = bin_dir / "claude.exe"
    claude_exe.write_bytes(b"synthetic claude executable")
    manager = ActivationManager(
        source_root=ROOT,
        codex_home=codex_home,
        app_data=app_data,
        executables={Host.CLAUDE: claude_exe},
        version_provider=lambda _host, _path: "2.1.220",
        python_executable=sys.executable,
    )
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug=None,
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    overlay = json.loads(plan.files[0].content)
    command = overlay["hooks"]["PreCompact"][0]["hooks"][0]["command"]
    assert "hook_entry.py" in command
    compact = subprocess.run(
        command,
        cwd=repo,
        shell=True,
        input=json.dumps(
            {
                "session_id": "integration-session",
                "cwd": str(repo),
                "hook_event_name": "PreCompact",
                "trigger": "manual",
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
        env={**os.environ, "PYTHONPATH": ""},
    )
    assert compact.returncode == 0
    assert json.loads(compact.stdout) == {"continue": True}

    pretool_command = overlay["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    uncovered = subprocess.run(
        pretool_command,
        cwd=repo,
        shell=True,
        input=json.dumps(
            {
                "session_id": "integration-session",
                "cwd": str(repo),
                "hook_event_name": "PreToolUse",
                "tool_name": "hosted.deploy",
                "tool_use_id": "uncovered-1",
                "tool_input": {},
            }
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
        env={**os.environ, "PYTHONPATH": ""},
    )
    denial = json.loads(uncovered.stdout)
    assert uncovered.returncode == 0
    assert denial["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert denial["hookSpecificOutput"]["permissionDecisionReason"] == "uncovered_tool"

    StateStore(
        repo, fallback_base=app_data / "context-compaction" / "state"
    ).purge()
    manager.disable(Host.CLAUDE)


@pytest.mark.parametrize(
    ("host", "version", "reason"),
    [
        (Host.CODEX, "0.999.0", DegradedReason.UNSUPPORTED_HOST_VERSION),
        (Host.CLAUDE, "9.9.9", DegradedReason.UNSUPPORTED_HOST_VERSION),
    ],
)
def test_unsupported_version_refuses_activation(tmp_path: Path, host, version, reason):
    manager, _, _ = _manager(
        tmp_path, versions={Host.CODEX: version, Host.CLAUDE: version}
    )
    plan = manager.plan(
        host,
        _repository(tmp_path),
        task_slug=None,
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    assert plan.state is ActivationState.INACTIVE
    assert reason in plan.degraded_reasons


def test_untrusted_hook_and_uncovered_write_tool_refuse_activation(tmp_path: Path):
    manager, _, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    untrusted = manager.plan(
        Host.CODEX,
        repo,
        task_slug=None,
        capabilities=_capabilities(),
        hook_trusted=False,
    )
    uncovered = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug=None,
        capabilities=(ToolCapability("hosted.deploy", True, False),),
        hook_trusted=True,
    )
    assert untrusted.state is ActivationState.INACTIVE
    assert DegradedReason.INACTIVE_OR_UNTRUSTED_HOOK in untrusted.degraded_reasons
    assert uncovered.state is ActivationState.INACTIVE
    assert DegradedReason.ACTIVATION_CONFLICT in uncovered.degraded_reasons


def test_unowned_conflict_and_owned_drift_are_never_overwritten(tmp_path: Path):
    manager, codex_home, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    target = codex_home / "context-pilot.config.toml"
    target.write_text("unrelated = true\n", encoding="utf-8")
    conflict = manager.plan(
        Host.CODEX, repo, task_slug=None, capabilities=_capabilities(), hook_trusted=True
    )
    assert conflict.state is ActivationState.CONFLICT
    with pytest.raises(ActivationError):
        manager.enable(conflict, approved_plan_hash=conflict.plan_sha256)
    assert target.read_text(encoding="utf-8") == "unrelated = true\n"

    target.unlink()
    ready = manager.plan(
        Host.CODEX, repo, task_slug=None, capabilities=_capabilities(), hook_trusted=True
    )
    manager.enable(ready, approved_plan_hash=ready.plan_sha256)
    target.write_text(target.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
    with pytest.raises(ActivationError) as drift:
        manager.disable(Host.CODEX)
    assert drift.value.reason is DegradedReason.OWNED_FILE_DRIFT
    assert target.exists()


def test_disable_removes_only_owned_activation_and_not_state(tmp_path: Path):
    manager, codex_home, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    unrelated = codex_home / "keep.txt"
    unrelated.write_text("keep\n", encoding="utf-8")
    plan = manager.plan(
        Host.CODEX, repo, task_slug=None, capabilities=_capabilities(), hook_trusted=True
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    store = StateStore(repo, fallback_base=tmp_path / "fallback")
    store.write_current(
        {
            "schema_version": 1,
            "event_id": "event",
            "repository_fingerprint": repository_fingerprint(repo),
        }
    )

    result = manager.disable(Host.CODEX)

    assert result.state is ActivationState.INACTIVE
    assert unrelated.read_text(encoding="utf-8") == "keep\n"
    assert store.read_current() is not None
    assert not (codex_home / "context-pilot.config.toml").exists()


def test_status_is_bounded_and_contains_no_absolute_paths(tmp_path: Path):
    manager, _, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    status = manager.status(Host.CLAUDE, repository_root=repo)
    serialized = json.dumps(status, sort_keys=True)
    assert len(serialized) <= 8_000
    assert str(tmp_path) not in serialized
    assert status["measurement_source"] == "unmeasured"
    assert status["state"] == "inactive"
    assert status["activation_observed"] is False
    assert status["tool_inventory_enforced"] is False


def test_enabled_status_is_unobserved_until_a_lifecycle_event_is_observed(
    tmp_path: Path,
):
    manager, _, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)

    status = manager.status(Host.CLAUDE, repository_root=repo)

    assert status["state"] == "enabled_unobserved"
    assert status["activation_observed"] is False
    assert status["tool_inventory_enforced"] is True
    assert status["observable_tool_count"] == 3

    enabled_plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    assert enabled_plan.state is ActivationState.ENABLED_UNOBSERVED
    def trusted_launch(_args, _env):
        registry = tmp_path / "claude.json"
        value = json.loads(registry.read_text(encoding="utf-8"))
        value["numStartups"] += 1
        value["projects"][str(repo.resolve())] = {
            "hasTrustDialogAccepted": True
        }
        registry.write_text(json.dumps(value), encoding="utf-8")
        return 0

    assert manager.run(enabled_plan, launcher=trusted_launch) == 0
    guarded = manager.status(Host.CLAUDE, repository_root=repo)
    assert guarded["activation_observed"] is False
    assert guarded["registry_guard"]["outcome"] == "validated"


def test_claude_run_rejects_registry_drift_without_reverting(tmp_path: Path):
    manager, _, app_data = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    active = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )

    field_name = "SENSITIVE-UNEXPECTED-FIELD"
    field_value = "BODY-MUST-NOT-PERSIST"

    def drifted_launch(_args, _env):
        registry = tmp_path / "claude.json"
        value = json.loads(registry.read_text(encoding="utf-8"))
        value["numStartups"] += 1
        value["projects"][str(repo.resolve())] = {
            "hasTrustDialogAccepted": True
        }
        value[field_name] = field_value
        registry.write_text(json.dumps(value), encoding="utf-8")
        return 0

    with pytest.raises(ActivationError) as drift:
        manager.run(active, launcher=drifted_launch)

    assert drift.value.reason is DegradedReason.HOST_REGISTRY_DRIFT
    assert json.loads((tmp_path / "claude.json").read_text(encoding="utf-8"))[
        field_name
    ] == field_value
    status = manager.status(Host.CLAUDE, repository_root=repo)
    assert status["registry_guard"]["outcome"] == "rejected"
    assert status["registry_guard"]["changed_field_categories"] == [
        "protected_top_level"
    ]
    serialized = json.dumps(status, sort_keys=True)
    assert field_name not in serialized
    assert field_value not in serialized
    stored = json.dumps(
        StateStore(
            repo, fallback_base=app_data / "context-compaction" / "state"
        ).read_events(),
        sort_keys=True,
    )
    field_fingerprint = hashlib.sha256(
        json.dumps(field_value, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert field_name not in stored
    assert field_value not in stored
    assert field_fingerprint not in stored


def test_claude_registry_capture_rejection_has_empty_diagnostic_categories(
    tmp_path: Path,
):
    manager, _, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    active = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    (tmp_path / "claude.json").unlink()

    with pytest.raises(ActivationError) as rejected:
        manager.run(active, launcher=lambda _args, _env: 0)

    assert rejected.value.reason is DegradedReason.HOST_REGISTRY_DRIFT
    status = manager.status(Host.CLAUDE, repository_root=repo)
    assert status["registry_guard"]["error_code"] == "registry_missing"
    assert status["registry_guard"]["changed_field_categories"] == []


def test_default_claude_run_uses_allowlisted_cwd_and_terminates_exact_child_on_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manager, _, _ = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    active = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    observed: dict[str, object] = {}

    class FakeProcess:
        returncode: int | None = None

        def poll(self):
            registry = tmp_path / "claude.json"
            value = json.loads(registry.read_text(encoding="utf-8"))
            value["numStartups"] += 1
            value["unexpected"] = True
            registry.write_text(json.dumps(value), encoding="utf-8")
            return self.returncode

        def terminate(self):
            observed["terminated"] = True
            self.returncode = -15

        def wait(self, timeout=None):
            observed["wait_timeout"] = timeout
            return self.returncode

        def kill(self):
            observed["killed"] = True
            self.returncode = -9

    def fake_popen(arguments, *, env, cwd):
        observed["arguments"] = arguments
        observed["environment"] = env
        observed["cwd"] = cwd
        return FakeProcess()

    monkeypatch.setattr(manager, "_process_factory", fake_popen)

    with pytest.raises(ActivationError) as drift:
        manager.run(active)

    assert drift.value.reason is DegradedReason.HOST_REGISTRY_DRIFT
    assert observed["cwd"] == repo.resolve()
    assert observed["terminated"] is True
    assert observed["wait_timeout"] == 5
    assert "killed" not in observed
    assert json.loads((tmp_path / "claude.json").read_text(encoding="utf-8"))[
        "unexpected"
    ] is True
    status = manager.status(Host.CLAUDE, repository_root=repo)
    assert status["registry_guard"]["changed_field_categories"] == [
        "protected_top_level"
    ]


def test_active_status_reports_latest_content_free_diagnostic(tmp_path: Path):
    manager, _, app_data = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    store = StateStore(
        repo, fallback_base=app_data / "context-compaction" / "state"
    )
    store.append_event(
        {
            "schema_version": 1,
            "event_id": "event-1",
            "host": "claude",
            "host_version": "2.1.220",
            "event_name": "SessionStart",
            "model_class": "anthropic",
            "trigger": "compact",
            "repository_fingerprint": repository_fingerprint(repo),
            "outcome": "validation_required",
            "gate_state": "validation_required",
            "duration_ms": 4,
            "event_bytes": 100,
            "reentry_chars": 700,
            "estimated_tokens": 175,
            "included_category_names": ["lifecycle_status", "task_identity"],
            "omitted_category_names": [],
            "truncated": False,
            "degraded_reason_codes": [],
            "measurement_source": "unmeasured",
        },
        dedupe_key="status-event",
    )

    status = manager.status(Host.CLAUDE, repository_root=repo)

    assert status["state"] == "active"
    assert status["activation_observed"] is True
    assert status["tool_inventory_enforced"] is True
    assert status["observable_tool_count"] == 3
    assert status["host_version"] == "2.1.220"
    assert status["latest_event"]["model_class"] == "anthropic"
    assert status["latest_event"]["included_category_names"] == [
        "lifecycle_status",
        "task_identity",
    ]
    assert str(tmp_path) not in json.dumps(status, sort_keys=True)
    assert manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    ).state is ActivationState.ACTIVE


def test_status_ignores_diagnostic_from_wrong_repository_identity(tmp_path: Path):
    manager, _, app_data = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    StateStore(
        repo, fallback_base=app_data / "context-compaction" / "state"
    ).append_event(
        {
            "schema_version": 1,
            "event_id": "wrong-repository",
            "host": "claude",
            "host_version": "2.1.220",
            "event_name": "SessionStart",
            "repository_fingerprint": "a" * 64,
            "outcome": "validation_required",
            "degraded_reason_codes": [],
            "measurement_source": "unmeasured",
        },
        dedupe_key="wrong-repository",
    )

    status = manager.status(Host.CLAUDE, repository_root=repo)

    assert status["state"] == "enabled_unobserved"
    assert status["activation_observed"] is False


def test_disable_marker_prevents_old_event_from_reactivating_new_files(
    tmp_path: Path,
):
    manager, _, app_data = _manager(tmp_path)
    repo = _repository(tmp_path)
    plan = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(plan, approved_plan_hash=plan.plan_sha256)
    store = StateStore(
        repo, fallback_base=app_data / "context-compaction" / "state"
    )
    store.append_event(
        {
            "schema_version": 1,
            "event_id": "observed-before-disable",
            "host": "claude",
            "host_version": "2.1.220",
            "event_name": "SessionStart",
            "repository_fingerprint": repository_fingerprint(repo),
            "outcome": "validation_required",
            "degraded_reason_codes": [],
            "measurement_source": "unmeasured",
        },
        dedupe_key="observed-before-disable",
    )
    assert manager.status(Host.CLAUDE, repository_root=repo)["state"] == "active"

    manager.disable(Host.CLAUDE)
    replacement = manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    )
    manager.enable(replacement, approved_plan_hash=replacement.plan_sha256)

    assert manager.status(Host.CLAUDE, repository_root=repo)["state"] == (
        "enabled_unobserved"
    )
    assert manager.plan(
        Host.CLAUDE,
        repo,
        task_slug="pilot-task",
        capabilities=_capabilities(),
        hook_trusted=True,
    ).state is ActivationState.ENABLED_UNOBSERVED


def test_mutating_api_rejects_untyped_host(tmp_path: Path):
    manager, _, _ = _manager(tmp_path)
    with pytest.raises(ActivationError):
        manager.disable("codex")  # type: ignore[arg-type]


def test_cli_exposes_strict_operator_commands():
    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if action.dest == "command"
    )
    assert set(subparsers.choices) == {
        "plan",
        "enable",
        "run",
        "status",
        "validate",
        "disable",
        "purge-state",
        "hook",
    }


def test_precompact_command_failure_is_fail_open_but_event_mismatch_is_not(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    payload = {
        "session_id": "session-1",
        "cwd": "C:/repo",
        "hook_event_name": "PreCompact",
        "trigger": "manual",
    }
    arguments = SimpleNamespace(
        host="codex",
        host_version="0.145.0",
        pilot_config="missing.json",
        expected_event="PreCompact",
    )
    monkeypatch.setattr(
        cli_module,
        "_core_from_allowlist",
        lambda _path: (_ for _ in ()).throw(ValueError("synthetic config failure")),
    )
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode("utf-8"))),
    )

    assert cli_module._run_hook(arguments) == 0
    assert json.loads(capsys.readouterr().out) == {"continue": True}

    payload["hook_event_name"] = "PreToolUse"
    monkeypatch.setattr(
        cli_module.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode("utf-8"))),
    )
    with pytest.raises(ValueError, match="synthetic config failure"):
        cli_module._run_hook(arguments)


def test_cli_run_builds_and_verifies_the_activation_plan_once(
    monkeypatch: pytest.MonkeyPatch,
):
    plan = object()
    calls = 0

    class FakeManager:
        def run(self, received):
            assert received is plan
            return 0

    def build_once(_manager, _arguments):
        nonlocal calls
        calls += 1
        return plan

    monkeypatch.setattr(cli_module, "_manager", lambda _arguments: FakeManager())
    monkeypatch.setattr(cli_module, "_build_plan", build_once)

    result = cli_module.main(
        [
            "run",
            "--host",
            "claude",
            "--repo",
            "synthetic-repository",
            "--tool-inventory",
            "synthetic-inventory.json",
        ]
    )

    assert result == 0
    assert calls == 1


def test_cli_unexpected_error_is_content_free(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    sensitive = "sk-ABCDEFGHIJKLMNOPQRSTUVWX at C:/private/source.py"

    def fail(_arguments):
        raise RuntimeError(sensitive)

    monkeypatch.setattr(cli_module, "_manager", fail)

    assert cli_module.main(["status", "--host", "codex"]) == 2
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "error"
    assert response["code"] == "internal_error"
    assert len(response["correlation_id"]) == 36
    assert sensitive not in json.dumps(response)
