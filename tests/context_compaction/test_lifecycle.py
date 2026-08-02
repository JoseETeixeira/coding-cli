"""Normalized lifecycle and validation-gate contracts."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace
from itertools import count
from pathlib import Path

from context_compaction.lifecycle import LifecycleCore
from context_compaction.models import (
    ActionStatus,
    DegradedReason,
    GateState,
    HookEvent,
    Host,
    HostPilotConfig,
    PilotConfig,
    ToolClass,
    Trigger,
)
from context_compaction.repository import RepositoryResolver, repository_fingerprint
from context_compaction.storage import StateStore


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _setup(tmp_path: Path, *, approval: str = "none"):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "pilot-task")
    _git(repo, "config", "user.email", "pilot@example.invalid")
    _git(repo, "config", "user.name", "Pilot Test")
    spec = repo / ".batman" / "pilot-task" / "spec"
    spec.mkdir(parents=True)
    tasks = spec / "tasks.md"
    tasks.write_text(
        "# Tasks\n\nStatus: Approved\n\n"
        f"Approval: {approval}\n\n- [ ] active work\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    fingerprint = repository_fingerprint(repo)
    host = HostPilotConfig(
        enabled=True,
        supported_versions=("0.145.0",),
        auto_token_limit=64_000,
        auto_limit_scope="body_after_prefix",
        tool_output_limit=12_000,
    )
    config = PilotConfig(
        repository_root=str(repo.resolve()),
        repository_fingerprint=fingerprint,
        task_slug="pilot-task",
        codex=host,
        claude=HostPilotConfig(
            enabled=True,
            supported_versions=("2.1.220",),
            auto_token_limit=100_000,
            auto_percent=80,
        ),
        enabled=True,
    )
    ids = (f"event-{index}" for index in count(1))
    core = LifecycleCore(
        config,
        RepositoryResolver(
            repo,
            allowed_fingerprint=fingerprint,
            explicit_task_slug="pilot-task",
        ),
        StateStore(repo),
        id_factory=lambda: next(ids),
        clock=lambda: "2026-08-01T00:00:00Z",
    )
    return repo, tasks, core


def _event(repo: Path, name: str, **overrides) -> HookEvent:
    values = {
        "host": Host.CODEX,
        "host_version": "0.145.0",
        "event_name": name,
        "cwd": str(repo),
        "trigger": Trigger.AUTO,
        "source": None,
        "session_id": "session-1",
    }
    values.update(overrides)
    return HookEvent(**values)


def _capture_and_resume(repo: Path, core: LifecycleCore):
    captured = core.handle_event(_event(repo, "PreCompact"))
    resumed = core.handle_event(
        _event(repo, "SessionStart", source="compact", trigger=None)
    )
    return captured, resumed


def test_precompact_is_fail_open_and_resume_requires_validation(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    captured, resumed = _capture_and_resume(repo, core)

    assert captured.continue_ is True
    assert captured.gate_state is GateState.CAPTURED
    assert resumed.continue_ is True
    assert resumed.gate_state is GateState.VALIDATION_REQUIRED
    assert resumed.additional_context
    assert len(resumed.additional_context) <= 8_000


def test_missing_state_resumes_degraded_and_blocks_material_tools(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    resumed = core.handle_event(
        _event(repo, "SessionStart", source="compact", trigger=None)
    )
    blocked = core.handle_event(
        _event(
            repo,
            "PreToolUse",
            tool_name="apply_patch",
            tool_use_id="tool-1",
            tool_class=ToolClass.LOCAL_WRITE,
            input_fingerprint="1" * 64,
        )
    )

    assert resumed.gate_state is GateState.DEGRADED
    assert resumed.degraded_reasons == (DegradedReason.STATE_MISSING,)
    assert blocked.continue_ is False
    assert blocked.stop_reason == "validation_required"


def test_read_evidence_can_validate_current_epoch(tmp_path: Path):
    repo, tasks, core = _setup(tmp_path)
    _, resumed = _capture_and_resume(repo, core)
    relative = tasks.relative_to(repo).as_posix()
    fingerprint = hashlib.sha256(relative.encode("utf-8")).hexdigest()

    allowed = core.handle_event(
        _event(
            repo,
            "PreToolUse",
            tool_name="read_file",
            tool_use_id="read-1",
            tool_class=ToolClass.READ,
            input_fingerprint=fingerprint,
            evidence_relative_path=relative,
        )
    )
    completed = core.handle_event(
        _event(
            repo,
            "PostToolUse",
            tool_name="read_file",
            tool_use_id="read-1",
            tool_class=ToolClass.READ,
            input_fingerprint=fingerprint,
            evidence_relative_path=relative,
            status="completed",
        )
    )
    validated = core.validate(resumed.event_id or "", evidence_paths=(relative,))

    assert allowed.continue_ is True
    assert completed.status == "recorded"
    assert validated.gate_state is GateState.VALIDATED


def test_source_change_refreshes_and_stays_read_only(tmp_path: Path):
    repo, tasks, core = _setup(tmp_path)
    _, resumed = _capture_and_resume(repo, core)
    relative = tasks.relative_to(repo).as_posix()
    tasks.write_text(tasks.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    result = core.validate(resumed.event_id or "", evidence_paths=(relative,))

    assert result.gate_state is GateState.DEGRADED
    assert DegradedReason.SOURCE_CHANGED in result.degraded_reasons


def test_missing_artifact_and_unvalidated_scoped_rule_degrade_validation(tmp_path: Path):
    repo, tasks, core = _setup(tmp_path)
    rule = repo / "AGENTS.md"
    rule.write_text("scoped rule\n", encoding="utf-8")
    _git(repo, "add", "AGENTS.md")
    _git(repo, "commit", "-m", "scoped rule")
    _, resumed = _capture_and_resume(repo, core)
    task_relative = tasks.relative_to(repo).as_posix()

    scoped = core.validate(resumed.event_id or "", evidence_paths=(task_relative,))

    assert scoped.gate_state is GateState.DEGRADED
    assert DegradedReason.SCOPED_RULES_UNVALIDATED in scoped.degraded_reasons

    tasks.unlink()
    missing = core.validate(resumed.event_id or "", evidence_paths=(task_relative,))
    assert missing.gate_state is GateState.DEGRADED
    assert DegradedReason.ARTIFACT_MISSING in missing.degraded_reasons


def test_pending_approval_survives_compaction_and_prevents_validation(tmp_path: Path):
    repo, tasks, core = _setup(tmp_path, approval="pending")
    _, resumed = _capture_and_resume(repo, core)
    relative = tasks.relative_to(repo).as_posix()
    result = core.validate(resumed.event_id or "", evidence_paths=(relative,))

    assert result.gate_state is GateState.DEGRADED
    assert DegradedReason.APPROVAL_UNRESOLVED in result.degraded_reasons


def test_started_action_becomes_ambiguous_after_mid_turn_compaction(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    core.handle_event(
        _event(
            repo,
            "PreToolUse",
            tool_name="github.create_pull_request",
            tool_use_id="publish-1",
            tool_class=ToolClass.EXTERNAL_SIDE_EFFECT,
            input_fingerprint="2" * 64,
        )
    )
    _, resumed = _capture_and_resume(repo, core)

    assert resumed.gate_state is GateState.DEGRADED
    assert DegradedReason.ACTION_AMBIGUOUS in resumed.degraded_reasons
    assert core.current_actions()[0].status is ActionStatus.AMBIGUOUS


def test_completed_non_idempotent_fingerprint_is_not_replayed(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    pre = _event(
        repo,
        "PreToolUse",
        tool_name="github.create_pull_request",
        tool_use_id="publish-1",
        tool_class=ToolClass.EXTERNAL_SIDE_EFFECT,
        input_fingerprint="3" * 64,
    )
    core.handle_event(pre)
    core.handle_event(
        _event(
            repo,
            "PostToolUse",
            tool_name="github.create_pull_request",
            tool_use_id="publish-1",
            tool_class=ToolClass.EXTERNAL_SIDE_EFFECT,
            input_fingerprint="3" * 64,
            status="completed",
        )
    )
    retry = core.handle_event(
        _event(
            repo,
            "PreToolUse",
            tool_name="github.create_pull_request",
            tool_use_id="publish-2",
            tool_class=ToolClass.EXTERNAL_SIDE_EFFECT,
            input_fingerprint="3" * 64,
        )
    )

    assert retry.continue_ is False
    assert retry.stop_reason == "completed_non_idempotent_action"


def test_duplicate_event_has_one_observable_record(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    event = _event(repo, "PreCompact", turn_id="turn-1")
    first = core.handle_event(event)
    second = core.handle_event(event)

    assert second.event_id == first.event_id
    assert second.status == "duplicate"
    matching = [item for item in core.diagnostics() if item["event_id"] == first.event_id]
    assert len(matching) == 1


def test_uncorrelated_claude_compaction_cycles_are_distinct(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    pre = _event(
        repo,
        "PreCompact",
        host=Host.CLAUDE,
        host_version="2.1.220",
        turn_id=None,
    )
    resumed = _event(
        repo,
        "SessionStart",
        host=Host.CLAUDE,
        host_version="2.1.220",
        trigger=None,
        source="compact",
        turn_id=None,
    )

    first_pre = core.handle_event(pre)
    first_resume = core.handle_event(resumed)
    second_pre = core.handle_event(pre)
    second_resume = core.handle_event(resumed)

    assert second_pre.status == "captured"
    assert second_resume.status == "validation_required"
    assert len(
        {
            first_pre.event_id,
            first_resume.event_id,
            second_pre.event_id,
            second_resume.event_id,
        }
    ) == 4


def test_diagnostic_is_content_free_and_records_available_counts(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    core.handle_event(
        _event(
            repo,
            "PreCompact",
            model="gpt-5.6-codex",
            event_bytes=321,
            pre_usage=70_000,
            measurement_source="host_hook",
        )
    )
    resumed = core.handle_event(
        _event(
            repo,
            "SessionStart",
            source="compact",
            trigger=None,
            model="gpt-5.6-codex",
            event_bytes=123,
            post_usage=8_000,
            measurement_source="host_hook",
        )
    )

    record = next(item for item in core.diagnostics() if item["event_id"] == resumed.event_id)
    assert record["event_name"] == "SessionStart"
    assert record["model_class"] == "openai"
    assert record["event_bytes"] == 123
    assert record["reentry_chars"] == len(resumed.additional_context or "")
    assert record["estimated_tokens"] > 0
    assert record["included_category_names"]
    assert record["truncated"] is False
    assert record["pre_usage"] is None
    assert record["post_usage"] == 8_000
    assert record["measurement_source"] == "host_hook"
    serialized = str(record).lower()
    assert "private summary body" not in serialized
    assert str(repo).lower() not in serialized


def test_memory_offline_is_nonblocking_for_source_reconstruction(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    core.set_memory_available(False)
    captured, resumed = _capture_and_resume(repo, core)

    assert captured.continue_ is True
    assert resumed.continue_ is True
    assert resumed.gate_state is GateState.VALIDATION_REQUIRED
    assert DegradedReason.MEMORY_UNAVAILABLE not in resumed.degraded_reasons


def test_disabled_pilot_never_blocks_a_tool(tmp_path: Path):
    repo, _, core = _setup(tmp_path)
    core.config = replace(core.config, enabled=False)
    result = core.handle_event(
        _event(
            repo,
            "PreToolUse",
            tool_name="apply_patch",
            tool_use_id="tool-disabled",
            tool_class=ToolClass.LOCAL_WRITE,
            input_fingerprint="4" * 64,
        )
    )

    assert result.status == "inactive"
    assert result.continue_ is True


def test_precompact_remains_fail_open_when_private_storage_fails(tmp_path: Path):
    repo, _, core = _setup(tmp_path)

    def fail_write(_payload):
        raise OSError("synthetic storage failure")

    core.store.write_current = fail_write
    core.store.append_event = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        OSError("synthetic diagnostic failure")
    )
    result = core.handle_event(_event(repo, "PreCompact"))

    assert result.continue_ is True
    assert result.gate_state is GateState.DEGRADED
