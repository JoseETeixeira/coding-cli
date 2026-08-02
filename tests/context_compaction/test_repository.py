"""Repository reconstruction contracts for the compaction pilot."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from context_compaction.models import DegradedReason
from context_compaction.repository import (
    RepositoryError,
    RepositoryResolver,
    canonical_repository_root,
    repository_fingerprint,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _repo(tmp_path: Path, *, branch: str = "main") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", branch)
    _git(repo, "config", "user.email", "pilot@example.invalid")
    _git(repo, "config", "user.name", "Pilot Test")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "base")
    return repo


def _task(repo: Path, slug: str, *, incomplete: bool = True) -> Path:
    spec = repo / ".batman" / slug / "spec"
    spec.mkdir(parents=True)
    checkbox = "[ ]" if incomplete else "[x]"
    (spec / "tasks.md").write_text(
        f"# Tasks: {slug}\n\nStatus: Approved\n\n- {checkbox} work\n",
        encoding="utf-8",
    )
    return spec


def test_canonical_root_rejects_unc_and_device_paths():
    with pytest.raises(RepositoryError) as unc:
        canonical_repository_root(r"\\server\share\repo")
    assert unc.value.reason is DegradedReason.ALLOWLIST_MISMATCH

    with pytest.raises(RepositoryError):
        canonical_repository_root(r"\\?\C:\repo")


def test_git_snapshot_keeps_relative_dirty_paths_and_status(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (repo / "new file.txt").write_text("new\n", encoding="utf-8")
    _task(repo, "work")

    state = RepositoryResolver(
        repo,
        allowed_fingerprint=repository_fingerprint(repo),
        explicit_task_slug="work",
    ).resolve()

    dirty = {(item.path, item.status) for item in state.repository.dirty_paths}
    assert ("tracked.txt", ".M") in dirty
    assert ("new file.txt", "??") in dirty
    assert all(not Path(item.path).is_absolute() for item in state.repository.dirty_paths)
    assert state.repository.branch == "main"
    assert len(state.repository.head or "") == 40


def test_detached_head_is_reported_without_inventing_branch(tmp_path: Path):
    repo = _repo(tmp_path)
    _task(repo, "work")
    _git(repo, "checkout", "--detach")

    state = RepositoryResolver(
        repo,
        allowed_fingerprint=repository_fingerprint(repo),
        explicit_task_slug="work",
    ).resolve()

    assert state.repository.branch is None
    assert state.repository.head == _git(repo, "rev-parse", "HEAD")


def test_task_selection_precedence_explicit_then_exact_branch_then_single(tmp_path: Path):
    repo = _repo(tmp_path, branch="feature/branch-task")
    _task(repo, "explicit-task")
    _task(repo, "branch-task")

    explicit = RepositoryResolver(
        repo,
        allowed_fingerprint=repository_fingerprint(repo),
        explicit_task_slug="explicit-task",
    ).resolve()
    assert explicit.task.slug == "explicit-task"
    assert explicit.task.selection_source == "explicit"

    branch = RepositoryResolver(
        repo, allowed_fingerprint=repository_fingerprint(repo)
    ).resolve()
    assert branch.task.slug == "branch-task"
    assert branch.task.selection_source == "branch"

    _git(repo, "checkout", "-b", "unrelated")
    (repo / ".batman" / "branch-task" / "spec" / "tasks.md").write_text(
        "# done\n- [x] complete\n", encoding="utf-8"
    )
    single = RepositoryResolver(
        repo, allowed_fingerprint=repository_fingerprint(repo)
    ).resolve()
    assert single.task.slug == "explicit-task"
    assert single.task.selection_source == "single_incomplete"


def test_zero_or_multiple_incomplete_tasks_are_ambiguous(tmp_path: Path):
    repo = _repo(tmp_path)
    no_task = RepositoryResolver(
        repo, allowed_fingerprint=repository_fingerprint(repo)
    ).resolve()
    assert no_task.task.degraded_reason is DegradedReason.TASK_AMBIGUOUS

    _task(repo, "one")
    _task(repo, "two")
    multiple = RepositoryResolver(
        repo, allowed_fingerprint=repository_fingerprint(repo)
    ).resolve()
    assert multiple.task.slug is None
    assert multiple.task.degraded_reason is DegradedReason.TASK_AMBIGUOUS


def test_explicit_missing_task_does_not_fall_back(tmp_path: Path):
    repo = _repo(tmp_path)
    _task(repo, "available")

    state = RepositoryResolver(
        repo,
        allowed_fingerprint=repository_fingerprint(repo),
        explicit_task_slug="missing",
    ).resolve()

    assert state.task.slug == "missing"
    assert state.task.degraded_reason is DegradedReason.ARTIFACT_MISSING


def test_scoped_rules_are_root_to_leaf_hash_pointers(tmp_path: Path):
    repo = _repo(tmp_path)
    _task(repo, "work")
    nested = repo / "src" / "feature"
    nested.mkdir(parents=True)
    target = nested / "code.py"
    target.write_text("pass\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("root rules\n", encoding="utf-8")
    (repo / "src" / "CLAUDE.md").write_text("nested rules\n", encoding="utf-8")

    state = RepositoryResolver(
        repo,
        allowed_fingerprint=repository_fingerprint(repo),
        explicit_task_slug="work",
    ).resolve(target_path=target)

    assert [pointer.relative_path for pointer in state.scoped_rule_pointers] == [
        "AGENTS.md",
        "src/CLAUDE.md",
    ]
    assert all(len(pointer.captured_hash) == 64 for pointer in state.scoped_rule_pointers)


def test_allowlist_fingerprint_mismatch_is_rejected(tmp_path: Path):
    repo = _repo(tmp_path)
    with pytest.raises(RepositoryError) as mismatch:
        RepositoryResolver(repo, allowed_fingerprint="0" * 64).resolve()
    assert mismatch.value.reason is DegradedReason.ALLOWLIST_MISMATCH


def test_symlink_target_escape_is_rejected_when_supported(tmp_path: Path):
    repo = _repo(tmp_path)
    _task(repo, "work")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = repo / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")

    resolver = RepositoryResolver(
        repo,
        allowed_fingerprint=repository_fingerprint(repo),
        explicit_task_slug="work",
    )
    with pytest.raises(RepositoryError):
        resolver.resolve(target_path=link)
