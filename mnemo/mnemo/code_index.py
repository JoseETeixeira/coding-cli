"""Automatic codebase indexing for mnemo.

The code index is a *rebuildable cache*, deliberately separate from memory:

  git-tracked files -> line-window chunks -> OpenAI embeddings
      -> Qdrant collection `mnemo_code` (payload is the source of truth)
      -> per-worktree v2 manifest (~/.mnemo/code/v2/<scope>/manifest.json)

It lives inside the mnemo MCP server rather than in a host hook, because that is
the only surface every agent shares: Claude Code hooks do not exist in Codex.
Two agents pointed at the same physical worktree share one scope. Related
worktrees and clones remain isolated even when they share Git history.

Three constraints here are load-bearing and were established empirically
(see ADR 0018); changing them silently corrupts the index:

  * Chunk point IDs are uuid5(scope:path:chunk_idx), never uuid4. Hosts reap
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
import stat
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from .config import Config
from .embedders import Embedder, make_embedder

# NB: stdout is the JSON-RPC channel. Never print() from here — log only.
log = logging.getLogger("mnemo.code_index")

_CHUNK_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00cf4fc964ff")
IDENTITY_VERSION = 2
MANIFEST_SCHEMA_VERSION = 2
SNAPSHOT_SEMANTICS = "last_completed_index; current source must be verified"

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


class WorktreeIdentityUnavailable(RepoUnresolved):
    """The repository exists, but a safe per-worktree proof is unavailable."""


@dataclass(frozen=True)
class WorktreeIdentity:
    version: int
    canonical_root: Path
    git_dir: Path
    git_common_dir: Path
    proof_digest: str
    code_index_scope: str


@dataclass(frozen=True)
class RepoInfo:
    root: Path
    repo_id: str
    name: str
    worktree: WorktreeIdentity

    @property
    def code_index_scope(self) -> str:
        return self.worktree.code_index_scope

    def as_dict(self) -> dict:
        return {
            "repo": self.name,
            "repo_id": self.repo_id,
            "repository_family_id": self.repo_id,
            "root": str(self.root),
            "code_index_scope": self.code_index_scope,
            "identity_version": self.worktree.version,
        }


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


def _canonical_path(path: Path | str) -> Path:
    try:
        return Path(path).resolve(strict=True)
    except OSError as exc:
        raise WorktreeIdentityUnavailable("worktree identity path is missing or unreadable") from exc


def _canonical_git_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return _canonical_path(candidate)


def _path_identity(path: Path, label: str, *, require_incarnation_clock: bool) -> list[str]:
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise WorktreeIdentityUnavailable(f"worktree identity {label} is unreadable") from exc
    device = int(getattr(metadata, "st_dev", 0) or 0)
    file_id = int(getattr(metadata, "st_ino", 0) or 0)
    birth_ns = int(getattr(metadata, "st_birthtime_ns", 0) or 0)
    if not birth_ns:
        birth = float(getattr(metadata, "st_birthtime", 0.0) or 0.0)
        birth_ns = int(birth * 1_000_000_000)
    clock_ns = birth_ns
    if not clock_ns and require_incarnation_clock:
        clock_ns = int(getattr(metadata, "st_ctime_ns", 0) or 0)
    if not device or not file_id or (require_incarnation_clock and not clock_ns):
        raise WorktreeIdentityUnavailable(f"worktree identity {label} lacks stable filesystem proof")
    return [label, str(stat.S_IFMT(metadata.st_mode)), str(device), str(file_id), str(clock_ns)]


def _hash_identity_parts(parts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        raw = part.encode("utf-8", errors="surrogatepass")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def compute_code_index_scope(root: Path) -> WorktreeIdentity:
    """Derive one opaque, fail-closed identity for this worktree incarnation."""
    canonical_root = _canonical_path(root)
    git_dir_raw = _run_git(canonical_root, "rev-parse", "--absolute-git-dir", timeout=5.0)
    common_dir_raw = _run_git(
        canonical_root,
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
        timeout=5.0,
    )
    if not git_dir_raw or not git_dir_raw.strip() or not common_dir_raw or not common_dir_raw.strip():
        raise WorktreeIdentityUnavailable("Git did not provide absolute worktree administrative paths")
    git_dir = _canonical_git_path(canonical_root, git_dir_raw.strip())
    git_common_dir = _canonical_git_path(canonical_root, common_dir_raw.strip())
    linked = os.path.normcase(str(git_dir)) != os.path.normcase(str(git_common_dir))
    marker = git_dir / "gitdir" if linked else git_common_dir / "config"

    parts = [
        "mnemo-code-worktree-v2",
        os.path.normcase(str(canonical_root)),
        os.path.normcase(str(git_dir)),
        os.path.normcase(str(git_common_dir)),
        *_path_identity(git_dir, "git-dir", require_incarnation_clock=False),
        *_path_identity(marker, "stable-marker", require_incarnation_clock=True),
    ]
    if linked:
        try:
            marker_bytes = marker.read_bytes()
        except OSError as exc:
            raise WorktreeIdentityUnavailable("linked-worktree identity marker is unreadable") from exc
        if len(marker_bytes) > 4096:
            raise WorktreeIdentityUnavailable("linked-worktree identity marker is unexpectedly large")
        parts.extend(("linked-marker-digest", hashlib.sha256(marker_bytes).hexdigest()))

    proof_digest = _hash_identity_parts(parts)
    return WorktreeIdentity(
        version=IDENTITY_VERSION,
        canonical_root=canonical_root,
        git_dir=git_dir,
        git_common_dir=git_common_dir,
        proof_digest=proof_digest,
        code_index_scope=f"wt2_{proof_digest[:32]}",
    )


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

    root = _canonical_path(root)
    return RepoInfo(
        root=root,
        repo_id=compute_repo_id(root),
        name=root.name,
        worktree=compute_code_index_scope(root),
    )


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
        raise RuntimeError("git ls-files failed for repository")
    rels = [p for p in out.split("\0") if p]
    if cfg.code_include_untracked:
        extra = _run_git(root, "ls-files", "-z", "--others", "--exclude-standard")
        if extra is None:
            raise RuntimeError("git ls-files for untracked files failed")
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
    except OSError as exc:
        raise RuntimeError("eligible source file became unreadable") from exc
    if b"\0" in raw[:8192]:
        return None  # binary despite an allowed extension
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
class Manifest:
    """Scope-bound v2 incremental state. Safe to delete; index rebuilds.

    Flushed via atomic os.replace so a killed process never leaves a torn file.
    """

    FLUSH_EVERY = 50

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"files": {}}
        self.load_state = "missing"
        self._pending = 0
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("files"), dict):
                    self.data = loaded
                    self.load_state = "loaded"
                else:
                    self.load_state = "invalid"
        except (OSError, ValueError) as exc:
            self.load_state = "invalid"
            log.warning("manifest unreadable (%s); scope requires rebuild", exc)

    def matches(self, repo: RepoInfo, embed_model: str, code_collection: str) -> bool:
        files = self.data.get("files")
        if not isinstance(files, dict) or any(
            not isinstance(rel, str)
            or not isinstance(entry, dict)
            or not isinstance(entry.get("sha"), str)
            or not isinstance(entry.get("chunks"), int)
            or entry["chunks"] < 0
            or not isinstance(entry.get("indexed_at"), (int, float))
            for rel, entry in files.items()
        ):
            return False
        if not isinstance(self.data.get("indexing"), bool):
            return False
        if self.data.get("last_index") is not None and not isinstance(
            self.data["last_index"], (int, float)
        ):
            return False
        if self.data.get("snapshot_head") is not None and not isinstance(
            self.data["snapshot_head"], str
        ):
            return False
        expected = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "identity_version": repo.worktree.version,
            "repository_family_id": repo.repo_id,
            "code_index_scope": repo.code_index_scope,
            "proof_digest": repo.worktree.proof_digest,
            "repo_root": str(repo.root),
            "embed_model": embed_model,
            "code_collection": code_collection,
        }
        return self.load_state == "loaded" and all(self.data.get(key) == value for key, value in expected.items())

    def bind(self, repo: RepoInfo, embed_model: str, code_collection: str) -> None:
        self.data = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "identity_version": repo.worktree.version,
            "repository_family_id": repo.repo_id,
            "code_index_scope": repo.code_index_scope,
            "proof_digest": repo.worktree.proof_digest,
            "repo_root": str(repo.root),
            "embed_model": embed_model,
            "code_collection": code_collection,
            "snapshot_head": None,
            "last_index": None,
            "indexing": False,
            "files": {},
        }
        self.load_state = "loaded"
        self._pending = 0

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

    def chunk_count(self) -> int:
        return sum(entry["chunks"] for entry in self.files.values())

    def flush(self) -> None:
        self._pending = 0
        tmp = self.path.with_suffix(".json.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.data), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("could not flush manifest %s: %s", self.path, exc)
            raise


# ---------------------------------------------------------------------------
# indexer
# ---------------------------------------------------------------------------
@dataclass
class IndexProgress:
    state: str = "idle"  # idle | running | done | error | skipped
    repo: str | None = None
    repo_id: str | None = None
    code_index_scope: str | None = None
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


class ProgressRegistry:
    """Process-local progress shared by foreground and background clients."""

    def __init__(self) -> None:
        self._items: dict[str, IndexProgress] = {}
        self._lock = threading.Lock()

    def get(self, code_index_scope: str) -> IndexProgress:
        with self._lock:
            item = self._items.get(code_index_scope)
            return replace(item) if item is not None else IndexProgress(code_index_scope=code_index_scope)

    def set(self, code_index_scope: str, progress: IndexProgress) -> None:
        with self._lock:
            self._items[code_index_scope] = replace(progress)


class CodeIndex:
    """Owns the `mnemo_code` collection. Never touches mnemo_memory."""

    def __init__(
        self,
        cfg: Config,
        embedder: Embedder | None = None,
        client: QdrantClient | None = None,
        progress_registry: ProgressRegistry | None = None,
    ):
        self.cfg = cfg
        cfg.ensure_dirs()
        self.embedder = embedder or make_embedder(cfg)
        self.dim = self.embedder.dim
        self.client = client or QdrantClient(url=cfg.qdrant_url, timeout=60)
        self._progress = progress_registry or ProgressRegistry()
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
        if not exists:
            try:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE),
                )
            except Exception as exc:  # concurrent creation by another agent is fine
                log.debug("create_collection(%s): %s", name, exc)
        # Without these, per-file eviction degrades to a full scan on the hot path.
        for field_name in (
            "code_index_scope",
            "repository_family_id",
            "repo_id",
            "file_path",
            "file_hash",
            "language",
        ):
            try:
                self.client.create_payload_index(name, field_name=field_name, field_schema=qm.PayloadSchemaType.KEYWORD)
            except Exception:
                pass

    # ---- progress --------------------------------------------------------
    def progress(self, code_index_scope: str) -> IndexProgress:
        return self._progress.get(code_index_scope)

    def _set_progress(self, code_index_scope: str, prog: IndexProgress) -> None:
        self._progress.set(code_index_scope, prog)

    # ---- paths -----------------------------------------------------------
    def _repo_dir(self, code_index_scope: str) -> Path:
        return self.cfg.code_dir / "v2" / code_index_scope

    def _manifest_path(self, code_index_scope: str) -> Path:
        return self._repo_dir(code_index_scope) / "manifest.json"

    def _lock_path(self, code_index_scope: str) -> Path:
        return self._repo_dir(code_index_scope) / "index.lock"

    # ---- qdrant ----------------------------------------------------------
    @staticmethod
    def _point_id(code_index_scope: str, rel: str, chunk_idx: int) -> str:
        # Deterministic: a resumed index overwrites instead of duplicating.
        return str(uuid.uuid5(_CHUNK_NS, f"v2:{code_index_scope}:{rel}:{chunk_idx}"))

    @staticmethod
    def _scope_filter(code_index_scope: str) -> qm.Filter:
        return qm.Filter(
            must=[qm.FieldCondition(key="code_index_scope", match=qm.MatchValue(value=code_index_scope))]
        )

    def _delete_scope_points(self, code_index_scope: str) -> None:
        self.client.delete(
            collection_name=self.cfg.code_collection,
            points_selector=qm.FilterSelector(filter=self._scope_filter(code_index_scope)),
            wait=True,
        )

    def _count_scope_points(self, code_index_scope: str) -> int:
        return self.client.count(
            collection_name=self.cfg.code_collection,
            count_filter=self._scope_filter(code_index_scope),
            exact=True,
        ).count

    def _delete_file_points(self, code_index_scope: str, rel: str, keep_hash: str | None = None) -> None:
        must: list[Any] = [
            qm.FieldCondition(key="code_index_scope", match=qm.MatchValue(value=code_index_scope)),
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
        self.client.delete(
            collection_name=self.cfg.code_collection,
            # FilterSelector must be explicit — points_selector is overloaded
            # and a bare list means delete-by-ID.
            points_selector=qm.FilterSelector(filter=flt),
            wait=True,
        )

    def _upsert(self, points: list[qm.PointStruct]) -> None:
        self.client.upsert(collection_name=self.cfg.code_collection, points=points, wait=True)

    # ---- indexing --------------------------------------------------------
    def index_repo(self, repo: RepoInfo, force: bool = False) -> IndexProgress:
        """Incrementally index a repo. Safe to kill at any point: the next run
        resumes and any duplicated work is idempotent."""
        scope = repo.code_index_scope
        prog = IndexProgress(
            state="running",
            repo=repo.name,
            repo_id=repo.repo_id,
            code_index_scope=scope,
            started_at=time.time(),
        )
        self._set_progress(scope, prog)

        lock = _acquire_lock(self._lock_path(scope))
        if lock is None:
            prog.state = "skipped"
            prog.detail = "another process is indexing this worktree scope"
            prog.finished_at = time.time()
            self._set_progress(scope, prog)
            return prog

        try:
            manifest = Manifest(self._manifest_path(scope))
            bound = manifest.matches(repo, self.cfg.embed_model, self.cfg.code_collection)
            complete = bound and self._count_scope_points(scope) == manifest.chunk_count()
            if force or not complete:
                # Missing/corrupt/legacy/mismatched state cannot authorize orphan
                # points. Reset only this derived v2 scope, then bind empty first.
                self._delete_scope_points(scope)
                manifest.bind(repo, self.cfg.embed_model, self.cfg.code_collection)
                manifest.flush()
            manifest.data["indexing"] = True
            manifest.flush()

            files = discover_files(repo.root, self.cfg)
            prog.files_total = len(files)
            self._set_progress(scope, prog)
            file_failures = 0

            live = set(files)
            for gone in [r for r in list(manifest.files) if r not in live]:
                self._delete_file_points(scope, gone)
                manifest.drop(gone)

            for rel in files:
                prog.files_done += 1
                abs_path = repo.root / rel
                sha = file_sha(abs_path)
                if sha is None:
                    file_failures += 1
                    continue
                if not force and manifest.unchanged(rel, sha):
                    continue
                try:
                    written = self._index_file(repo, rel, abs_path, sha, manifest)
                except Exception as exc:
                    log.warning("indexing %s in scope %s failed: %s", rel, scope[4:12], exc)
                    file_failures += 1
                    continue
                if written:
                    prog.files_indexed += 1
                    prog.chunks_written += written
                self._set_progress(scope, prog)

            if file_failures:
                raise RuntimeError(f"indexing failed for {file_failures} eligible file(s)")
            manifest.data["last_index"] = time.time()
            head = _run_git(repo.root, "rev-parse", "HEAD", timeout=5.0)
            manifest.data["snapshot_head"] = head.strip() if head and head.strip() else None
            manifest.data["indexing"] = False
            manifest.flush()
            prog.state = "done"
            prog.finished_at = time.time()
        except Exception as exc:
            log.exception("index_repo failed for %s scope %s", repo.name, scope[4:12])
            prog.state = "error"
            prog.error = f"{type(exc).__name__}: indexing failed; see mnemo server logs"
            prog.finished_at = time.time()
        finally:
            _release_lock(lock)
        self._set_progress(scope, prog)
        return prog

    def _index_file(self, repo: RepoInfo, rel: str, abs_path: Path, sha: str, manifest: Manifest) -> int:
        text = read_text(abs_path)
        if text is None or not text.strip():
            self._delete_file_points(repo.code_index_scope, rel)
            manifest.record(rel, sha, 0)
            return 0
        chunks = chunk_text(text, self.cfg.code_chunk_lines, self.cfg.code_chunk_overlap)
        if not chunks:
            return 0

        language = Path(rel).suffix.lstrip(".").lower() or Path(rel).name.lower()
        vectors = self.embedder.embed([c.text for c in chunks])

        points = [
            qm.PointStruct(
                id=self._point_id(repo.code_index_scope, rel, c.index),
                vector=vec,
                payload={
                    "code_index_scope": repo.code_index_scope,
                    "repository_family_id": repo.repo_id,
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
        self._delete_file_points(repo.code_index_scope, rel, keep_hash=sha)
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
        manifest = Manifest(self._manifest_path(repo.code_index_scope))
        if not manifest.matches(repo, self.cfg.embed_model, self.cfg.code_collection):
            return []
        must: list[Any] = [
            qm.FieldCondition(key="code_index_scope", match=qm.MatchValue(value=repo.code_index_scope))
        ]
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
        manifest = Manifest(self._manifest_path(repo.code_index_scope))
        bound = manifest.matches(repo, self.cfg.embed_model, self.cfg.code_collection)
        prog = self.progress(repo.code_index_scope)
        count = 0
        if bound:
            try:
                count = self._count_scope_points(repo.code_index_scope)
            except Exception:
                log.exception(
                    "status count failed for %s scope %s",
                    repo.name,
                    repo.code_index_scope[4:12],
                )
                return {
                    **repo.as_dict(),
                    "ok": False,
                    "error": "status_failed",
                    "detail": "code index status failed; check mnemo server logs",
                }
        if prog.state == "running":
            index_state = "building"
        elif prog.state == "skipped" and prog.detail == "another process is indexing this worktree scope":
            index_state = "building_elsewhere"
        elif prog.state == "error":
            index_state = "error"
        elif not bound:
            index_state = "unindexed"
        elif manifest.data.get("indexing") is True or count != manifest.chunk_count():
            index_state = "interrupted"
        elif manifest.data.get("last_index") is not None:
            index_state = "ready"
        else:
            index_state = "interrupted"
        return {
            **repo.as_dict(),
            "ok": True,
            "index_state": index_state,
            "collection": self.cfg.code_collection,
            "embed_model": self.cfg.embed_model,
            "files_in_manifest": len(manifest.files) if bound else 0,
            "chunks_indexed": count,
            "last_index": manifest.data.get("last_index") if bound else None,
            "snapshot_head": manifest.data.get("snapshot_head") if bound else None,
            "snapshot_semantics": SNAPSHOT_SEMANTICS,
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
            scope = repo.code_index_scope
            live = self._threads.get(scope)
            if live is not None and live.is_alive():
                return "already-running"
            last = self._done.get(scope)
            if min_interval > 0 and last is not None and (time.time() - last) < min_interval:
                return "recently-indexed"

            def run() -> None:
                completed = False
                try:
                    # Own clients: sidesteps sharing a QdrantClient/OpenAI client
                    # across the loop thread and this one.
                    result = self._factory().index_repo(repo, force=full)
                    completed = result is not None and result.state == "done"
                except Exception:
                    log.exception("background index failed for %s scope %s", repo.name, scope[4:12])
                finally:
                    if completed:
                        with self._lock:
                            self._done[scope] = time.time()

            thread = threading.Thread(target=run, name=f"mnemo-index-{repo.name}-{scope[4:12]}", daemon=True)
            self._threads[scope] = thread
            thread.start()
            return "started"
