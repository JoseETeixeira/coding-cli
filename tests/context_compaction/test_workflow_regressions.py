"""Characterize checkpoint, handoff, and native-host escape hatches."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[2]
PROTECTED_HASHES = {
    ".codex/config.toml": "3f5b6a1a7b22a00a99ba4d38d832870bf0c7272145bae839ee90306c5fc1e890",
    ".claude/settings.json": "e3566b3a06430868d71e9287dfd6c6c520a3da027aabea01951d407ee131dc2f",
    "hooks/hooks.json": "4fa24d5dd9a70e58c695b838ad31bb7efcfc1468814f3369859967a720fe5fd6",
    ".claude/hooks/batman-phase-checkpoint.py": "6db830fbdfb6a9a306e92122b2d50bcbccce2b6edc1d3b5dd60685f5f60840fe",
    ".claude/hooks/batman-handoff-checkpoint.py": "c47c2f62931d091ee4c2e58313a3305a7968e9a83ac9db559c78a9b108b217bb",
    "skills/handoff/SKILL.md": "706d60291d1bfdf461599382d9513145a48159f679e3c6d906c3c1985a463cb4",
}


def test_protected_native_configs_and_existing_workflow_assets_are_byte_identical():
    observed = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in PROTECTED_HASHES
    }

    assert observed == PROTECTED_HASHES
    for relative in (".codex/config.toml", ".claude/settings.json", "hooks/hooks.json"):
        body = (ROOT / relative).read_text(encoding="utf-8")
        assert "context-pilot" not in body
        assert "context_compaction" not in body


def test_phase_checkpoint_still_arms_only_after_approval(tmp_path: Path):
    hook = _load_hook("phase", ".claude/hooks/batman-phase-checkpoint.py")
    artifact = tmp_path / "repo" / ".batman" / "work" / "spec" / "requirements.md"
    target = hook.resolve_target(
        {
            "tool_name": "Write",
            "cwd": str(tmp_path / "repo"),
            "tool_input": {"file_path": str(artifact)},
        }
    )
    context = hook.build_context(target, None)

    assert target["phase"] == 2
    assert target["namespace"] == "repo:repo"
    assert "This hook wrote NOTHING to mnemo" in context
    assert "ONLY once the user approves" in context
    assert "curated distillation, not a copy of the artifact" in context


def test_delegation_handoff_remains_pointer_first_and_write_after_artifact(tmp_path: Path):
    hook = _load_hook("handoff", ".claude/hooks/batman-handoff-checkpoint.py")
    artifact = tmp_path / "repo" / ".batman" / "work" / "handoffs" / "task-3.exec.md"
    target = hook.resolve_target(
        {
            "tool_name": "Edit",
            "cwd": str(tmp_path / "repo"),
            "tool_input": {"file_path": str(artifact)},
        }
    )
    context = hook.build_context(target, None)

    assert target["stem"] == "task-3.exec"
    assert "FILE is the source of truth" in context
    assert "Write it NOW, before you return" in context
    assert "pointer set to the memory_id" in context
    assert "not the file body" in context


def test_shared_memory_keeps_phase_and_handoff_contracts_beside_thin_compaction_pointer():
    shared = (ROOT / "skills/shared-memory/SKILL.md").read_text(encoding="utf-8")
    execute = (ROOT / "prompts/execute-task.prompt.md").read_text(encoding="utf-8")
    handoff = (ROOT / "skills/handoff/SKILL.md").read_text(encoding="utf-8")

    assert shared.count("## Phase checkpoints") == 1
    assert shared.count("## Delegation handoffs") == 1
    assert shared.count("`context-compaction`") == 1
    assert "memory_get(<pointer>)" in shared
    assert "the file holds the detail" in shared
    assert "writes no handoff artifact" in execute
    assert "Do not duplicate content already captured in other artifacts" in handoff
    assert "Reference them by path or URL instead" in handoff


def _load_hook(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(f"context_pilot_{name}_hook", ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
