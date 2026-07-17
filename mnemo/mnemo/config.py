"""Runtime configuration for mnemo, resolved from environment variables.

Every knob has a safe default so the server boots with zero config beyond an
OpenAI API key and a running Qdrant on port 1337.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Known OpenAI embedding models -> output dimensionality.
_MODEL_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def _env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    qdrant_url: str = field(default_factory=lambda: _env("MNEMO_QDRANT_URL", "QDRANT_URL", default="http://127.0.0.1:1337"))
    collection: str = field(default_factory=lambda: _env("MNEMO_COLLECTION", default="mnemo_memory"))
    data_dir: Path = field(default_factory=lambda: Path(_env("MNEMO_DATA_DIR", default=str(Path.home() / ".mnemo"))).expanduser())
    # Embeddings are OpenAI-only by product decision (no local fallback).
    embedder: str = field(default_factory=lambda: (_env("MNEMO_EMBEDDER", default="openai") or "openai").lower())
    embed_model: str = field(default_factory=lambda: _env("MNEMO_EMBED_MODEL", default="text-embedding-3-small"))
    openai_api_key: str | None = field(default_factory=lambda: _env("OPENAI_API_KEY", "MNEMO_OPENAI_API_KEY"))
    openai_base_url: str | None = field(default_factory=lambda: _env("OPENAI_BASE_URL", "MNEMO_OPENAI_BASE_URL"))
    default_namespace: str = field(default_factory=lambda: _env("MNEMO_DEFAULT_NAMESPACE", default="global"))
    agent_id: str = field(default_factory=lambda: _env("MNEMO_AGENT_ID", "MNEMO_WRITER", default="unknown-agent"))
    redact: bool = field(default_factory=lambda: _bool("MNEMO_REDACT", default=True))

    # ---- code index -------------------------------------------------------
    # The code index is a rebuildable cache in its own collection; it never
    # shares mnemo_memory (whose reads apply a `revoked` filter and whose event
    # log is append-only truth). See ADR 0007.
    code_collection: str = field(default_factory=lambda: _env("MNEMO_CODE_COLLECTION", default="mnemo_code"))
    code_auto_index: bool = field(default_factory=lambda: _bool("MNEMO_CODE_AUTO_INDEX", default=True))
    # Explicit repo override. Only meaningful for project-scoped registrations —
    # a user-scope server serves every repo, so this must stay unset there.
    code_repo: str | None = field(default_factory=lambda: _env("MNEMO_REPO", "MNEMO_CODE_ROOT"))
    code_max_file_bytes: int = field(default_factory=lambda: int(_env("MNEMO_CODE_MAX_FILE_BYTES", default="1000000") or 1000000))
    code_chunk_lines: int = field(default_factory=lambda: int(_env("MNEMO_CODE_CHUNK_LINES", default="60") or 60))
    code_chunk_overlap: int = field(default_factory=lambda: int(_env("MNEMO_CODE_CHUNK_OVERLAP", default="12") or 12))
    # Index untracked-but-unignored files too. Off by default: a thin .gitignore
    # makes `git ls-files --others` return mostly vendor junk (measured 6518 vs
    # 200 tracked in coding-cli).
    code_include_untracked: bool = field(default_factory=lambda: _bool("MNEMO_CODE_INCLUDE_UNTRACKED", default=False))

    def __post_init__(self) -> None:
        # Some MCP hosts (e.g. Codex) do not pass the parent environment through
        # to stdio servers, so OPENAI_API_KEY may be missing even when it is set
        # in the user's shell. Fall back to a local key file the user controls.
        if not self.openai_api_key:
            key_file = self.data_dir / "openai_api_key"
            try:
                if key_file.exists():
                    self.openai_api_key = key_file.read_text(encoding="utf-8").strip() or None
            except OSError:
                pass

    @property
    def embed_dim(self) -> int:
        override = os.environ.get("MNEMO_EMBED_DIM")
        if override:
            return int(override)
        return _MODEL_DIMS.get(self.embed_model, 1536)

    @property
    def code_dir(self) -> Path:
        """Per-repo code-index manifests + locks (a cache, not the event log)."""
        return self.data_dir / "code"

    def ensure_dirs(self) -> None:
        (self.data_dir / "events").mkdir(parents=True, exist_ok=True)
        self.code_dir.mkdir(parents=True, exist_ok=True)
