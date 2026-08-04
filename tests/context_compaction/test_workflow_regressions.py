"""Characterize checkpoint, handoff, and native-host escape hatches."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]

# Hashed over newline-normalized TEXT, not raw bytes. The repository has no
# `.gitattributes` and this machine checks out with `core.autocrlf=true`, so the
# same commit is LF in a worktree and CRLF in the main checkout. A byte gate
# therefore reported drift on three of these files in the main checkout while
# their content was identical -- it measured the checkout, not the asset.
PROTECTED_HASHES = {
    # Rebaselined 2026-08-04, deliberately and outside the pilot, after the
    # owner-approved gpt-image-2 timeout correction and optical-compression
    # registration. The latter remains a normal MCP server; it does not enable
    # context-pilot or alter native compaction.
    ".codex/config.toml": "f7e46fdf85af5a30025c7493b650be5c60a58e4716756ce43b7055faf4dd135e",
    ".claude/settings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
    # Rebaselined in the same owner-approved change: this is a guarded Claude
    # Read-result transform, not a PreCompact/PostCompact lifecycle hook.
    "hooks/hooks.json": "e0e1b009926c2ca4253d192906345a821ff184706fee86cb276ae0b5e93b708a",
    # Rebaselined 2026-08-02, deliberately and outside the pilot: both hooks derived
    # their mnemo namespace from the directory name, so any linked worktree wrote to
    # `repo:<branch-dir>` and orphaned its checkpoints from the repository corpus. The
    # fix follows `.git` back to the main checkout with pure file I/O. This gate proves
    # the PILOT never edits these assets -- an owner-approved fix to them re-baselines it
    # with a stated reason rather than being silently absorbed.
    ".claude/hooks/batman-phase-checkpoint.py": "323760300f2a5d7529b8db864684b82cce1e73f848dce6abd91b0d5b1adb941c",
    ".claude/hooks/batman-handoff-checkpoint.py": "714453c0f9254cf0614a9d0ad95b29e5b11dccbf56c83d0adcc209e0f93f9223",
    "skills/handoff/SKILL.md": "7c11924a5569f7fff2163d4795e28395b43e41ce5b1da08fd76338cb5dae54aa",
}


def test_protected_native_configs_and_existing_workflow_assets_are_byte_identical():
    observed = {
        relative: hashlib.sha256(
            (ROOT / relative).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
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


def test_mnemo_stays_importable_as_a_library_with_only_its_package_root_on_sys_path(
    tmp_path: Path,
):
    """R12.1: the checkpoint hooks embed mnemo as a library, not via run_server.py.

    `find_prior()` in both Batman hooks does exactly `sys.path.insert(0, <repo>/mnemo)`
    and then imports `mnemo.engine`. When `engine.py` gained a bare
    `from context_compaction.budget import ...`, that resolved only with the
    repository ROOT on the path, which only `mnemo/run_server.py` provides. The
    hooks caught the ImportError, fell back to `prior=None`, and then told the model
    "No prior checkpoint exists ... this is the first write" -- dropping the paired
    memory_forget and leaving two live `active` items per slug+phase.

    `-P` keeps the script directory and cwd off sys.path, so this reproduces the
    hook's real resolution environment rather than pytest's.
    """
    probe = (
        "import sys;"
        "sys.path.insert(0, {mnemo!r});"
        "from mnemo.config import Config;"
        "from mnemo.engine import MemoryEngine, build_task_context_response;"
        "print('ok')"
    ).format(mnemo=str(ROOT / "mnemo"))

    result = subprocess.run(
        [sys.executable, "-P", "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_phase_checkpoint_names_the_supersede_target_when_a_prior_checkpoint_is_live():
    """The branch the ImportError silently skipped. Never two live `active` items."""
    hook = _load_hook("phase", ".claude/hooks/batman-phase-checkpoint.py")
    target = {
        "phase": 4,
        "label": "Task Planning",
        "slug": "work",
        "namespace": "repo:repo",
        "artifact": "/repo/.batman/work/spec/tasks.md",
    }
    prior = {
        "memory_id": "00000000-0000-4000-8000-000000000000",
        "writer": "copilot",
        "timestamp": "2026-08-01T16:54:19.309921+00:00",
        "text": "prior phase-4 checkpoint body",
    }

    context = hook.build_context(target, prior)

    assert 'memory_forget(memory_id="00000000-0000-4000-8000-000000000000"' in context
    assert "Never leave two `active` items for the same slug and phase." in context
    assert "This is the first write." not in context


def test_delegation_handoff_names_the_supersede_target_when_a_prior_handoff_is_live():
    hook = _load_hook("handoff", ".claude/hooks/batman-handoff-checkpoint.py")
    target = hook.resolve_target(
        {
            "tool_name": "Edit",
            "cwd": "/repo",
            "tool_input": {"file_path": "/repo/.batman/work/handoffs/task-3.exec.md"},
        }
    )
    prior = {
        "memory_id": "11111111-1111-4111-8111-111111111111",
        "writer": "claude-code",
        "timestamp": "2026-08-01T16:54:19.309921+00:00",
        "text": "prior handoff body",
    }

    context = hook.build_context(target, prior)

    assert 'memory_forget(memory_id="11111111-1111-4111-8111-111111111111"' in context
    assert "Never leave two `active` items for the same slug and stem." in context
    assert "This is the first write." not in context


def test_checkpoint_namespace_follows_a_worktree_back_to_its_main_checkout(tmp_path: Path):
    """Checkpoints are per repository, not per worktree.

    `PurePosixPath(root).name` returned the worktree's own directory name, so
    `coding-cli.worktrees/some-branch` wrote to `repo:some-branch` and orphaned every
    checkpoint from the `repo:coding-cli` corpus the next session reads back.
    """
    main = tmp_path / "coding-cli"
    (main / ".git" / "worktrees" / "some-branch").mkdir(parents=True)
    worktree = tmp_path / "coding-cli.worktrees" / "some-branch"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text(
        "gitdir: {0}\n".format(main / ".git" / "worktrees" / "some-branch"),
        encoding="utf-8",
    )

    for name, relative in (
        ("phase", ".claude/hooks/batman-phase-checkpoint.py"),
        ("handoff", ".claude/hooks/batman-handoff-checkpoint.py"),
    ):
        hook = _load_hook(name, relative)
        assert hook.repository_name(worktree.as_posix()) == "coding-cli"
        assert hook.repository_name(main.as_posix()) == "coding-cli"


def test_checkpoint_namespace_fails_soft_to_the_directory_name(tmp_path: Path):
    """A missing, malformed, or non-worktree `.git` must never cost the user's write."""
    hook = _load_hook("phase", ".claude/hooks/batman-phase-checkpoint.py")

    absent = tmp_path / "plain-dir"
    absent.mkdir()
    malformed = tmp_path / "garbage-dir"
    malformed.mkdir()
    (malformed / ".git").write_text("not a gitdir pointer", encoding="utf-8")
    detached = tmp_path / "elsewhere"
    detached.mkdir()
    (detached / ".git").write_text("gitdir: /nowhere/at/all\n", encoding="utf-8")

    assert hook.repository_name(absent.as_posix()) == "plain-dir"
    assert hook.repository_name(malformed.as_posix()) == "garbage-dir"
    assert hook.repository_name(detached.as_posix()) == "elsewhere"


def test_checkpoint_namespace_resolution_makes_no_subprocess_call(monkeypatch):
    """The 'no git call' constraint is load-bearing: `git` here reintroduced a 31s hang."""
    import subprocess as _subprocess

    def explode(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("checkpoint namespace resolution must not shell out")

    for attribute in ("run", "Popen", "check_output", "call", "check_call"):
        monkeypatch.setattr(_subprocess, attribute, explode)

    hook = _load_hook("phase", ".claude/hooks/batman-phase-checkpoint.py")
    assert hook.repository_name(str(ROOT).replace("\\", "/")) == "coding-cli"


def _load_hook(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(f"context_pilot_{name}_hook", ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
