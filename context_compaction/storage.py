"""Atomic, private, disposable state storage for the compaction pilot."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from .models import DegradedReason, SCHEMA_VERSION
from .repository import canonical_repository_root

OWNER_ID = "coding-cli-context-compaction-pilot"
MAX_STATE_BYTES = 1_048_576
_FORBIDDEN_KEYS = {
    "absolute_path",
    "binary",
    "command",
    "compact_summary",
    "credential",
    "cwd",
    "diff",
    "password",
    "raw_input",
    "raw_output",
    "secret",
    "source_body",
    "tool_input",
    "tool_output",
    "transcript",
    "transcript_path",
    "token_value",
}
_ABSOLUTE_WINDOWS = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|//)")
_SENSITIVE_VALUE = re.compile(
    r"(?i)(?:"
    r"\bsk-[A-Za-z0-9_-]{16,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bbearer\s+\S{10,}|"
    r"(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*\S+"
    r")"
)
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class StorageError(RuntimeError):
    def __init__(self, reason: DegradedReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def resolve_state_directory(
    repository_root: str | os.PathLike[str],
    *,
    fallback_base: str | os.PathLike[str] | None = None,
) -> Path:
    root = canonical_repository_root(repository_root)
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "coding-cli-context-pilot",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        timeout=10,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve(strict=False)

    if fallback_base is None:
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA")
            if not local:
                raise StorageError(
                    DegradedReason.STATE_MISSING, "local application state unavailable"
                )
            base = Path(local) / "coding-cli" / "context-compaction"
        else:
            configured = os.environ.get("XDG_STATE_HOME")
            base = (
                Path(configured) / "coding-cli" / "context-compaction"
                if configured
                else Path.home() / ".local" / "state" / "coding-cli" / "context-compaction"
            )
    else:
        base = Path(fallback_base)
    base = base.expanduser().resolve(strict=False)
    identity = os.path.normcase(str(root)).replace("\\", "/")
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return base / key


class StateStore:
    """Own current state and a bounded content-free event ring."""

    def __init__(
        self,
        repository_root: str | os.PathLike[str],
        *,
        fallback_base: str | os.PathLike[str] | None = None,
        retention: int = 200,
        max_bytes: int = MAX_STATE_BYTES,
    ) -> None:
        if retention <= 0 or retention > 10_000:
            raise ValueError("invalid event retention")
        if max_bytes < 1_024 or max_bytes > 16 * MAX_STATE_BYTES:
            raise ValueError("invalid state size limit")
        self.repository_root = canonical_repository_root(repository_root)
        self.directory = resolve_state_directory(
            self.repository_root, fallback_base=fallback_base
        )
        self.retention = retention
        self.max_bytes = max_bytes
        key = os.path.normcase(str(self.directory))
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(key, threading.RLock())

    def write_current(self, payload: Mapping[str, Any]) -> None:
        encoded = self._encode(payload)
        with self._lock:
            with self._process_lock():
                self._ensure_owned()
                self._atomic_write(self.directory / "current.json", encoded)

    def read_current(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.directory.exists():
                return None
            with self._process_lock(create=False):
                self._assert_owner()
                path = self.directory / "current.json"
                if not path.exists():
                    return None
                return self._decode(path)

    def append_event(self, payload: Mapping[str, Any], *, dedupe_key: str) -> bool:
        if not dedupe_key or len(dedupe_key) > 512 or "\x00" in dedupe_key:
            raise StorageError(DegradedReason.STATE_MALFORMED, "invalid event identity")
        safe_payload = json.loads(self._encode(payload).decode("utf-8"))
        with self._lock:
            with self._process_lock():
                self._ensure_owned()
                path = self.directory / "events.json"
                records: list[dict[str, Any]] = []
                if path.exists():
                    decoded = self._decode_container(path)
                    if not isinstance(decoded, list):
                        raise StorageError(DegradedReason.STATE_MALFORMED, "invalid event ring")
                    records = decoded
                if any(record.get("dedupe_key") == dedupe_key for record in records):
                    return False
                records.append({"dedupe_key": dedupe_key, "payload": safe_payload})
                records = records[-self.retention :]
                encoded = json.dumps(
                    records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                if len(encoded) > self.max_bytes:
                    while records and len(encoded) > self.max_bytes:
                        records.pop(0)
                        encoded = json.dumps(
                            records,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                if not records:
                    raise StorageError(
                        DegradedReason.STATE_OVERSIZED, "event cannot fit the state ring"
                    )
                self._atomic_write(path, encoded)
                return True

    def read_events(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.directory.exists():
                return []
            with self._process_lock(create=False):
                self._assert_owner()
                path = self.directory / "events.json"
                if not path.exists():
                    return []
                decoded = self._decode_container(path)
                if not isinstance(decoded, list):
                    raise StorageError(DegradedReason.STATE_MALFORMED, "invalid event ring")
                result: list[dict[str, Any]] = []
                for item in decoded:
                    if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                        raise StorageError(DegradedReason.STATE_MALFORMED, "invalid event record")
                    result.append(item["payload"])
                return result

    def purge(self) -> None:
        with self._lock:
            with self._process_lock():
                if self.directory.exists():
                    self._assert_owner()
                    allowed = {"owner.json", "current.json", "events.json"}
                    entries = list(self.directory.iterdir())
                    unknown = [
                        item
                        for item in entries
                        if item.name not in allowed and ".tmp" not in item.name
                    ]
                    if unknown:
                        raise StorageError(
                            DegradedReason.OWNED_FILE_DRIFT,
                            "private state contains unowned entries",
                        )
                    for path in entries:
                        if path.is_file() or path.is_symlink():
                            path.unlink(missing_ok=True)
                        elif path.is_dir() and ".tmp" in path.name:
                            shutil.rmtree(path)
                    self.directory.rmdir()
            self._lock_path().unlink(missing_ok=True)

    def _ensure_owned(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = self.directory / "owner.json"
        if marker.exists():
            self._assert_owner()
            return
        if any(self.directory.iterdir()):
            raise StorageError(
                DegradedReason.OWNED_FILE_DRIFT, "state directory is not pilot-owned"
            )
        encoded = json.dumps(
            {"owner": OWNER_ID, "schema_version": SCHEMA_VERSION},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._atomic_write(marker, encoded)

    def _assert_owner(self) -> None:
        marker = self.directory / "owner.json"
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StorageError(
                DegradedReason.OWNED_FILE_DRIFT, "pilot ownership marker unavailable"
            ) from exc
        if value != {"owner": OWNER_ID, "schema_version": SCHEMA_VERSION}:
            raise StorageError(
                DegradedReason.OWNED_FILE_DRIFT, "pilot ownership marker drifted"
            )

    def _encode(self, payload: Mapping[str, Any]) -> bytes:
        if not isinstance(payload, Mapping):
            raise StorageError(DegradedReason.STATE_MALFORMED, "state must be an object")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise StorageError(DegradedReason.STATE_MALFORMED, "unknown state schema")
        self._validate_value(payload)
        try:
            encoded = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise StorageError(DegradedReason.STATE_MALFORMED, "state is not JSON") from exc
        if len(encoded) > self.max_bytes:
            raise StorageError(DegradedReason.STATE_OVERSIZED, "state exceeds size limit")
        return encoded

    def _decode(self, path: Path) -> dict[str, Any]:
        value = self._decode_container(path)
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
            raise StorageError(DegradedReason.STATE_MALFORMED, "unknown state schema")
        self._validate_value(value)
        return value

    def _decode_container(self, path: Path) -> Any:
        try:
            if path.stat().st_size > self.max_bytes:
                raise StorageError(DegradedReason.STATE_OVERSIZED, "state exceeds size limit")
            return json.loads(path.read_text(encoding="utf-8"))
        except StorageError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StorageError(DegradedReason.STATE_MALFORMED, "state cannot be decoded") from exc

    def _validate_value(self, value: Any, *, key: str | None = None) -> None:
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                if not isinstance(child_key, str) or len(child_key) > 128:
                    raise StorageError(DegradedReason.STATE_MALFORMED, "invalid state key")
                normalized = child_key.lower()
                if normalized in _FORBIDDEN_KEYS or any(
                    part in normalized for part in ("credential", "password", "secret")
                ):
                    raise StorageError(
                        DegradedReason.STATE_MALFORMED, "sensitive state category rejected"
                    )
                self._validate_value(child_value, key=normalized)
            return
        if isinstance(value, list):
            if len(value) > 10_000:
                raise StorageError(DegradedReason.STATE_OVERSIZED, "state list is oversized")
            for child in value:
                self._validate_value(child, key=key)
            return
        if isinstance(value, str):
            if len(value) > self.max_bytes or "\x00" in value:
                raise StorageError(DegradedReason.STATE_OVERSIZED, "state string is oversized")
            if _SENSITIVE_VALUE.search(value):
                raise StorageError(
                    DegradedReason.STATE_MALFORMED,
                    "sensitive state value rejected",
                )
            if key and "path" in key and (_ABSOLUTE_WINDOWS.match(value) or value.startswith("/")):
                raise StorageError(
                    DegradedReason.STATE_MALFORMED, "absolute state paths are forbidden"
                )
            return
        if value is not None and not isinstance(value, (bool, int, float)):
            raise StorageError(DegradedReason.STATE_MALFORMED, "unsupported state value")

    def _atomic_write(self, target: Path, encoded: bytes) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.directory,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                os.chmod(temporary, 0o600)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            os.chmod(target, 0o600)
        except OSError as exc:
            raise StorageError(DegradedReason.INTERNAL_ERROR, "atomic state write failed") from exc
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink(missing_ok=True)

    def _lock_path(self) -> Path:
        return self.directory.parent / f".{self.directory.name}.context-pilot.lock"

    @contextmanager
    def _process_lock(self, *, create: bool = True):
        """Serialize independent hook processes with a one-byte OS file lock."""

        lock_path = self._lock_path()
        if create:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
        elif not lock_path.is_file():
            # A read-only command may observe an older state directory without
            # a lock file. Preserve its no-mutation contract and rely on atomic
            # file replacement for a coherent snapshot.
            yield
            return
        mode = "a+b" if create else "r+b"
        try:
            stream = lock_path.open(mode)
        except FileNotFoundError:
            if not create:
                yield
                return
            raise
        with stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
