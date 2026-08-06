"""Pure Git identity tests plus code-index tests against a real Qdrant.

Qdrant-backed tests use a deterministic fake embedder (no network / no OpenAI
cost). Each run uses a throwaway collection that is deleted on teardown.

Run:  py -3.12 -m pytest mnemo/tests -q
Only Qdrant-backed tests skip when Qdrant is unreachable.

Several tests here guard failure modes that produce NO exception and NO log —
they would silently return wrong code forever. Those are called out inline.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mnemo import code_index  # noqa: E402
from mnemo.code_index import (  # noqa: E402
    CodeIndex,
    GitUnavailable,
    IndexProgress,
    Manifest,
    ProgressRegistry,
    RepoUnresolved,
    WorktreeIdentityUnavailable,
    candidates_from_roots,
    chunk_text,
    compute_repo_id,
    discover_files,
    resolve_repo,
)
from mnemo.config import Config  # noqa: E402

QDRANT_URL = os.environ.get("MNEMO_QDRANT_URL", "http://127.0.0.1:1337")
DIM = 64


class FakeEmbedder:
    """Deterministic hash-based embedding — same text -> same vector, no network."""

    dim = DIM

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [self.embed_one(t) for t in texts]

    def embed_one(self, text):
        vec = [0.0] * DIM
        for token in text.lower().split():
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            vec[h % DIM] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


def _qdrant_up() -> bool:
    try:
        import urllib.request

        urllib.request.urlopen(QDRANT_URL + "/readyz", timeout=2).read()
        return True
    except Exception:
        return False


def _git(root, *args):
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )


@pytest.fixture()
def repo(tmp_path):
    """A real throwaway git repo — discovery goes through git, so it must be real."""
    root = tmp_path / "sample-repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    (root / "app.py").write_text(
        "def charge_card(token):\n"
        "    # retry the payment capture on timeout\n"
        "    for attempt in range(3):\n"
        "        try:\n"
        "            return gateway.capture(token)\n"
        "        except Timeout:\n"
        "            continue\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Sample\n\nA sample project.\n", encoding="utf-8")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 64)
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (root / "ignored").mkdir()
    (root / "ignored" / "secret.py").write_text("KEY = 'nope'\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


@pytest.fixture()
def index(tmp_path):
    if not _qdrant_up():
        pytest.skip("Qdrant not reachable on 1337")
    cfg = Config()
    cfg.code_collection = f"mnemo_code_test_{uuid.uuid4().hex[:8]}"
    cfg.qdrant_url = QDRANT_URL
    cfg.data_dir = tmp_path / "data"
    idx = CodeIndex(cfg, embedder=FakeEmbedder())
    yield idx
    try:
        idx.client.delete_collection(cfg.code_collection)
    except Exception:
        pass


# ---- repo resolution -------------------------------------------------------
def test_resolve_repo_refuses_non_git(tmp_path):
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    with pytest.raises(RepoUnresolved):
        resolve_repo(plain)


def test_resolve_repo_refuses_home():
    # The live failure this guards: Claude Code spawns MCP servers with an
    # inherited cwd, which is $HOME on a terminal launch. Indexing there would
    # silently poison the shared index for every agent.
    with pytest.raises(RepoUnresolved):
        resolve_repo(os.path.expanduser("~"))


def test_resolve_repo_honors_noindex_marker(repo):
    (repo / ".mnemo-noindex").write_text("", encoding="utf-8")
    with pytest.raises(RepoUnresolved):
        resolve_repo(repo)


def test_resolve_repo_from_subdirectory(repo):
    sub = repo / "pkg" / "deep"
    sub.mkdir(parents=True)
    info = resolve_repo(sub)
    assert os.path.normcase(str(info.root)) == os.path.normcase(str(repo))


def test_code_index_scope_is_stable_for_same_tree_and_subdirectory(repo):
    sub = repo / "pkg" / "deep"
    sub.mkdir(parents=True)
    root_info = resolve_repo(repo)
    sub_info = resolve_repo(sub)
    assert root_info.code_index_scope == sub_info.code_index_scope
    assert root_info.worktree == sub_info.worktree
    assert root_info.code_index_scope.startswith("wt2_")


def test_related_worktrees_and_clone_get_distinct_scopes(repo, tmp_path):
    linked_a = tmp_path / "linked-a"
    linked_b = tmp_path / "linked-b"
    clone = tmp_path / "same-history-clone"
    _git(repo, "worktree", "add", "-q", "-b", "linked-a", str(linked_a))
    _git(repo, "worktree", "add", "-q", "-b", "linked-b", str(linked_b))
    _git(tmp_path, "clone", "-q", str(repo), str(clone))

    infos = [resolve_repo(path) for path in (repo, linked_a, linked_b, clone)]
    assert len({info.repo_id for info in infos}) == 1
    assert len({info.code_index_scope for info in infos}) == len(infos)


def test_recreated_worktree_path_gets_new_scope(repo, tmp_path):
    linked = tmp_path / "reused-linked-path"
    _git(repo, "worktree", "add", "-q", "-b", "incarnation-one", str(linked))
    first = resolve_repo(linked).code_index_scope
    _git(repo, "worktree", "remove", "--force", str(linked))
    _git(repo, "worktree", "add", "-q", "-b", "incarnation-two", str(linked))
    second = resolve_repo(linked).code_index_scope
    assert first != second


def test_moved_checkout_gets_safe_new_scope(repo, tmp_path):
    before = resolve_repo(repo)
    moved = tmp_path / "moved-elsewhere"
    shutil.move(str(repo), moved)
    after = resolve_repo(moved)
    assert after.repo_id == before.repo_id
    assert after.code_index_scope != before.code_index_scope


def test_worktree_identity_refuses_zero_filesystem_proof(repo, monkeypatch):
    real_stat = code_index.os.stat
    info = resolve_repo(repo)

    def zero_known_git_dir(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if os.path.normcase(str(path)) == os.path.normcase(str(info.worktree.git_dir)):
            values = list(result)
            values[1] = 0
            return os.stat_result(values)
        return result

    monkeypatch.setattr(code_index.os, "stat", zero_known_git_dir)
    with pytest.raises(WorktreeIdentityUnavailable, match="stable filesystem proof"):
        code_index.compute_code_index_scope(repo)


def test_worktree_identity_accepts_relative_git_admin_paths(repo, monkeypatch):
    expected = code_index.compute_code_index_scope(repo)
    real_run_git = code_index._run_git

    def relative_admin_paths(root, *args, timeout=30.0):
        if args == ("rev-parse", "--absolute-git-dir"):
            return ".git\n"
        if args == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return ".git\n"
        return real_run_git(root, *args, timeout=timeout)

    monkeypatch.setattr(code_index, "_run_git", relative_admin_paths)
    assert code_index.compute_code_index_scope(repo) == expected


def test_worktree_identity_refuses_unreadable_marker(repo, monkeypatch):
    info = resolve_repo(repo)
    real_stat = code_index.os.stat

    def unreadable_marker(path, *args, **kwargs):
        if os.path.normcase(str(path)) == os.path.normcase(str(info.worktree.git_common_dir / "config")):
            raise PermissionError("denied")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(code_index.os, "stat", unreadable_marker)
    with pytest.raises(WorktreeIdentityUnavailable, match="stable-marker is unreadable"):
        code_index.compute_code_index_scope(repo)


def test_repo_id_is_stable_and_path_independent(repo, tmp_path):
    """repo_id remains repository-family diagnostics and survives checkout moves."""
    first = compute_repo_id(repo)
    assert compute_repo_id(repo) == first, "repo_id must be deterministic"
    moved = tmp_path / "moved-elsewhere"
    os.rename(repo, moved)
    assert compute_repo_id(moved) == first, "repo_id must survive a move (root-commit keyed)"


def test_candidates_from_roots_filters_config_and_nonrepo(repo, tmp_path):
    home_cfg = os.path.expanduser("~/.claude")
    plain = tmp_path / "plain"
    plain.mkdir()
    uris = [
        repo.as_uri(),
        (tmp_path / "does-not-exist").as_uri(),
        plain.as_uri(),
    ]
    if os.path.isdir(home_cfg):
        uris.append("file:///" + home_cfg.replace("\\", "/"))
    got = candidates_from_roots(uris)
    assert [os.path.normcase(str(p)) for p in got] == [os.path.normcase(str(repo))]


def test_candidates_from_roots_empty_means_unsupported():
    # Codex declares no roots capability but still answers with an empty array
    # rather than an error — that must fall through, not resolve to nothing.
    assert candidates_from_roots([]) == []


# ---- discovery + chunking --------------------------------------------------
def test_discover_respects_gitignore_and_skips_binaries(repo):
    cfg = Config()
    files = discover_files(repo, cfg)
    assert "app.py" in files
    assert "README.md" in files
    assert "logo.png" not in files, "binary assets must not be indexed"
    assert not any("ignored" in f for f in files), ".gitignore must be honoured"


def test_discover_git_failure_is_not_laundered_into_empty_repo(repo, monkeypatch):
    monkeypatch.setattr(code_index, "_run_git", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="git ls-files failed"):
        discover_files(repo, Config())


def test_chunk_text_covers_every_line_and_reports_real_spans():
    text = "\n".join(f"line{i}" for i in range(1, 201))
    chunks = chunk_text(text, chunk_lines=60, overlap=12)
    assert chunks
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 200, "chunking must reach the end of the file"
    for c in chunks:
        assert c.start_line <= c.end_line
        assert c.text.splitlines()[0] == f"line{c.start_line}", "reported span must match the text"


def test_chunk_text_handles_overlap_larger_than_window():
    chunks = chunk_text("a\nb\nc\nd\n", chunk_lines=2, overlap=99)
    assert chunks, "a degenerate overlap must not hang or produce nothing"


def test_chunk_text_empty():
    assert chunk_text("", 60, 12) == []
    assert chunk_text("   \n\n  \n", 60, 12) == []


# ---- indexing --------------------------------------------------------------
def test_index_then_search_finds_code(index, repo):
    info = resolve_repo(repo)
    prog = index.index_repo(info)
    assert prog.state == "done", prog.error
    assert prog.files_indexed >= 2
    hits = index.search("retry the payment capture on timeout", repo=info, top_k=5)
    assert hits, "indexed code must be retrievable"
    assert hits[0]["path"] == "app.py"
    assert hits[0]["start_line"] >= 1


def test_index_is_idempotent(index, repo):
    """Guards the uuid4 landmine: kills mid-index are routine (a daemon thread's
    `finally` never runs), so a resumed index MUST overwrite, not duplicate."""
    info = resolve_repo(repo)
    index.index_repo(info)
    first = index.status(info)["chunks_indexed"]
    index.index_repo(info, force=True)
    second = index.status(info)["chunks_indexed"]
    assert first == second, "re-indexing must overwrite, not accumulate chunks"


def test_incremental_skips_unchanged_files(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    calls_after_first = index.embedder.calls
    index.index_repo(info)
    assert index.embedder.calls == calls_after_first, "unchanged files must not be re-embedded"


def test_changed_file_is_reindexed_and_shrink_evicts_stale_chunks(index, repo):
    """A file shrinking from many chunks to few must not leave orphans behind —
    deterministic IDs overwrite survivors but cannot remove the tail."""
    info = resolve_repo(repo)
    big = repo / "big.py"
    big.write_text("\n".join(f"# padding line {i}" for i in range(400)), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "big")
    index.index_repo(info)
    before = index.status(info)["chunks_indexed"]

    big.write_text("# tiny now\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "shrink")
    index.index_repo(info)
    after = index.status(info)["chunks_indexed"]
    assert after < before, "stale chunks from the longer version must be evicted"

    hits = index.search("padding line", repo=info, top_k=10)
    assert all("padding line" not in h["text"] for h in hits), "evicted content must not resurface"


def test_file_becoming_empty_evicts_previous_chunks(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    assert index.search("payment capture", repo=info)
    (repo / "app.py").write_text("", encoding="utf-8")
    assert index.index_repo(info).state == "done"
    assert all(hit["path"] != "app.py" for hit in index.search("payment capture", repo=info))


def test_deleted_file_is_removed_from_index(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    assert index.search("payment capture", repo=info, top_k=5)
    (repo / "app.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "rm")
    index.index_repo(info)
    hits = index.search("payment capture", repo=info, top_k=5)
    assert all(h["path"] != "app.py" for h in hits), "deleted files must leave the index"


def test_repo_isolation(index, repo, tmp_path):
    """Two repos share one collection — one must never surface the other's code."""
    other = tmp_path / "other-repo"
    other.mkdir()
    _git(other, "init", "-q")
    _git(other, "config", "user.email", "t@example.invalid")
    _git(other, "config", "user.name", "t")
    (other / "unrelated.py").write_text("def quantum_flux_capacitor():\n    return 42\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-qm", "init")

    a = resolve_repo(repo)
    b = resolve_repo(other)
    index.index_repo(a)
    index.index_repo(b)

    hits = index.search("quantum flux capacitor", repo=a, top_k=5)
    assert all(h["path"] != "unrelated.py" for h in hits), "repo A must not see repo B's code"


def test_language_and_path_filters(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    py_only = index.search("sample project", repo=info, top_k=10, language="py")
    assert all(h["language"] == "py" for h in py_only)
    scoped = index.search("payment", repo=info, top_k=10, path_contains="app")
    assert all("app" in h["path"] for h in scoped)


def test_status_reports_counts(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    st = index.status(info)
    assert st["ok"] is True
    assert st["chunks_indexed"] > 0
    assert st["files_in_manifest"] > 0
    assert st["repo"] == repo.name


def test_changing_embed_model_invalidates_manifest(index, repo):
    """Vectors from a different model are meaningless — the manifest must not
    let them be treated as still-valid."""
    info = resolve_repo(repo)
    index.index_repo(info)
    index.cfg.embed_model = "text-embedding-3-large"
    calls_before = index.embedder.calls
    index.index_repo(info)
    assert index.embedder.calls > calls_before, "a model change must force re-embedding"


def test_recreated_collection_cannot_reuse_stale_manifest(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    index.client.delete_collection(index.cfg.code_collection)

    rebuilt = CodeIndex(index.cfg, embedder=FakeEmbedder())
    try:
        assert rebuilt.status(info)["index_state"] == "interrupted"
        assert rebuilt.index_repo(info).state == "done"
        assert rebuilt.embedder.calls > 0
        assert rebuilt.status(info)["index_state"] == "ready"
    finally:
        try:
            rebuilt.client.delete_collection(index.cfg.code_collection)
        except Exception:
            pass


def test_changed_collection_name_invalidates_manifest(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    cfg = Config()
    cfg.code_collection = f"mnemo_code_test_{uuid.uuid4().hex[:8]}"
    cfg.qdrant_url = QDRANT_URL
    cfg.data_dir = index.cfg.data_dir
    other = CodeIndex(cfg, embedder=FakeEmbedder())
    try:
        assert other.status(info)["index_state"] == "unindexed"
        assert other.index_repo(info).state == "done"
        manifest = Manifest(other._manifest_path(info.code_index_scope))
        assert manifest.data["code_collection"] == cfg.code_collection
    finally:
        try:
            other.client.delete_collection(cfg.code_collection)
        except Exception:
            pass


def test_v2_manifest_path_and_binding(index, repo):
    info = resolve_repo(repo)
    assert index.index_repo(info).state == "done"
    path = index._manifest_path(info.code_index_scope)
    assert path == index.cfg.code_dir / "v2" / info.code_index_scope / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 2
    assert data["identity_version"] == info.worktree.version
    assert data["repository_family_id"] == info.repo_id
    assert data["code_index_scope"] == info.code_index_scope
    assert data["proof_digest"] == info.worktree.proof_digest
    assert data["repo_root"] == str(info.root)
    assert data["embed_model"] == index.cfg.embed_model
    assert data["code_collection"] == index.cfg.code_collection
    assert data["last_index"] is not None
    assert data["snapshot_head"]


def test_missing_or_mismatched_manifest_never_queries_orphan_points(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    manifest_path = index._manifest_path(info.code_index_scope)
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.unlink()

    assert index.search("payment capture", repo=info) == []
    missing = index.status(info)
    assert missing["index_state"] == "unindexed"
    assert missing["chunks_indexed"] == 0
    assert missing["last_index"] is None

    original["proof_digest"] = "wrong-proof"
    manifest_path.write_text(json.dumps(original), encoding="utf-8")
    assert index.search("payment capture", repo=info) == []
    assert index.status(info)["index_state"] == "unindexed"


def test_corrupt_v2_manifest_is_unindexed_then_rebuilt(index, repo):
    info = resolve_repo(repo)
    path = index._manifest_path(info.code_index_scope)
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    assert index.status(info)["index_state"] == "unindexed"
    assert index.search("payment capture", repo=info) == []
    assert index.index_repo(info).state == "done"
    assert index.status(info)["index_state"] == "ready"


def test_structurally_malformed_v2_manifest_is_not_queryable(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    path = index._manifest_path(info.code_index_scope)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["files"] = {"app.py": "not-a-file-record"}
    path.write_text(json.dumps(data), encoding="utf-8")
    assert index.search("payment capture", repo=info) == []
    assert index.status(info)["index_state"] == "unindexed"


def test_legacy_manifest_and_points_remain_quarantined(index, repo):
    info = resolve_repo(repo)
    legacy_path = index.cfg.code_dir / info.repo_id / "manifest.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(json.dumps({"repo_id": info.repo_id, "files": {}}), encoding="utf-8")
    legacy_id = str(uuid.uuid4())
    index.client.upsert(
        collection_name=index.cfg.code_collection,
        points=[
            code_index.qm.PointStruct(
                id=legacy_id,
                vector=FakeEmbedder().embed_one("legacy-only-token"),
                payload={"repo_id": info.repo_id, "file_path": "legacy.py", "text": "legacy-only-token"},
            )
        ],
        wait=True,
    )

    assert index.search("legacy-only-token", repo=info) == []
    assert index.index_repo(info).state == "done"
    assert legacy_path.exists()
    points = index.client.retrieve(index.cfg.code_collection, ids=[legacy_id], with_payload=True)
    assert points and points[0].payload["repo_id"] == info.repo_id
    assert all(hit["path"] != "legacy.py" for hit in index.search("legacy-only-token", repo=info))


def test_v2_points_use_scope_payload_and_omit_legacy_repo_id(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    points, _ = index.client.scroll(
        collection_name=index.cfg.code_collection,
        scroll_filter=index._scope_filter(info.code_index_scope),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    assert points
    for point in points:
        assert point.payload["code_index_scope"] == info.code_index_scope
        assert point.payload["repository_family_id"] == info.repo_id
        assert "repo_id" not in point.payload


def test_related_worktree_and_clone_content_isolation(index, repo, tmp_path):
    linked = [tmp_path / "linked-content-a", tmp_path / "linked-content-b"]
    clones = [tmp_path / "clone-content-a", tmp_path / "clone-content-b"]
    for number, path in enumerate(linked):
        _git(repo, "worktree", "add", "-q", "-b", f"linked-content-{number}", str(path))
    for path in clones:
        _git(tmp_path, "clone", "-q", str(repo), str(path))
    unique = {
        repo: "primary_scope_albatross",
        linked[0]: "linked_scope_barracuda",
        linked[1]: "linked_scope_cassowary",
        clones[0]: "clone_scope_dormouse",
        clones[1]: "clone_scope_egret",
    }
    for root, token in unique.items():
        (root / "app.py").write_text(f"def marker():\n    return '{token}'\n", encoding="utf-8")

    infos = {root: resolve_repo(root) for root in unique}
    for info in infos.values():
        assert index.index_repo(info).state == "done"
    assert len({info.repo_id for info in infos.values()}) == 1
    assert len({info.code_index_scope for info in infos.values()}) == 5

    for root, info in infos.items():
        hits = index.search(unique[root], repo=info, top_k=10)
        assert any(unique[root] in hit["text"] for hit in hits)
        other_tokens = set(unique.values()) - {unique[root]}
        assert all(not any(token in hit["text"] for token in other_tokens) for hit in hits)
        assert index.status(info)["chunks_indexed"] > 0

    never_indexed = tmp_path / "never-indexed"
    _git(repo, "worktree", "add", "-q", "-b", "never-indexed", str(never_indexed))
    empty = index.status(resolve_repo(never_indexed))
    assert empty["index_state"] == "unindexed"
    assert empty["files_in_manifest"] == empty["chunks_indexed"] == 0
    assert empty["last_index"] is None
    assert empty["progress"]["code_index_scope"] == resolve_repo(never_indexed).code_index_scope


def test_branch_detached_head_and_local_edits_keep_scope_and_disclose_snapshot(index, repo):
    initial = resolve_repo(repo)
    index.index_repo(initial)
    completed = index.status(initial)
    indexed_head = completed["snapshot_head"]

    _git(repo, "checkout", "-q", "-b", "scope-stability")
    assert resolve_repo(repo).code_index_scope == initial.code_index_scope
    _git(repo, "checkout", "-q", "--detach", "HEAD")
    assert resolve_repo(repo).code_index_scope == initial.code_index_scope

    (repo / "app.py").write_text("def later_edit():\n    return 'not-indexed-yet'\n", encoding="utf-8")
    lagging = index.status(resolve_repo(repo))
    assert lagging["index_state"] == "ready"
    assert lagging["snapshot_head"] == indexed_head
    assert lagging["snapshot_semantics"] == "last_completed_index; current source must be verified"


def test_scope_local_delete_does_not_touch_related_worktree(index, repo, tmp_path):
    linked = tmp_path / "linked-delete"
    _git(repo, "worktree", "add", "-q", "-b", "linked-delete", str(linked))
    primary_info = resolve_repo(repo)
    linked_info = resolve_repo(linked)
    index.index_repo(primary_info)
    index.index_repo(linked_info)
    primary_before = index.status(primary_info)["chunks_indexed"]

    (linked / "app.py").unlink()
    index.index_repo(linked_info)
    assert index.status(primary_info)["chunks_indexed"] == primary_before
    assert index.search("payment capture", repo=primary_info)
    assert all(hit["path"] != "app.py" for hit in index.search("payment capture", repo=linked_info))


def test_full_reset_only_mutates_active_scope(index, repo, tmp_path):
    linked = tmp_path / "linked-full-reset"
    _git(repo, "worktree", "add", "-q", "-b", "linked-full-reset", str(linked))
    first = resolve_repo(repo)
    second = resolve_repo(linked)
    index.index_repo(first)
    index.index_repo(second)
    second_before = index.status(second)
    index.index_repo(first, force=True)
    second_after = index.status(second)
    assert second_after["chunks_indexed"] == second_before["chunks_indexed"]
    assert second_after["last_index"] == second_before["last_index"]


def test_scope_reset_failure_does_not_bind_manifest(index, repo, monkeypatch):
    info = resolve_repo(repo)

    def fail_reset(scope):
        raise RuntimeError("simulated reset failure")

    monkeypatch.setattr(index, "_delete_scope_points", fail_reset)
    progress = index.index_repo(info)
    assert progress.state == "error"
    assert not index._manifest_path(info.code_index_scope).exists()
    assert index.status(info)["index_state"] == "error"


def test_per_file_failure_does_not_stamp_completed_snapshot(index, repo, monkeypatch):
    info = resolve_repo(repo)

    def fail_file(*args, **kwargs):
        raise RuntimeError("simulated file failure")

    monkeypatch.setattr(index, "_index_file", fail_file)
    progress = index.index_repo(info)
    assert progress.state == "error"
    manifest = Manifest(index._manifest_path(info.code_index_scope))
    assert manifest.data["last_index"] is None
    assert manifest.data["indexing"] is True


def test_file_hash_failure_does_not_stamp_completed_snapshot(index, repo, monkeypatch):
    info = resolve_repo(repo)
    monkeypatch.setattr(code_index, "file_sha", lambda path: None)
    progress = index.index_repo(info)
    assert progress.state == "error"
    manifest = Manifest(index._manifest_path(info.code_index_scope))
    assert manifest.data["last_index"] is None
    assert manifest.data["indexing"] is True


def test_progress_registry_is_shared_and_scope_keyed(index, repo, tmp_path):
    linked = tmp_path / "linked-progress"
    _git(repo, "worktree", "add", "-q", "-b", "linked-progress", str(linked))
    first = resolve_repo(repo)
    second = resolve_repo(linked)
    registry = ProgressRegistry()
    foreground = CodeIndex(index.cfg, embedder=FakeEmbedder(), client=index.client, progress_registry=registry)
    background = CodeIndex(index.cfg, embedder=FakeEmbedder(), client=index.client, progress_registry=registry)
    progress = IndexProgress(state="running", code_index_scope=first.code_index_scope, files_total=3)
    background._set_progress(first.code_index_scope, progress)
    observed = foreground.progress(first.code_index_scope)
    assert observed == progress
    assert observed is not progress
    progress.files_done = 2
    assert foreground.progress(first.code_index_scope).files_done == 0
    assert foreground.progress(second.code_index_scope).state == "idle"


def test_background_indexer_coalesces_same_scope_not_related_scopes(repo, tmp_path):
    linked = tmp_path / "linked-background"
    _git(repo, "worktree", "add", "-q", "-b", "linked-background", str(linked))
    first = resolve_repo(repo)
    second = resolve_repo(linked)
    release = threading.Event()
    started: list[str] = []

    class BlockingIndex:
        def index_repo(self, info, force=False):
            started.append(info.code_index_scope)
            release.wait(5)

    background = code_index.BackgroundIndexer(BlockingIndex)
    assert background.kick(first, min_interval=0) == "started"
    assert background.kick(first, min_interval=0) == "already-running"
    assert background.kick(second, min_interval=0) == "started"
    deadline = time.time() + 2
    while len(started) < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert set(started) == {first.code_index_scope, second.code_index_scope}
    assert set(background._threads) == {first.code_index_scope, second.code_index_scope}
    release.set()
    for thread in background._threads.values():
        thread.join(timeout=2)


def test_failed_background_run_does_not_enter_success_debounce(repo):
    info = resolve_repo(repo)

    class FailedIndex:
        def index_repo(self, resolved, force=False):
            return IndexProgress(state="error", code_index_scope=resolved.code_index_scope)

    background = code_index.BackgroundIndexer(FailedIndex)
    assert background.kick(info, min_interval=300) == "started"
    background._threads[info.code_index_scope].join(timeout=2)
    assert background.kick(info, min_interval=300) == "started"
    background._threads[info.code_index_scope].join(timeout=2)


def test_lock_contention_reports_scope_local_external_build(index, repo):
    info = resolve_repo(repo)
    lock = code_index._acquire_lock(index._lock_path(info.code_index_scope))
    assert lock is not None
    try:
        progress = index.index_repo(info)
        assert progress.state == "skipped"
        assert index.status(info)["index_state"] == "building_elsewhere"
    finally:
        code_index._release_lock(lock)


def test_status_distinguishes_interrupted_and_local_build(index, repo):
    info = resolve_repo(repo)
    manifest = Manifest(index._manifest_path(info.code_index_scope))
    manifest.bind(info, index.cfg.embed_model, index.cfg.code_collection)
    manifest.flush()
    assert index.status(info)["index_state"] == "interrupted"

    index._set_progress(
        info.code_index_scope,
        IndexProgress(state="running", code_index_scope=info.code_index_scope, files_total=4),
    )
    building = index.status(info)
    assert building["index_state"] == "building"
    assert building["progress"]["code_index_scope"] == info.code_index_scope
    assert building["last_index"] is None


def test_interrupted_incremental_run_never_looks_ready(index, repo):
    info = resolve_repo(repo)
    index.index_repo(info)
    manifest = Manifest(index._manifest_path(info.code_index_scope))
    assert manifest.data["last_index"] is not None
    manifest.data["indexing"] = True
    manifest.flush()
    fresh_registry = ProgressRegistry()
    observer = CodeIndex(index.cfg, embedder=FakeEmbedder(), client=index.client, progress_registry=fresh_registry)
    status = observer.status(info)
    assert status["index_state"] == "interrupted"
    assert status["last_index"] is not None


def test_public_code_tool_signatures_and_additive_status(monkeypatch, repo):
    from mnemo import server

    assert list(inspect.signature(server.code_search).parameters) == [
        "query", "repo", "top_k", "language", "path_contains", "ctx"
    ]
    assert list(inspect.signature(server.code_index_status).parameters) == ["repo", "ctx"]
    assert list(inspect.signature(server.code_reindex).parameters) == ["repo", "full", "ctx"]

    info = resolve_repo(repo)
    response = {
        **info.as_dict(),
        "ok": True,
        "index_state": "unindexed",
        "snapshot_semantics": code_index.SNAPSHOT_SEMANTICS,
    }

    class StatusIndex:
        def status(self, resolved):
            assert resolved == info
            return response

    async def resolved(ctx, path=""):
        return info

    monkeypatch.setattr(server, "resolve_repo_for_call", resolved)
    monkeypatch.setattr(server, "code_index", lambda: StatusIndex())
    got = asyncio.run(server.code_index_status(repo=str(repo)))
    assert got["repo_id"] == got["repository_family_id"] == info.repo_id
    assert got["code_index_scope"] == info.code_index_scope
    assert got["identity_version"] == 2


def test_public_code_tool_maps_identity_failure(monkeypatch):
    from mnemo import server

    async def failed(ctx, path=""):
        raise WorktreeIdentityUnavailable("safe worktree proof unavailable")

    monkeypatch.setattr(server, "resolve_repo_for_call", failed)
    got = asyncio.run(server.code_index_status())
    assert got == {
        "error": "worktree_identity_unavailable",
        "detail": "safe worktree proof unavailable",
    }


def test_public_search_maps_initialization_failure(monkeypatch, repo):
    from mnemo import server

    info = resolve_repo(repo)

    async def resolved(ctx, path=""):
        return info

    def failed_index():
        raise RuntimeError("secret-shaped internal failure")

    monkeypatch.setattr(server, "resolve_repo_for_call", resolved)
    monkeypatch.setattr(server, "code_index", failed_index)
    response = asyncio.run(server.code_search("query", repo=str(repo)))
    assert response["error"] == "search_failed"
    assert response["detail"] == "code search failed; check mnemo server logs"
    assert "secret-shaped" not in str(response)


def test_public_search_reports_scope_snapshot_and_unindexed_hint(index, repo, monkeypatch):
    from mnemo import server

    info = resolve_repo(repo)

    async def resolved(ctx, path=""):
        return info

    class NoopIndexer:
        def kick(self, *args, **kwargs):
            return "started"

    monkeypatch.setattr(server, "resolve_repo_for_call", resolved)
    monkeypatch.setattr(server, "code_index", lambda: index)
    monkeypatch.setattr(server, "_indexer", NoopIndexer())
    empty = asyncio.run(server.code_search("payment capture", repo=str(repo)))
    assert empty["count"] == 0
    assert empty["results"] == []
    assert empty["index_state"] == "unindexed"
    assert "this worktree scope" in empty["hint"]
    assert empty["snapshot_semantics"] == code_index.SNAPSHOT_SEMANTICS
    assert empty["note"].startswith("Index locates, source decides")

    index.index_repo(info)
    ready = asyncio.run(server.code_search("payment capture", repo=str(repo)))
    assert ready["index_state"] == "ready"
    assert ready["last_index"] is not None
    assert all(hit["path"] != "" for hit in ready["results"])


def test_public_reindex_targets_resolved_scope(monkeypatch, repo):
    from mnemo import server

    info = resolve_repo(repo)
    seen = {}

    async def resolved(ctx, path=""):
        return info

    class RecordingIndexer:
        def kick(self, resolved_info, full=False, min_interval=300.0):
            seen.update(scope=resolved_info.code_index_scope, full=full, min_interval=min_interval)
            return "started"

    class StatusIndex:
        def status(self, resolved_info):
            return {**resolved_info.as_dict(), "index_state": "building"}

    monkeypatch.setattr(server, "resolve_repo_for_call", resolved)
    monkeypatch.setattr(server, "_indexer", RecordingIndexer())
    monkeypatch.setattr(server, "code_index", lambda: StatusIndex())
    response = asyncio.run(server.code_reindex(repo=str(repo), full=True))
    assert seen == {"scope": info.code_index_scope, "full": True, "min_interval": 0.0}
    assert response["started"] == "started"
    assert response["full"] is True
    assert response["index_state"] == "building"
    assert response["code_index_scope"] == info.code_index_scope


def test_public_reindex_does_not_fail_after_background_start(monkeypatch, repo):
    from mnemo import server

    info = resolve_repo(repo)

    async def resolved(ctx, path=""):
        return info

    class StartedIndexer:
        def kick(self, *args, **kwargs):
            return "started"

    def foreground_should_not_be_needed():
        raise RuntimeError("foreground client unavailable")

    monkeypatch.setattr(server, "resolve_repo_for_call", resolved)
    monkeypatch.setattr(server, "_indexer", StartedIndexer())
    monkeypatch.setattr(server, "code_index", foreground_should_not_be_needed)
    response = asyncio.run(server.code_reindex(repo=str(repo)))
    assert response["started"] == "started"
    assert response["index_state"] == "building"


# ---- embedder batching -----------------------------------------------------
def test_embed_batches_preserve_order():
    """Guards the worst bug in the feature: OpenAI's data[].index is
    REQUEST-relative, so sorting across concatenated sub-batch responses silently
    attaches vectors to the wrong chunks — no exception, no log, just confidently
    wrong search results forever."""
    from mnemo import embedders

    class FakeResp:
        def __init__(self, data):
            self.data = data

    class FakeDatum:
        def __init__(self, index, embedding):
            self.index = index
            self.embedding = embedding

    class FakeClient:
        def __init__(self):
            self.embeddings = self
            self.batches = []

        def create(self, model, input):
            self.batches.append(list(input))
            # Return SHUFFLED data with request-relative indices, exactly like the
            # real API may.
            data = [FakeDatum(i, [float(len(t))]) for i, t in enumerate(input)]
            return FakeResp(list(reversed(data)))

    emb = embedders.OpenAIEmbedder.__new__(embedders.OpenAIEmbedder)
    emb._client = FakeClient()
    emb.model = "text-embedding-3-small"
    emb.dim = 1
    emb._tok = embedders._Tokenizer("text-embedding-3-small")

    texts = ["x" * (i + 1) for i in range(300)]  # forces >1 sub-batch (cap 128)
    vectors = emb.embed(texts)
    assert len(emb._client.batches) > 1, "test must actually exercise sub-batching"
    assert len(vectors) == len(texts)
    for text, vec in zip(texts, vectors):
        assert vec[0] == float(len(text)), "each vector must stay attached to its own text"


def test_embed_empty_and_oversized_inputs():
    from mnemo import embedders

    tok = embedders._Tokenizer("text-embedding-3-small")
    huge = "word " * 50_000
    truncated, was = tok.truncate(huge)
    assert was is True
    assert tok.count(truncated) <= embedders.MAX_INPUT_TOKENS


def test_tokenizer_handles_special_token_literals():
    """Source code legitimately contains <|endoftext|>-shaped strings; tiktoken
    raises ValueError on those unless disallowed_special=() is passed."""
    from mnemo import embedders

    tok = embedders._Tokenizer("text-embedding-3-small")
    assert tok.count("prompt = '<|endoftext|>'") > 0


# --- git subprocess hygiene -------------------------------------------------
# These two pin the fix for a hang that no end-to-end test here can see: pytest's
# stdin is not a JSON-RPC pipe, so the deadlock only reproduces under a real stdio
# MCP host. Pin the call contract instead of the behaviour.


def test_run_git_never_inherits_stdin(monkeypatch):
    """stdin=DEVNULL is what keeps git from blocking on the MCP JSON-RPC pipe.

    capture_output redirects stdout/stderr only. Without an explicit stdin the
    child inherits the server's, and git blocks at startup querying that handle.
    """
    seen = {}

    def fake_run(*a, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(a[0], 0, b"", b"")

    monkeypatch.setattr(code_index.subprocess, "run", fake_run)
    code_index._run_git(".", "rev-parse", "--show-toplevel")
    assert seen["stdin"] is subprocess.DEVNULL


def test_run_git_raises_rather_than_lying_on_timeout(monkeypatch):
    """A broken git must not be laundered into a negative answer.

    Returning None here would become "not inside a git repository" for a directory
    that is one, and would let discover_files report zero files -- which evicts the
    whole index and stamps it done.
    """

    def fake_run(*a, **kw):
        raise subprocess.TimeoutExpired(a[0], 5.0)

    monkeypatch.setattr(code_index.subprocess, "run", fake_run)
    with pytest.raises(GitUnavailable):
        code_index._run_git(".", "rev-parse", "--show-toplevel")
    assert issubclass(GitUnavailable, RepoUnresolved), "existing handlers must still catch it"
