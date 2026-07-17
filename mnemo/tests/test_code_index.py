"""Code-index tests against a real Qdrant on port 1337, using a deterministic
fake embedder (no network / no OpenAI cost). Each run uses a throwaway
collection that is deleted on teardown.

Run:  py -3.12 -m pytest mnemo/tests -q
Skips automatically if Qdrant is unreachable.

Several tests here guard failure modes that produce NO exception and NO log —
they would silently return wrong code forever. Those are called out inline.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mnemo import code_index  # noqa: E402
from mnemo.code_index import (  # noqa: E402
    CodeIndex,
    GitUnavailable,
    RepoUnresolved,
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


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable on 1337")


def _git(root, *args):
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True)


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


def test_repo_id_is_stable_and_path_independent(repo, tmp_path):
    """repo_id keys the shared index. Two agents must derive the same one, and it
    must survive the checkout moving (this repo moved off Desktop once already)."""
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
