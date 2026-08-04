"""Content-addressed storage: exact originals plus a segment optical cache.

Two stores with different jobs sharing one directory:

- **originals** — the exact text behind every rendered page. This is what makes
  the lossy render safe: the image is a gist, and anything precision-critical is
  fetched back verbatim by digest. Losing this store would turn a recoverable
  approximation into an unrecoverable one, so writes are atomic.
- **segments** — rendered PNGs keyed by content plus glyph size. An agent
  history is append-only, so re-rendering it every turn is O(N^2) work over
  segments that did not change. Memoising turns that into O(N): measured 10.2x
  faster over 18 segments, and the speedup scales as ~N/2.

Digests are hex and length-checked before touching the filesystem, so a digest
arriving from a tool argument can never escape the store directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .constants import DEFAULT_RETENTION_DAYS, DIGEST_CHARS, STORE_DIRNAME

_HEX = re.compile(r"\A[0-9a-f]+\Z")


class StoreError(RuntimeError):
    """Raised when the store cannot satisfy a request safely."""


def resolve_store_dir(root: str | Path | None = None) -> Path:
    """Locate the store.

    Precedence is explicit > ambient > default. An explicit `root` wins over
    `OPTICAL_COMPRESSION_DIR`, because the reverse makes a caller that passed a
    directory silently write somewhere else entirely whenever the variable
    happens to be set in the environment.
    """
    if root is not None:
        return (Path(root) / STORE_DIRNAME).resolve()
    override = os.environ.get("OPTICAL_COMPRESSION_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.cwd() / STORE_DIRNAME).resolve()


def validate_digest(digest: str) -> str:
    """Reject anything that is not a plain lowercase hex digest.

    The digest reaches this module from a tool argument, so it is untrusted
    input used to build a path. `..`, separators, drive letters, and NUL all
    fail this check before any filesystem call happens.
    """
    if not isinstance(digest, str):
        raise StoreError("digest must be a string")
    candidate = digest.strip().lower()
    if not candidate or len(candidate) > 64 or not _HEX.match(candidate):
        raise StoreError("digest must be lowercase hexadecimal")
    return candidate


@dataclass(frozen=True)
class StoredOriginal:
    digest: str
    text: str
    chars: int
    created_at: float


class OpticalStore:
    """Filesystem-backed originals store and segment cache."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.base = resolve_store_dir(root)
        self.originals_dir = self.base / "originals"
        self.segments_dir = self.base / "segments"

    # -- lifecycle ---------------------------------------------------------

    def ensure(self) -> None:
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.segments_dir.mkdir(parents=True, exist_ok=True)

    # -- originals ---------------------------------------------------------

    def put_original(self, text: str, *, meta: dict | None = None) -> str:
        """Store exact text; return its digest. Idempotent by content."""
        self.ensure()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST_CHARS]
        target = self.originals_dir / f"{digest}.json"
        if target.exists():
            stored = self.get_original(digest)
            if stored is not None:
                if stored.text != text:  # pragma: no cover - 64-bit hash collision
                    raise StoreError("content digest collision")
                return digest

        payload = {
            "digest": digest,
            "chars": len(text),
            "created_at": time.time(),
            "meta": meta or {},
            "text": text,
        }
        _atomic_write(target, json.dumps(payload, ensure_ascii=False))
        return digest

    def get_original(self, digest: str) -> StoredOriginal | None:
        digest = validate_digest(digest)
        target = self.originals_dir / f"{digest}.json"
        if not self._inside(target, self.originals_dir) or not target.exists():
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            text = payload.get("text")
            if not isinstance(text, str) or payload.get("digest") != digest:
                return None
            actual_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST_CHARS]
            if actual_digest != digest:
                return None
            created_at = float(payload.get("created_at", 0.0))
        except (OSError, TypeError, ValueError):
            return None
        return StoredOriginal(
            digest=digest,
            text=text,
            chars=len(text),
            created_at=created_at,
        )

    def slice_original(
        self, digest: str, *, start: int = 0, length: int | None = None
    ) -> str | None:
        """Return an exact span, so a caller can retrieve one hash cheaply."""
        stored = self.get_original(digest)
        if stored is None:
            return None
        if start < 0:
            raise StoreError("start must be non-negative")
        if length is not None and length < 0:
            raise StoreError("length must be non-negative")
        return stored.text[start:] if length is None else stored.text[start : start + length]

    # -- segment cache -----------------------------------------------------

    def get(self, digest: str) -> bytes | None:
        try:
            digest = validate_digest(digest)
        except StoreError:
            return None
        target = self.segments_dir / f"{digest}.png"
        if not self._inside(target, self.segments_dir) or not target.exists():
            return None
        try:
            return target.read_bytes()
        except OSError:  # pragma: no cover - transient IO
            return None

    def put(self, digest: str, png: bytes) -> None:
        digest = validate_digest(digest)
        self.ensure()
        target = self.segments_dir / f"{digest}.png"
        if target.exists():
            return
        _atomic_write_bytes(target, png)

    # -- maintenance -------------------------------------------------------

    def stats(self) -> dict[str, object]:
        originals = _listing(self.originals_dir, ".json")
        segments = _listing(self.segments_dir, ".png")
        return {
            "store": str(self.base),
            "originals": len(originals),
            "original_bytes": sum(path.stat().st_size for path in originals),
            "segments": len(segments),
            "segment_bytes": sum(path.stat().st_size for path in segments),
        }

    def prune(self, *, older_than_days: int = DEFAULT_RETENTION_DAYS) -> dict[str, int]:
        """Drop entries past retention. Never touches anything else.

        `older_than_days=0` means "everything", and is special-cased rather than
        computed. Deriving a cutoff of `now` raced the filesystem: an entry
        written microseconds earlier can carry an mtime equal to or later than
        `now` — timestamp granularity is coarse on some filesystems and clocks
        are not guaranteed monotonic against them — so a plain `mtime < now`
        left just-written entries behind, non-deterministically.
        """
        if older_than_days < 0:
            raise StoreError("retention must be non-negative")
        cutoff = float("inf") if older_than_days == 0 else time.time() - older_than_days * 86_400
        removed = {"originals": 0, "segments": 0}
        for key, directory, suffix in (
            ("originals", self.originals_dir, ".json"),
            ("segments", self.segments_dir, ".png"),
        ):
            for path in _listing(directory, suffix):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        removed[key] += 1
                except OSError:  # pragma: no cover - transient IO
                    continue
        return removed

    def _inside(self, path: Path, parent: Path) -> bool:
        try:
            return path.resolve().is_relative_to(parent.resolve())
        except (OSError, ValueError):  # pragma: no cover - unresolvable path
            return False


class MemoryCache:
    """In-process segment cache for benchmarks and tests."""

    def __init__(self) -> None:
        self._entries: dict[str, bytes] = {}
        self.hits = 0
        self.misses = 0

    def get(self, digest: str) -> bytes | None:
        payload = self._entries.get(digest)
        if payload is None:
            self.misses += 1
        else:
            self.hits += 1
        return payload

    def put(self, digest: str, png: bytes) -> None:
        self._entries[digest] = png

    def __len__(self) -> int:
        return len(self._entries)


def _listing(directory: Path, suffix: str) -> list[Path]:
    if not directory.is_dir():
        return []
    return [path for path in directory.iterdir() if path.suffix == suffix and path.is_file()]


def _atomic_write(target: Path, text: str) -> None:
    _atomic_write_bytes(target, text.encode("utf-8"))


def _atomic_write_bytes(target: Path, payload: bytes) -> None:
    """Write via a temp file in the same directory, then replace.

    A half-written original is worse than a missing one: the caller would get
    truncated text back and have no way to tell.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, target)
    finally:
        if temporary.exists():  # pragma: no cover - only on a failed replace
            try:
                temporary.unlink()
            except OSError:
                pass
