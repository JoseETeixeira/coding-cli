"""Content-free semantic guard for Claude Code's host-owned registry."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .models import RegistryFieldCategory

_MAX_REGISTRY_BYTES = 4 * 1024 * 1024
_CHANGED_FIELD_CATEGORIES = frozenset(
    category.value for category in RegistryFieldCategory
)


class ClaudeRegistryError(ValueError):
    """A closed, content-free registry validation failure."""

    def __init__(
        self, code: str, *, changed_field_categories: Iterable[str] = ()
    ) -> None:
        super().__init__(code)
        self.code = code
        categories = {
            category
            if category in _CHANGED_FIELD_CATEGORIES
            else "protected_top_level"
            for category in changed_field_categories
        }
        self.changed_field_categories = tuple(sorted(categories))


@dataclass(frozen=True)
class ClaudeRegistryManifest:
    schema_version: int
    byte_count: int
    content_sha256: str
    semantic_sha256: str
    num_startups: int
    target_state: str
    manifest_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "byte_count": self.byte_count,
            "content_sha256": self.content_sha256,
            "semantic_sha256": self.semantic_sha256,
            "num_startups": self.num_startups,
            "target_state": self.target_state,
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True)
class ClaudeRegistryObservation:
    schema_version: int
    byte_count: int
    content_sha256: str
    semantic_sha256: str
    num_startups_delta: int
    target_trusted: bool
    change_names: tuple[str, ...]
    observation_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "byte_count": self.byte_count,
            "content_sha256": self.content_sha256,
            "semantic_sha256": self.semantic_sha256,
            "num_startups_delta": self.num_startups_delta,
            "target_trusted": self.target_trusted,
            "change_names": list(self.change_names),
            "observation_sha256": self.observation_sha256,
        }


class ClaudeRegistryGuard:
    """Compare Claude registry semantics without retaining registry bodies."""

    def __init__(
        self,
        registry_path: Path,
        repository_key: str,
        manifest: ClaudeRegistryManifest,
        protected_field_sha256: Mapping[str, str],
    ) -> None:
        self.registry_path = registry_path
        self.repository_key = repository_key
        self._normalized_repository_key = _normalize_project_key(repository_key)
        self.manifest = manifest
        self._protected_field_sha256 = dict(protected_field_sha256)

    @classmethod
    def capture(
        cls, registry_path: str | Path, repository_root: str | Path
    ) -> ClaudeRegistryGuard:
        path = Path(registry_path).expanduser().resolve(strict=False)
        repository_key = str(Path(repository_root).expanduser().resolve(strict=False))
        value, byte_count, content_sha256 = _read_registry(path)
        num_startups, projects = _registry_fields(value)
        matches = _matching_project_keys(projects, repository_key)
        if matches:
            raise ClaudeRegistryError("target_project_preexisting")
        protected = _protected_value(value, matches)
        semantic_sha256 = _canonical_sha256(protected)
        base = {
            "schema_version": 1,
            "byte_count": byte_count,
            "content_sha256": content_sha256,
            "semantic_sha256": semantic_sha256,
            "num_startups": num_startups,
            "target_state": "absent",
        }
        manifest = ClaudeRegistryManifest(
            **base,
            manifest_sha256=_canonical_sha256(base),
        )
        return cls(
            path,
            repository_key,
            manifest,
            _protected_field_fingerprints(protected),
        )

    def validate_current(self, *, final: bool) -> ClaudeRegistryObservation:
        value, byte_count, content_sha256 = _read_registry(self.registry_path)
        num_startups, projects = _registry_fields(value)
        matches = _matching_project_keys(projects, self.repository_key)
        if len(matches) > 1:
            raise ClaudeRegistryError("target_project_ambiguous")

        protected = _protected_value(value, matches)
        semantic_sha256 = _canonical_sha256(protected)
        semantic_drift = semantic_sha256 != self.manifest.semantic_sha256
        changed_field_categories: tuple[str, ...] = ()
        if semantic_drift:
            current_field_sha256 = _protected_field_fingerprints(protected)
            changed_names = {
                *self._protected_field_sha256,
                *current_field_sha256,
            }
            changed_names = {
                name
                for name in changed_names
                if self._protected_field_sha256.get(name)
                != current_field_sha256.get(name)
            }
            changed_field_categories = _changed_field_categories(changed_names) or (
                RegistryFieldCategory.PROTECTED_TOP_LEVEL.value,
            )

        target_trusted = False
        if matches:
            key = matches[0]
            if key != self.repository_key:
                raise ClaudeRegistryError(
                    "target_project_noncanonical",
                    changed_field_categories=changed_field_categories,
                )
            target = projects[key]
            if not isinstance(target, dict) or target.get("hasTrustDialogAccepted") is not True:
                raise ClaudeRegistryError(
                    "target_project_untrusted",
                    changed_field_categories=changed_field_categories,
                )
            target_trusted = True
        elif final:
            raise ClaudeRegistryError(
                "target_project_missing",
                changed_field_categories=changed_field_categories,
            )

        startup_delta = num_startups - self.manifest.num_startups
        if final:
            if startup_delta != 1:
                raise ClaudeRegistryError(
                    "startup_count_mismatch",
                    changed_field_categories=changed_field_categories,
                )
        elif startup_delta not in {0, 1}:
            raise ClaudeRegistryError(
                "startup_count_mismatch",
                changed_field_categories=changed_field_categories,
            )

        if semantic_drift:
            raise ClaudeRegistryError(
                "registry_semantic_drift",
                changed_field_categories=changed_field_categories,
            )

        changes: list[str] = []
        if startup_delta:
            changes.append("num_startups")
        if target_trusted:
            changes.append("target_project_trust")
        base = {
            "schema_version": 1,
            "byte_count": byte_count,
            "content_sha256": content_sha256,
            "semantic_sha256": semantic_sha256,
            "num_startups_delta": startup_delta,
            "target_trusted": target_trusted,
            "change_names": changes,
        }
        return ClaudeRegistryObservation(
            schema_version=1,
            byte_count=byte_count,
            content_sha256=content_sha256,
            semantic_sha256=semantic_sha256,
            num_startups_delta=startup_delta,
            target_trusted=target_trusted,
            change_names=tuple(changes),
            observation_sha256=_canonical_sha256(base),
        )


def _read_registry(path: Path) -> tuple[dict[str, Any], int, str]:
    if not path.is_file() or path.is_symlink():
        raise ClaudeRegistryError("registry_missing")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ClaudeRegistryError("registry_unreadable") from exc
    if not raw or len(raw) > _MAX_REGISTRY_BYTES:
        raise ClaudeRegistryError("registry_oversized")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ClaudeRegistryError("registry_malformed") from exc
    if not isinstance(value, dict):
        raise ClaudeRegistryError("registry_malformed")
    return value, len(raw), hashlib.sha256(raw).hexdigest()


def _registry_fields(value: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    num_startups = value.get("numStartups")
    projects = value.get("projects")
    if (
        not isinstance(num_startups, int)
        or isinstance(num_startups, bool)
        or num_startups < 0
        or not isinstance(projects, dict)
        or any(not isinstance(key, str) for key in projects)
    ):
        raise ClaudeRegistryError("registry_schema_mismatch")
    return num_startups, projects


def _matching_project_keys(
    projects: dict[str, Any], repository_key: str
) -> tuple[str, ...]:
    normalized = _normalize_project_key(repository_key)
    return tuple(
        key for key in projects if _normalize_project_key(key) == normalized
    )


def _normalize_project_key(value: str) -> str:
    return os.path.normcase(os.path.normpath(value))


def _protected_value(
    value: dict[str, Any], matches: Iterable[str]
) -> dict[str, Any]:
    sanitized = dict(value)
    sanitized.pop("numStartups", None)
    projects = dict(sanitized["projects"])
    for key in matches:
        projects.pop(key, None)
    sanitized["projects"] = projects
    return sanitized


def _protected_field_fingerprints(value: Mapping[str, Any]) -> dict[str, str]:
    return {name: _canonical_sha256(child) for name, child in value.items()}


def _changed_field_categories(field_names: Iterable[str]) -> tuple[str, ...]:
    categories = {_field_category(name) for name in field_names}
    return tuple(
        category.value for category in sorted(categories, key=lambda item: item.value)
    )


def _field_category(field_name: str) -> RegistryFieldCategory:
    if field_name == "projects":
        return RegistryFieldCategory.EXISTING_PROJECT_STATE
    if not _safe_field_name(field_name):
        return RegistryFieldCategory.PROTECTED_TOP_LEVEL
    normalized = field_name.lower()
    if any(part in normalized for part in ("oauth", "auth", "credential", "token", "account")):
        return RegistryFieldCategory.AUTHENTICATION_METADATA
    if any(part in normalized for part in ("feature", "growthbook", "experiment", "flag")):
        return RegistryFieldCategory.FEATURE_STATE
    if any(part in normalized for part in ("cache", "cached")):
        return RegistryFieldCategory.CACHE_STATE
    if any(
        part in normalized
        for part in (
            "theme",
            "onboard",
            "seen",
            "dismiss",
            "notification",
            "editor",
            "tutorial",
            "hint",
            "survey",
        )
    ):
        return RegistryFieldCategory.UI_STATE
    if any(part in normalized for part in ("usage", "history", "count", "metric", "stats")):
        return RegistryFieldCategory.USAGE_STATE
    return RegistryFieldCategory.PROTECTED_TOP_LEVEL


def _safe_field_name(value: str) -> bool:
    return 0 < len(value) <= 128 and value.isascii() and all(
        character.isalnum() or character in {"_", "-"} for character in value
    )


def _canonical_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ClaudeRegistryError("registry_malformed") from exc
    return hashlib.sha256(encoded).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = child
    return value


def _reject_nonfinite(_value: str) -> None:
    raise ValueError("non-finite number")
