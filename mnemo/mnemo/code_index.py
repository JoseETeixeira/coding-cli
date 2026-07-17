"""Automatic codebase indexing for mnemo.

The code index is a *rebuildable cache*, deliberately separate from memory:

  git-tracked files -> line-window chunks -> OpenAI embeddings
      -> Qdrant collection `mnemo_code` (payload is the source of truth)
      -> per-repo manifest (~/.mnemo/code/<repo_id>/manifest.json) for incrementality

It lives inside the mnemo MCP server rather than in a host hook, because that is
the only surface every agent shares: Claude Code hooks do not exist in Codex.
Two agents pointed at the same Qdrant therefore share one index — whichever
indexes first, both query.

Three constraints here are load-bearing and were established empirically
(see ADR 0007); changing them silently corrupts the index:

  * Chunk point IDs are uuid5(repo_id:path:chunk_idx), never uuid4. Hosts reap
    stdio servers with TerminateProcess and a daemon thread's `finally` never
    runs, so interrupted indexes are ROUTINE. Deterministic IDs make a resumed
    index overwrite; uuid4 would duplicate every chunk on every kill.
  * Order per file is: embed -> Qdrant upsert -> sweep stale chunks -> record in
    manifest. The manifest may UNDER-approximate what Qdrant holds (costs
    idempotent rework) but must never OVER-approximate (a file recorded but not
    upserted is permanently stale and never self-heals).
  * Repo resolution never guesses. An unresolved repo returns a typed error
    instead of indexing whatever directory the process happened to start in.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from .config import Config
from .embedders import Embedder, make_embedder

# NB: stdout is the JSON-RPC channel. Never print() from here — log only.
log = logging.getLogger("mnemo.code_index")

_CHUNK_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00cf4fc964ff")

NOINDEX_MARKER = ".mnemo-noindex"

# Directories that are never worth embedding even when git tracks them.
_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "dist", "build", "target", "vendor",
    ".git", ".idea", ".vscode", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".cocoindex", "site-packages", ".next", ".nuxt", "coverage", ".tox",
}

_SKIP_SUFFIXES = {
    ".lock", ".min.js", ".min.css", ".map", ".snap",
}

# Text/source extensions worth indexing. Everything else is skipped — binaries
# and assets waste tokens and pollute results.
_CODE_SUFFIXES = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".go", ".rs", ".java", ".kt", ".kts", ".scala", ".rb", ".php", ".cs", ".fs",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".m", ".mm", ".swift",
    ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".bat", ".cmd",
    ".sql", ".graphql", ".gql", ".proto", ".thrift",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".properties",
    ".md", ".mdx", ".rst", ".txt", ".adoc",
    ".tf", ".tfvars", ".hcl", ".dockerfile", ".gradle", ".cmake", ".mk",
    ".dm", ".dme", ".dmf", ".dms",  # BYOND / DreamMaker
    ".gd", ".tres", ".tscn", ".gdshader",  # Godot
    ".lua", ".luau", ".dart", ".ex", ".exs", ".erl", ".hs", ".ml", ".clj", ".r",
    ".glsl", ".hlsl", ".vert", ".frag", ".comp", ".shader",
}

_NAMED_FILES = {
    "Dockerfile", "Makefile", "Rakefile", "Gemfile", "Procfile", "Jenkinsfile",
    "CMakeLists.txt", "SConstruct", "SConscript", "BUILD", "WORKSPACE",
}


# ---------------------------------------------------------------------------
# repo resolution
# ---------------------------------------------------------------------------
class RepoUnresolved(Exception):
    """Raised instead of guessing a repo. Guessing writes chunks under the wrong
    key and both agents then read a poisoned index with no error surfaced."""


class GitUnavailable(RepoUnresolved):
    """git could not answer -- it timed out or failed to spawn.

    This is NOT a negative answer, and conflating the two is what turned a stalled
    git into a confident, false "not inside a git repository" for a directory that
    plainly was one. Subclasses RepoUnresolved so existing handlers keep working;
    they just stop lying about why.
    """


@dataclass
class RepoInfo:
    root: Path
    repo_id: str
    name: str

    def as_dict(self) -> dict:
        return {"repo": self.name, "repo_id": self.repo_id, "root": str(self.root)}


def _run_git(root: Path | str, *args: str, timeout: float = 30.0) -> str | None:
    """None means git answered "no" (non-zero exit). It never means git broke.

    stdin=DEVNULL is load-bearing, not hygiene. capture_output redirects stdout and
    stderr only, so without it the child inherits the server's stdin -- under stdio
    MCP that is the live JSON-RPC pipe, on which the server's own reader already has
    a blocking read pending. The child blocks at startup querying that handle and
    only the timeout below breaks it. Measured: memory_status 31.10s -> 1.25s.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("git %s failed in %s: %s", " ".join(args), root, exc)
        raise GitUnavailable(f"git {' '.join(args)} failed in {root}: {exc}") from exc
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace")


def _protected_dirs() -> set[str]:
    """Directories we refuse to index: home, drive/filesystem roots, agent config."""
    home = Path.home()
    out = {os.path.normcase(str(home.resolve()))}
    for cfg in (".claude", ".codex", ".agents", ".mnemo", ".config"):
        out.add(os.path.normcase(str((home / cfg).resolve())))
    root = Path(os.path.abspath(os.sep))
    out.add(os.path.normcase(str(root)))
    if os.name == "nt":
        drive = os.path.splitdrive(str(home))[0]
        if drive:
            out.add(os.path.normcase(drive + os.sep))
    return out


def git_toplevel(start: Path | str) -> Path | None:
    """Repo root for `start`, or None. Normalises git's forward-slash output —
    on Windows `git rev-parse` returns C:/x while os.getcwd() returns C:\\x, so a
    raw == between them is always False."""
    if not Path(start).is_dir():
        return None
    # 5s, not the 30s default: this sits on the preflight path, where a stall is
    # indistinguishable from a hang. A local rev-parse that hasn't answered in 5s
    # never will. ls-files keeps the longer budget -- it legitimately needs it.
    out = _run_git(start, "rev-parse", "--show-toplevel", timeout=5.0)
    if not out or not out.strip():
        return None
    return Path(os.path.abspath(out.strip()))


def compute_repo_id(root: Path) -> str:
    """Stable id shared by every agent looking at the same repo.

    Prefers the root-commit SHA so the index survives the checkout moving on
    disk (this very repo moved off Desktop on 2026-07-15; a path-keyed id would
    have orphaned its index). Falls back to the normalised path for shallow or
    commit-less repos.
    """
    out = _run_git(root, "rev-list", "--max-parents=0", "HEAD", timeout=5.0)
    if out and out.strip():
        first = out.strip().splitlines()[0].strip()
        if first:
            return f"g{first[:16]}"
    norm = os.path.normcase(os.path.abspath(str(root)))
    return "p" + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def resolve_repo(candidate: str | Path | None, cfg: Config | None = None) -> RepoInfo:
    """Turn a candidate directory into a RepoInfo, or raise RepoUnresolved.

    Refuses $HOME, drive roots, agent config dirs, non-git dirs, and any repo
    carrying a .mnemo-noindex marker.
    """
    if not candidate:
        raise RepoUnresolved("no repository candidate was provided")
    path = Path(os.path.expanduser(str(candidate)))
    if not path.is_dir():
        raise RepoUnresolved(f"'{candidate}' is not an existing directory")

    root = git_toplevel(path)
    if root is None:
        raise RepoUnresolved(f"'{path}' is not inside a git repository (code indexing is git-only)")

    norm = os.path.normcase(str(root))
    if norm in _protected_dirs():
        raise RepoUnresolved(
            f"refusing to index '{root}' (home, drive root, or agent config directory)"
        )
    if (root / NOINDEX_MARKER).exists():
        raise RepoUnresolved(f"'{root}' opts out of indexing via {NOINDEX_MARKER}")

    return RepoInfo(root=root, repo_id=compute_repo_id(root), name=root.name)


def candidates_from_roots(root_uris: Iterable[str]) -> list[Path]:
    """Filter MCP `roots/list` URIs down to plausible repos.

    Claude Code returns several roots (the project plus every additional working
    dir — a live probe returned ~/.claude alongside the project), and never sets
    Root.name. Codex has no roots capability but still answers with an empty
    array rather than an error, so an empty list means "unsupported", not "no
    repo".
    """
    from urllib.parse import unquote, urlparse
    from urllib.request import url2pathname

    protected = _protected_dirs()
    out: list[Path] = []
    for uri in root_uris:
        try:
            parsed = urlparse(str(uri))
            if parsed.scheme and parsed.scheme != "file":
                continue
            # Never string-strip "file://" — that breaks drive letters and
            # percent-encoding (this user has paths like "Ambiente%20de%20Trabalho").
            path = Path(url2pathname(unquote(parsed.path)))
        except Exception:
            continue
        if not path.is_dir():
            continue  # stale root: a probe returned the pre-move Desktop path
        if os.path.normcase(str(path)) in protected:
            continue
        if not (path / ".git").exists():
            continue
        out.append(path)
    return out


# ---------------------------------------------------------------------------
# discovery + chunking
# ---------------------------------------------------------------------------
def _eligible(rel: str, cfg: Config, root: Path) -> bool:
    parts = Path(rel).parts
    if any(p in _SKIP_DIRS for p in parts):
        return False
    name = Path(rel).name
    if name in _NAMED_FILES:
        return True
    lower = name.lower()
    if any(lower.endswith(s) for s in _SKIP_SUFFIXES):
        return False
    if Path(lower).suffix not in _CODE_SUFFIXES:
        return False
    try:
        if (root / rel).stat().st_size > cfg.code_max_file_bytes:
            return False
    except OSError:
        return False
    return True


def discover_files(root: Path, cfg: Config) -> list[str]:
    """Repo-relative paths worth indexing, via git so .gitignore is honoured free.

    `-z` is required, not cosmetic: core.quotepath defaults ON, so without it git
    returns non-ASCII names as escaped literals ("acentua\\303\\247\\303\\243o.py").
    """
    out = _run_git(root, "ls-files", "-z")
    if out is None:
        return []
    rels = [p for p in out.split("\0") if p]
    if cfg.code_include_untracked:
        extra = _run_git(root, "ls-files", "-z", "--others", "--exclude-standard")
        if extra:
            rels.extend(p for p in extra.split("\0") if p)
    seen: set[str] = set()
    keep: list[str] = []
    for rel in rels:
        if rel in seen:
            continue
        seen.add(rel)
        if _eligible(rel, cfg, root):
            keep.append(rel)
    return keep


@dataclass
class Chunk:
    index: int
    start_line: int
    end_line: int
    text: str


def chunk_text(text: str, chunk_lines: int, overlap: int) -> list[Chunk]:
    """Overlapping line windows, snapped to blank lines where one is nearby.

    Deliberately language-agnostic: a real parser per language is not worth the
    complexity when the index only has to *locate* code that the agent then
    opens and reads.
    """
    lines = text.splitlines()
    if not lines:
        return []
    if overlap >= chunk_lines:
        overlap = max(0, chunk_lines // 4)
    step = max(1, chunk_lines - overlap)

    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(lines):
        end = min(start + chunk_lines, len(lines))
        # Prefer a blank-line boundary near the window edge so chunks tend to
        # end between definitions rather than mid-body.
        if end < len(lines):
            for probe in range(end, max(end - 8, start + 1), -1):
                if not lines[probe - 1].strip():
                    end = probe
                    break
        body = "\n".join(lines[start:end])
        if body.strip():
            chunks.append(Chunk(index=idx, start_line=start + 1, end_line=end, text=body))
            idx += 1
        if end >= len(lines):
            break
        start = max(end - overlap, start + step)
    return chunks


def file_sha(path: Path) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw[:8192]:
        return None  # binary despite an allowed extension
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
class Manifest:
    """Per-repo incremental state. A cache — safe to delete; the index rebuilds.

    Flushed via atomic os.replace so a killed process never leaves a torn file.
    """

    FLUSH_EVERY = 50

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"files": {}, "repo_id": None, "embed_model": None, "last_index": None}
        self._pending = 0
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("files"), dict):
                    self.data = loaded
        except (OSError, ValueError) as exc:
            log.warning("manifest unreadable (%s); rebuilding from scratch", exc)

    @property
    def files(self) -> dict[str, Any]:
        return self.data.setdefault("files", {})

    def record(self, rel: str, sha: str, chunks: int) -> None:
        self.files[rel] = {"sha": sha, "chunks": chunks, "indexed_at": time.time()}
        self._pending += 1
        if self._pending >= self.FLUSH_EVERY:
            self.flush()

    def drop(self, rel: str) -> None:
        if self.files.pop(rel, None) is not None:
            self._pending += 1

    def unchanged(self, rel: str, sha: str) -> bool:
        entry = self.files.get(rel)
        return bool(entry and entry.get("sha") == sha)

    def flush(self) -> None:
        self._pending = 0
        tmp = self.path.with_suffix(".json.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.data), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("could not flush manifest %s: %s", self.path, exc)


# ---------------------------------------------------------------------------
# indexer
# ---------------------------------------------------------------------------
@dataclass
class IndexProgress:
    state: str = "idle"  # idle | running | done | error | skipped
    repo: str | None = None
    repo_id: str | None = None
    files_total: int = 0
    files_done: int = 0
    files_indexed: int = 0
    chunks_written: int = 0
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict:
        out = {k: v for k, v in self.__dict__.items() if v is not None}
        if self.state == "running" and self.files_total:
            out["percent"] = round(100.0 * self.files_done / self.files_total, 1)
        return out


class CodeIndex:
    """Owns the `mnemo_code` collection. Never touches mnemo_memory."""

    def __init__(self, cfg: Config, embedder: Embedder | None = None, client: QdrantClient | None = None):
        self.cfg = cfg
        cfg.ensure_dirs()
        self.embedder = embedder or make_embedder(cfg)
        self.dim = self.embedder.dim
        self.client = client or QdrantClient(url=cfg.qdrant_url, timeout=60)
        self._progress: dict[str, IndexProgress] = {}
        self._progress_lock = threading.Lock()
        self._ensure_collection()

    # ---- setup -----------------------------------------------------------
    def _ensure_collection(self) -> None:
        name = self.cfg.code_collection
        try:
            exists = self.client.collection_exists(name)
        except Exception:
            try:
                self.client.get_collection(name)
                exists = True
            except Exception:
                exists = False
        if exists:
            return
        try:
            self.client.create_collection(
                collection_name=name,
                vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE),
            )
        except Exception as exc:  # concurrent creation by another agent is fine
            log.debug("create_collection(%s): %s", name, exc)
        # Without these, per-file eviction degrades to a full scan on the hot path.
        for field_name in ("repo_id", "file_path", "file_hash", "language"):
            try:
                self.client.create_payload_index(name, field_name=field_name, field_schema=qm.PayloadSchemaType.KEYWORD)
            except Exception:
                pass

    # ---- progress --------------------------------------------------------
    def progress(self, repo_id: str) -> IndexProgress:
        with self._progress_lock:
            return self._progress.get(repo_id, IndexProgress())

    def _set_progress(self, repo_id: str, prog: IndexProgress) -> None:
        with self._progress_lock:
            self._progress[repo_id] = prog

    # ---- paths -----------------------------------------------------------
    def _repo_dir(self, repo_id: str) -> Path:
        return self.cfg.code_dir / repo_id

    def _manifest_path(self, repo_id: str) -> Path:
        return self._repo_dir(repo_id) / "manifest.json"

    def _lock_path(self, repo_id: str) -> Path:
        return self._repo_dir(repo_id) / "index.lock"

    # ---- qdrant ----------------------------------------------------------
    @staticmethod
    def _point_id(repo_id: str, rel: str, chunk_idx: int) -> str:
        # Deterministic: a resumed index overwrites instead of duplicating.
        return str(uuid.uuid5(_CHUNK_NS, f"{repo_id}:{rel}:{chunk_idx}"))

    def _delete_file_points(self, repo_id: str, rel: str, keep_hash: str | None = None) -> None:
        must: list[Any] = [
            qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id)),
            qm.FieldCondition(key="file_path", match=qm.MatchValue(value=rel)),
        ]
        flt = qm.Filter(must=must)
        if keep_hash is not None:
            # Shrink sweep: survivors carry the new hash, stragglers from a
            # longer previous version do not.
            flt = qm.Filter(
                must=must,
                must_not=[qm.FieldCondition(key="file_hash", match=qm.MatchValue(value=keep_hash))],
            )
        try:
            self.client.delete(
                collection_name=self.cfg.code_collection,
                # FilterSelector must be explicit — points_selector is overloaded
                # and a bare list means delete-by-ID.
                points_selector=qm.FilterSelector(filter=flt),
                wait=True,
            )
        except Exception as exc:
            log.warning("failed evicting points for %s: %s", rel, exc)

    def _upsert(self, points: list[qm.PointStruct]) -> None:
        self.client.upsert(collection_name=self.cfg.code_collection, points=points, wait=True)

    # ---- indexing --------------------------------------------------------
    def index_repo(self, repo: RepoInfo, force: bool = False) -> IndexProgress:
        """Incrementally index a repo. Safe to kill at any point: the next run
        resumes and any duplicated work is idempotent."""
        prog = IndexProgress(state="running", repo=repo.name, repo_id=repo.repo_id, started_at=time.time())
        self._set_progress(repo.repo_id, prog)

        lock = _acquire_lock(self._lock_path(repo.repo_id))
        if lock is None:
            prog.state = "skipped"
            prog.detail = "another agent is indexing this repo"
            prog.finished_at = time.time()
            self._set_progress(repo.repo_id, prog)
            return prog

        try:
            manifest = Manifest(self._manifest_path(repo.repo_id))
            if force or manifest.data.get("embed_model") not in (None, self.cfg.embed_model):
                # A different embedder means every stored vector is meaningless.
                manifest.data["files"] = {}
            manifest.data["repo_id"] = repo.repo_id
            manifest.data["repo_root"] = str(repo.root)
            manifest.data["embed_model"] = self.cfg.embed_model

            files = discover_files(repo.root, self.cfg)
            prog.files_total = len(files)
            self._set_progress(repo.repo_id, prog)

            live = set(files)
            for gone in [r for r in list(manifest.files) if r not in live]:
                self._delete_file_points(repo.repo_id, gone)
                manifest.drop(gone)

            for rel in files:
                prog.files_done += 1
                abs_path = repo.root / rel
                sha = file_sha(abs_path)
                if sha is None:
                    continue
                if not force and manifest.unchanged(rel, sha):
                    continue
                try:
                    written = self._index_file(repo, rel, abs_path, sha, manifest)
                except Exception as exc:
                    log.warning("indexing %s failed: %s", rel, exc)
                    continue
                if written:
                    prog.files_indexed += 1
                    prog.chunks_written += written
                self._set_progress(repo.repo_id, prog)

            manifest.data["last_index"] = time.time()
            manifest.flush()
            prog.state = "done"
            prog.finished_at = time.time()
        except Exception as exc:
            log.exception("index_repo failed for %s", repo.name)
            prog.state = "error"
            prog.error = str(exc)
            prog.finished_at = time.time()
        finally:
            _release_lock(lock)
        self._set_progress(repo.repo_id, prog)
        return prog

    def _index_file(self, repo: RepoInfo, rel: str, abs_path: Path, sha: str, manifest: Manifest) -> int:
        text = read_text(abs_path)
        if text is None or not text.strip():
            return 0
        chunks = chunk_text(text, self.cfg.code_chunk_lines, self.cfg.code_chunk_overlap)
        if not chunks:
            return 0

        language = Path(rel).suffix.lstrip(".").lower() or Path(rel).name.lower()
        vectors = self.embedder.embed([c.text for c in chunks])

        points = [
            qm.PointStruct(
                id=self._point_id(repo.repo_id, rel, c.index),
                vector=vec,
                payload={
                    "repo_id": repo.repo_id,
                    "repo": repo.name,
                    "file_path": rel,
                    "file_hash": sha,
                    "language": language,
                    "chunk_index": c.index,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "text": c.text,
                    "indexed_at": time.time(),
                },
            )
            for c, vec in zip(chunks, vectors)
        ]

        # Order matters: upsert -> sweep -> record. Reversing it would let a kill
        # leave the manifest claiming a file is indexed when it is not.
        self._upsert(points)
        self._delete_file_points(repo.repo_id, rel, keep_hash=sha)
        manifest.record(rel, sha, len(points))
        return len(points)

    # ---- query -----------------------------------------------------------
    def search(
        self,
        query: str,
        repo: RepoInfo,
        top_k: int = 8,
        language: str | None = None,
        path_contains: str | None = None,
    ) -> list[dict]:
        must: list[Any] = [qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo.repo_id))]
        if language:
            must.append(qm.FieldCondition(key="language", match=qm.MatchValue(value=language.lstrip(".").lower())))
        flt = qm.Filter(must=must)
        vector = self.embedder.embed_one(query)
        # Over-fetch so a path filter still has candidates to keep.
        limit = top_k * 4 if path_contains else top_k
        try:
            resp = self.client.query_points(
                collection_name=self.cfg.code_collection,
                query=vector,
                query_filter=flt,
                limit=limit,
                with_payload=True,
            )
            points = resp.points
        except AttributeError:  # older client
            points = self.client.search(
                collection_name=self.cfg.code_collection,
                query_vector=vector,
                query_filter=flt,
                limit=limit,
                with_payload=True,
            )
        out: list[dict] = []
        for p in points:
            payload = p.payload or {}
            rel = payload.get("file_path", "")
            if path_contains and path_contains.lower() not in rel.lower():
                continue
            out.append(
                {
                    "path": rel,
                    "start_line": payload.get("start_line"),
                    "end_line": payload.get("end_line"),
                    "language": payload.get("language"),
                    "score": round(float(getattr(p, "score", 0.0)), 4),
                    "text": payload.get("text", ""),
                }
            )
            if len(out) >= top_k:
                break
        return out

    def status(self, repo: RepoInfo) -> dict:
        manifest = Manifest(self._manifest_path(repo.repo_id))
        try:
            count = self.client.count(
                collection_name=self.cfg.code_collection,
                count_filter=qm.Filter(must=[qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo.repo_id))]),
                exact=True,
            ).count
        except Exception as exc:
            return {**repo.as_dict(), "ok": False, "error": str(exc)}
        prog = self.progress(repo.repo_id)
        return {
            **repo.as_dict(),
            "ok": True,
            "collection": self.cfg.code_collection,
            "embed_model": self.cfg.embed_model,
            "files_in_manifest": len(manifest.files),
            "chunks_indexed": count,
            "last_index": manifest.data.get("last_index"),
            "auto_index": self.cfg.code_auto_index,
            "progress": prog.as_dict(),
        }


# ---------------------------------------------------------------------------
# locking
# ---------------------------------------------------------------------------
def _acquire_lock(path: Path):
    """Non-blocking OS-level lock; None when another process holds it.

    Uses filelock so the kernel releases on process death — including
    TerminateProcess, which is how hosts reap stdio servers. A userspace lock
    cannot do this: a daemon thread's `finally` never runs, so every interrupted
    session would leak its lock forever. Contention means "someone else is
    already indexing", so skipping is correct — indexing is best-effort.

    engine._DirLock is deliberately NOT reused: it breaks locks on a timeout with
    no liveness check, and its __exit__ deletes whatever lock dir exists, so an
    evicted holder destroys the new owner's lock.
    """
    try:
        from filelock import FileLock, Timeout
    except ImportError:
        log.warning("filelock unavailable; proceeding without a cross-process index lock")
        return _NULL_LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        return None
    except OSError as exc:
        log.warning("could not acquire index lock %s: %s", path, exc)
        return _NULL_LOCK
    return lock


_NULL_LOCK = object()


def _release_lock(lock) -> None:
    if lock is None or lock is _NULL_LOCK:
        return
    try:
        lock.release()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# background trigger
# ---------------------------------------------------------------------------
class BackgroundIndexer:
    """Runs index_repo off the event loop.

    Necessary rather than merely nice: FastMCP calls sync @mcp.tool() functions
    directly on the asyncio loop (mcp 1.26.0 func_metadata.py:92-95 — no
    to_thread, unlike resources), so any indexing done inline would stall every
    other tool call for the whole run.
    """

    def __init__(self, index_factory):
        self._factory = index_factory
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._done: dict[str, float] = {}

    def kick(self, repo: RepoInfo, full: bool = False, min_interval: float = 300.0) -> str:
        """Start a background index unless one is live or ran very recently.

        `full` rebuilds from scratch (ignores the manifest); `min_interval=0`
        bypasses the debounce. They are independent knobs — an explicit
        code_reindex wants the debounce off but not necessarily a full rebuild.
        """
        with self._lock:
            live = self._threads.get(repo.repo_id)
            if live is not None and live.is_alive():
                return "already-running"
            last = self._done.get(repo.repo_id)
            if min_interval > 0 and last is not None and (time.time() - last) < min_interval:
                return "recently-indexed"

            def run() -> None:
                try:
                    # Own clients: sidesteps sharing a QdrantClient/OpenAI client
                    # across the loop thread and this one.
                    self._factory().index_repo(repo, force=full)
                except Exception:
                    log.exception("background index failed for %s", repo.name)
                finally:
                    with self._lock:
                        self._done[repo.repo_id] = time.time()

            thread = threading.Thread(target=run, name=f"mnemo-index-{repo.name}", daemon=True)
            self._threads[repo.repo_id] = thread
            thread.start()
            return "started"
