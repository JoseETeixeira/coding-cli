"""Safe, bounded reconstruction of repository and Batman task pointers."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import DegradedReason, DirtyPath, RepositorySnapshot, StatePointer

_TASK_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_UNC_OR_DEVICE = re.compile(r"^(?:\\\\|//|\\\\[?.]\\)")
_OPEN_TASK = re.compile(r"^\s*-\s*\[\s\]\s+", re.MULTILINE)
_PHASE = re.compile(r"\bPhase\s+(\d+)\b", re.IGNORECASE)
_EXPLICIT_FIELD = re.compile(r"^\s*([A-Za-z][A-Za-z -]{1,40}):\s*(.*?)\s*$", re.MULTILINE)
_LIKELY_SECRET = re.compile(
    r"(?i)(?:"
    r"\bsk-[A-Za-z0-9_-]{16,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bbearer\s+\S{10,}|"
    r"(?:api[_ -]?key|access[_ -]?token|password|secret|token)\s*[:=]\s*\S+"
    r")"
)
_ARTIFACTS = (
    ("understanding", "steering/understanding.md"),
    ("requirements", "spec/requirements.md"),
    ("design", "spec/design.md"),
    ("tasks", "spec/tasks.md"),
)
_RULE_NAMES = ("AGENTS.md", "CLAUDE.md")


class RepositoryError(RuntimeError):
    """A reconstruction failure with a closed degradation reason."""

    def __init__(self, reason: DegradedReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class TaskSelection:
    slug: str | None
    selection_source: str | None
    degraded_reason: DegradedReason | None
    goal_preview: str | None = None
    phase: int | None = None
    active_plan_pointer: StatePointer | None = None
    approval_status: str = "none"
    verification_status: str = "unverified"
    blocker_pointers: tuple[StatePointer, ...] = ()


@dataclass(frozen=True)
class RepositoryState:
    repository: RepositorySnapshot
    task: TaskSelection
    artifact_pointers: tuple[StatePointer, ...]
    scoped_rule_pointers: tuple[StatePointer, ...]
    critical_pointers: tuple[StatePointer, ...] = ()

    @property
    def required_pointers(self) -> tuple[StatePointer, ...]:
        values = [*self.artifact_pointers, *self.scoped_rule_pointers]
        if self.task.active_plan_pointer is not None:
            values.append(self.task.active_plan_pointer)
        seen: set[tuple[str, str]] = set()
        result: list[StatePointer] = []
        for pointer in values:
            key = (pointer.relative_path, pointer.captured_hash)
            if key not in seen:
                seen.add(key)
                result.append(pointer)
        return tuple(result)


def canonical_repository_root(value: str | os.PathLike[str]) -> Path:
    """Return an existing canonical local directory; reject UNC/device ambiguity."""

    raw = os.fspath(value)
    if not raw or "\x00" in raw or _UNC_OR_DEVICE.match(raw):
        raise RepositoryError(DegradedReason.ALLOWLIST_MISMATCH, "unsafe repository root")
    try:
        path = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RepositoryError(
            DegradedReason.ALLOWLIST_MISMATCH, "repository root cannot be resolved"
        ) from exc
    if not path.is_dir():
        raise RepositoryError(DegradedReason.ALLOWLIST_MISMATCH, "root is not a directory")
    resolved = str(path)
    if _UNC_OR_DEVICE.match(resolved):
        raise RepositoryError(DegradedReason.ALLOWLIST_MISMATCH, "unsafe repository root")
    return path


def repository_fingerprint(value: str | os.PathLike[str]) -> str:
    root = canonical_repository_root(value)
    identity = os.path.normcase(str(root)).replace("\\", "/")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class RepositoryResolver:
    """Resolve only bounded Git metadata and explicitly named artifact pointers."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        allowed_fingerprint: str,
        explicit_task_slug: str | None = None,
    ) -> None:
        self.root = canonical_repository_root(root)
        self.fingerprint = repository_fingerprint(self.root)
        if self.fingerprint != allowed_fingerprint:
            raise RepositoryError(
                DegradedReason.ALLOWLIST_MISMATCH, "repository allowlist mismatch"
            )
        if explicit_task_slug is not None and not _TASK_SLUG.fullmatch(explicit_task_slug):
            raise RepositoryError(DegradedReason.TASK_AMBIGUOUS, "invalid task slug")
        self.explicit_task_slug = explicit_task_slug

    def resolve(self, *, target_path: str | os.PathLike[str] | None = None) -> RepositoryState:
        branch = self._branch()
        repository = RepositorySnapshot(
            fingerprint=self.fingerprint,
            branch=branch,
            head=self._head(),
            dirty_paths=self._dirty_paths(),
        )
        task = self._select_task(branch)
        artifact_pointers = self._artifact_pointers(task.slug) if task.slug else ()
        task = self._enrich_task(task, artifact_pointers)
        rules = self._scoped_rules(target_path or self.root)
        critical = self._critical_pointers(artifact_pointers)
        return RepositoryState(repository, task, artifact_pointers, rules, critical)

    def hash_relative_path(self, relative_path: str) -> str:
        path = self.resolve_relative_path(relative_path)
        if not path.is_file():
            raise RepositoryError(DegradedReason.ARTIFACT_MISSING, "required file unavailable")
        return _hash_file(path)

    def resolve_relative_path(self, relative_path: str) -> Path:
        normalized = relative_path.replace("\\", "/")
        if (
            not normalized
            or normalized.startswith("/")
            or re.match(r"^[A-Za-z]:", normalized)
            or any(part in {"", ".", ".."} for part in normalized.split("/"))
        ):
            raise RepositoryError(DegradedReason.ALLOWLIST_MISMATCH, "unsafe relative path")
        candidate = (self.root / Path(*normalized.split("/"))).resolve(strict=False)
        if not candidate.is_relative_to(self.root):
            raise RepositoryError(DegradedReason.ALLOWLIST_MISMATCH, "path escapes repository")
        return candidate

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=False,
            timeout=10,
        )
        if check and result.returncode != 0:
            raise RepositoryError(DegradedReason.STATE_CONTRADICTORY, "Git metadata unavailable")
        return result

    def _branch(self) -> str | None:
        result = self._git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def _head(self) -> str | None:
        result = self._git("rev-parse", "--verify", "HEAD", check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def _dirty_paths(self) -> tuple[DirtyPath, ...]:
        result = self._git(
            "status", "--porcelain=v2", "-z", "--untracked-files=all"
        )
        records = result.stdout.split("\x00")
        dirty: list[DirtyPath] = []
        skip_original = False
        for record in records:
            if not record:
                continue
            if skip_original:
                skip_original = False
                continue
            kind = record[0]
            if kind == "1":
                fields = record.split(" ", 8)
                if len(fields) == 9:
                    dirty.append(DirtyPath(fields[8].replace("\\", "/"), fields[1]))
            elif kind == "2":
                fields = record.split(" ", 9)
                if len(fields) == 10:
                    dirty.append(DirtyPath(fields[9].replace("\\", "/"), fields[1]))
                    skip_original = True
            elif kind == "u":
                fields = record.split(" ", 10)
                if len(fields) == 11:
                    dirty.append(DirtyPath(fields[10].replace("\\", "/"), fields[1]))
            elif kind == "?":
                dirty.append(DirtyPath(record[2:].replace("\\", "/"), "??"))
        return tuple(sorted(dirty, key=lambda item: (item.path, item.status)))

    def _task_directories(self) -> dict[str, Path]:
        batman = self.root / ".batman"
        if not batman.is_dir():
            return {}
        result: dict[str, Path] = {}
        for child in batman.iterdir():
            if child.is_dir() and _TASK_SLUG.fullmatch(child.name):
                resolved = child.resolve(strict=True)
                if resolved.is_relative_to(self.root):
                    result[child.name] = resolved
        return result

    def _select_task(self, branch: str | None) -> TaskSelection:
        directories = self._task_directories()
        if self.explicit_task_slug is not None:
            if self.explicit_task_slug not in directories:
                return TaskSelection(
                    self.explicit_task_slug,
                    "explicit",
                    DegradedReason.ARTIFACT_MISSING,
                )
            return TaskSelection(self.explicit_task_slug, "explicit", None)

        branch_slug = branch.rsplit("/", 1)[-1] if branch else None
        if branch_slug and branch_slug in directories:
            return TaskSelection(branch_slug, "branch", None)

        incomplete = [
            slug for slug, path in directories.items() if self._is_incomplete(path)
        ]
        if len(incomplete) == 1:
            return TaskSelection(incomplete[0], "single_incomplete", None)
        return TaskSelection(None, None, DegradedReason.TASK_AMBIGUOUS)

    @staticmethod
    def _is_incomplete(task_dir: Path) -> bool:
        tasks = task_dir / "spec" / "tasks.md"
        if not tasks.is_file():
            return False
        return bool(_OPEN_TASK.search(_read_bounded(tasks)))

    def _artifact_pointers(self, slug: str) -> tuple[StatePointer, ...]:
        base = self.root / ".batman" / slug
        pointers: list[StatePointer] = []
        for kind, suffix in _ARTIFACTS:
            path = (base / suffix).resolve(strict=False)
            if not path.is_file() or not path.is_relative_to(self.root):
                continue
            pointers.append(_pointer(self.root, path, kind, f"{slug}:{kind}"))
        return tuple(pointers)

    def _enrich_task(
        self, task: TaskSelection, pointers: tuple[StatePointer, ...]
    ) -> TaskSelection:
        tasks_pointer = next((item for item in pointers if item.kind == "tasks"), None)
        if tasks_pointer is None:
            if task.slug is None:
                return task
            return TaskSelection(
                task.slug,
                task.selection_source,
                task.degraded_reason or DegradedReason.ARTIFACT_MISSING,
            )
        path = self.resolve_relative_path(tasks_pointer.relative_path)
        body = _read_bounded(path)
        fields = {name.lower(): value for name, value in _EXPLICIT_FIELD.findall(body)}
        phase_match = _PHASE.search(fields.get("status", "")) or _PHASE.search(body[:2_000])
        phase = int(phase_match.group(1)) if phase_match else None
        approval = fields.get("approval", "none").strip().lower()
        if "pending" in approval or "await" in approval:
            approval_status = "pending"
        elif "approve" in approval or "grant" in approval:
            approval_status = "granted"
        else:
            approval_status = "none"
        verification = fields.get("verification", "unverified")[:128]
        active = _first_open_task_pointer(self.root, path, task.slug or "task", body)
        goal = _goal_preview(task.slug, pointers, self.root)
        blockers = _field_pointers(
            self.root, path, task.slug or "task", body, field_name="blocker"
        )
        return TaskSelection(
            task.slug,
            task.selection_source,
            task.degraded_reason,
            goal,
            phase,
            active,
            approval_status,
            verification,
            blockers,
        )

    def _scoped_rules(
        self, target_path: str | os.PathLike[str]
    ) -> tuple[StatePointer, ...]:
        raw = Path(target_path)
        candidate = raw if raw.is_absolute() else self.root / raw
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise RepositoryError(DegradedReason.ALLOWLIST_MISMATCH, "target escapes repository")
        directory = resolved if resolved.is_dir() else resolved.parent
        relative = directory.relative_to(self.root)
        levels = [self.root]
        cursor = self.root
        for part in relative.parts:
            cursor = cursor / part
            levels.append(cursor)
        pointers: list[StatePointer] = []
        for level in levels:
            for name in _RULE_NAMES:
                path = level / name
                if path.is_file():
                    actual = path.resolve(strict=True)
                    if not actual.is_relative_to(self.root):
                        raise RepositoryError(
                            DegradedReason.ALLOWLIST_MISMATCH, "rule path escapes repository"
                        )
                    rel = actual.relative_to(self.root).as_posix()
                    pointers.append(
                        StatePointer("scoped_rule", rel, rel, None, _hash_file(actual))
                    )
        return tuple(pointers)

    def _critical_pointers(
        self, artifacts: Iterable[StatePointer]
    ) -> tuple[StatePointer, ...]:
        result: list[StatePointer] = []
        for pointer in artifacts:
            path = self.resolve_relative_path(pointer.relative_path)
            body = _read_bounded(path)
            for number, line in enumerate(body.splitlines(), 1):
                if "critical" in line.lower() or "must not" in line.lower():
                    result.append(
                        StatePointer(
                            "critical_anchor",
                            f"{pointer.stable_id}:L{number}",
                            pointer.relative_path,
                            f"L{number}",
                            pointer.captured_hash,
                        )
                    )
                    if len(result) == 32:
                        return tuple(result)
        return tuple(result)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_bounded(path: Path, maximum: int = 1_000_000) -> str:
    if path.stat().st_size > maximum:
        raise RepositoryError(DegradedReason.STATE_OVERSIZED, "artifact is oversized")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RepositoryError(DegradedReason.ARTIFACT_MISSING, "artifact is unreadable") from exc


def _pointer(root: Path, path: Path, kind: str, stable_id: str) -> StatePointer:
    return StatePointer(
        kind=kind,
        stable_id=stable_id,
        relative_path=path.relative_to(root).as_posix(),
        anchor=None,
        captured_hash=_hash_file(path),
    )


def _first_open_task_pointer(
    root: Path, path: Path, slug: str, body: str
) -> StatePointer | None:
    for number, line in enumerate(body.splitlines(), 1):
        if _OPEN_TASK.match(line):
            return StatePointer(
                "active_plan",
                f"{slug}:task:L{number}",
                path.relative_to(root).as_posix(),
                f"L{number}",
                _hash_file(path),
            )
    return None


def _field_pointers(
    root: Path, path: Path, slug: str, body: str, *, field_name: str
) -> tuple[StatePointer, ...]:
    result: list[StatePointer] = []
    prefix = f"{field_name}:"
    for number, line in enumerate(body.splitlines(), 1):
        if line.strip().lower().startswith(prefix):
            result.append(
                StatePointer(
                    field_name,
                    f"{slug}:{field_name}:L{number}",
                    path.relative_to(root).as_posix(),
                    f"L{number}",
                    _hash_file(path),
                )
            )
    return tuple(result[:16])


def _goal_preview(slug: str | None, pointers: Iterable[StatePointer], root: Path) -> str | None:
    for preferred in ("requirements", "understanding", "tasks"):
        pointer = next((item for item in pointers if item.kind == preferred), None)
        if pointer is None:
            continue
        body = _read_bounded(root / pointer.relative_path)
        title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
        if title and not _LIKELY_SECRET.search(title):
            return title[:500]
    return slug[:128] if slug else None
