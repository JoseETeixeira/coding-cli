"""Private state storage contracts for the compaction pilot."""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import pytest

from context_compaction.models import DegradedReason
from context_compaction.storage import (
    MAX_STATE_BYTES,
    OWNER_ID,
    StateStore,
    StorageError,
    resolve_state_directory,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    return repo


def _payload(event_id: str = "event-1") -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": event_id,
        "repository_fingerprint": "a" * 64,
        "relative_paths": ["src/file.py"],
    }


def _append_in_process(arguments: tuple[str, int]) -> bool:
    repository, index = arguments
    return StateStore(repository, retention=200).append_event(
        _payload(f"process-{index}"), dedupe_key=f"process-key-{index}"
    )


def test_git_state_directory_matches_worktree_private_git_path(tmp_path: Path):
    repo = _repo(tmp_path)
    expected = Path(
        _git(repo, "rev-parse", "--path-format=absolute", "--git-path", "coding-cli-context-pilot")
    ).resolve()

    assert resolve_state_directory(repo) == expected
    store = StateStore(repo)
    store.write_current(_payload())
    assert _git(repo, "status", "--porcelain") == ""


def test_non_git_fallback_is_keyed_by_canonical_root_hash(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fallback = tmp_path / "state"

    first = resolve_state_directory(workspace, fallback_base=fallback)
    second = resolve_state_directory(workspace, fallback_base=fallback)

    assert first == second
    assert first.parent == fallback.resolve()
    assert len(first.name) == 64


def test_reads_do_not_create_state_or_lock_files(tmp_path: Path):
    store = StateStore(_repo(tmp_path))
    lock_path = store.directory.parent / f".{store.directory.name}.context-pilot.lock"

    assert store.read_current() is None
    assert store.read_events() == []
    assert not store.directory.exists()
    assert not lock_path.exists()


def test_atomic_roundtrip_owner_marker_and_restrictive_mode(tmp_path: Path):
    repo = _repo(tmp_path)
    store = StateStore(repo)
    store.write_current(_payload())

    assert store.read_current() == _payload()
    marker = json.loads((store.directory / "owner.json").read_text(encoding="utf-8"))
    assert marker == {"owner": OWNER_ID, "schema_version": 1}
    assert not list(store.directory.glob("*.tmp"))
    if os.name != "nt":
        assert (store.directory / "current.json").stat().st_mode & 0o077 == 0


def test_storage_rejects_sensitive_or_oversized_payloads(tmp_path: Path):
    store = StateStore(_repo(tmp_path))
    with pytest.raises(StorageError):
        store.write_current({**_payload(), "transcript_path": "do-not-store"})
    with pytest.raises(StorageError) as oversized:
        store.write_current({**_payload(), "goal_preview": "x" * MAX_STATE_BYTES})
    assert oversized.value.reason is DegradedReason.STATE_OVERSIZED
    with pytest.raises(StorageError, match="sensitive"):
        store.write_current(
            {**_payload(), "goal_preview": "key sk-ABCDEFGHIJKLMNOPQRSTUVWX"}
        )


def test_unknown_schema_and_owner_drift_are_not_overwritten(tmp_path: Path):
    store = StateStore(_repo(tmp_path))
    store.write_current(_payload())
    current = store.directory / "current.json"
    current.write_text('{"schema_version":999}', encoding="utf-8")
    with pytest.raises(StorageError) as schema:
        store.read_current()
    assert schema.value.reason is DegradedReason.STATE_MALFORMED

    (store.directory / "owner.json").write_text(
        '{"owner":"someone-else","schema_version":1}', encoding="utf-8"
    )
    with pytest.raises(StorageError) as owner:
        store.write_current(_payload("another"))
    assert owner.value.reason is DegradedReason.OWNED_FILE_DRIFT


def test_events_are_deduplicated_and_retained_newest_200(tmp_path: Path):
    store = StateStore(_repo(tmp_path), retention=200)
    assert store.append_event(_payload("same"), dedupe_key="same") is True
    assert store.append_event(_payload("same"), dedupe_key="same") is False
    for index in range(205):
        store.append_event(_payload(f"event-{index}"), dedupe_key=f"key-{index}")

    events = store.read_events()
    assert len(events) == 200
    assert events[0]["event_id"] == "event-5"
    assert events[-1]["event_id"] == "event-204"


def test_concurrent_event_writes_do_not_lose_unique_records(tmp_path: Path):
    store = StateStore(_repo(tmp_path), retention=200)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda index: store.append_event(
                    _payload(f"event-{index}"), dedupe_key=f"key-{index}"
                ),
                range(100),
            )
        )
    assert {event["event_id"] for event in store.read_events()} == {
        f"event-{index}" for index in range(100)
    }


def test_independent_process_writes_are_serialized(tmp_path: Path):
    repo = _repo(tmp_path)
    with ProcessPoolExecutor(max_workers=4) as executor:
        assert all(
            executor.map(
                _append_in_process,
                [(str(repo), index) for index in range(20)],
            )
        )
    assert {event["event_id"] for event in StateStore(repo).read_events()} == {
        f"process-{index}" for index in range(20)
    }


def test_purge_only_removes_owned_private_state(tmp_path: Path):
    repo = _repo(tmp_path)
    source = repo / "keep.txt"
    source.write_text("keep\n", encoding="utf-8")
    store = StateStore(repo)
    store.write_current(_payload())
    private = store.directory

    store.purge()

    assert source.read_text(encoding="utf-8") == "keep\n"
    assert not private.exists()


def test_purge_removes_orphaned_owned_lock_when_state_is_absent(tmp_path: Path):
    repo = _repo(tmp_path)
    store = StateStore(repo)
    lock = store._lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"\0")

    store.purge()

    assert not store.directory.exists()
    assert not lock.exists()
