"""Closed, versioned data contracts for the context-compaction pilot."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_EVENTS = {
    "PreCompact",
    "PostCompact",
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
}


class _StringEnum(str, Enum):
    pass


class Host(_StringEnum):
    CODEX = "codex"
    CLAUDE = "claude"


class Trigger(_StringEnum):
    MANUAL = "manual"
    AUTO = "auto"


class GateState(_StringEnum):
    CAPTURED = "captured"
    VALIDATION_REQUIRED = "validation_required"
    VALIDATED = "validated"
    DEGRADED = "degraded"


class ToolClass(_StringEnum):
    READ = "read"
    LOCAL_WRITE = "local_write"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    UNKNOWN = "unknown"


class ActionStatus(_StringEnum):
    PLANNED = "planned"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    AMBIGUOUS = "ambiguous"


class DegradedReason(_StringEnum):
    UNSUPPORTED_HOST_VERSION = "unsupported_host_version"
    INACTIVE_OR_UNTRUSTED_HOOK = "inactive_or_untrusted_hook"
    ALLOWLIST_MISMATCH = "allowlist_mismatch"
    TASK_AMBIGUOUS = "task_ambiguous"
    STATE_MISSING = "state_missing"
    STATE_MALFORMED = "state_malformed"
    STATE_STALE = "state_stale"
    STATE_OVERSIZED = "state_oversized"
    STATE_CONTRADICTORY = "state_contradictory"
    ARTIFACT_MISSING = "artifact_missing"
    SOURCE_CHANGED = "source_changed"
    SCOPED_RULES_UNVALIDATED = "scoped_rules_unvalidated"
    ACTION_AMBIGUOUS = "action_ambiguous"
    APPROVAL_UNRESOLVED = "approval_unresolved"
    MEMORY_UNAVAILABLE = "memory_unavailable"
    ACTIVATION_CONFLICT = "activation_conflict"
    OWNED_FILE_DRIFT = "owned_file_drift"
    HOST_REGISTRY_DRIFT = "host_registry_drift"
    METRIC_UNAVAILABLE = "metric_unavailable"
    INTERNAL_ERROR = "internal_error"


class RegistryFieldCategory(_StringEnum):
    EXISTING_PROJECT_STATE = "existing_project_state"
    CACHE_STATE = "cache_state"
    AUTHENTICATION_METADATA = "authentication_metadata"
    FEATURE_STATE = "feature_state"
    USAGE_STATE = "usage_state"
    UI_STATE = "ui_state"
    PROTECTED_TOP_LEVEL = "protected_top_level"


@dataclass(frozen=True)
class BudgetLimits:
    reentry_chars: int = 8_000
    reentry_estimated_tokens: int = 2_000
    memory_text_chars: int = 4_000
    memory_item_chars: int = 500
    memory_envelope_chars: int = 8_000

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class HostPilotConfig:
    enabled: bool
    supported_versions: tuple[str, ...]
    auto_token_limit: int
    auto_limit_scope: str | None = None
    tool_output_limit: int | None = None
    auto_percent: int | None = None


@dataclass(frozen=True)
class PilotConfig:
    repository_root: str
    repository_fingerprint: str
    task_slug: str | None
    codex: HostPilotConfig
    claude: HostPilotConfig
    budgets: BudgetLimits = field(default_factory=BudgetLimits)
    enabled: bool = False
    retention_event_count: int = 200
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported pilot config schema")
        if not self.repository_root:
            raise ValueError("repository_root is required")
        _require_sha256(self.repository_fingerprint, "repository_fingerprint")
        if self.retention_event_count <= 0:
            raise ValueError("retention_event_count must be positive")


@dataclass(frozen=True)
class HookEvent:
    host: Host
    host_version: str
    event_name: str
    cwd: str
    trigger: Trigger | None = None
    source: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    model: str | None = None
    tool_name: str | None = None
    tool_use_id: str | None = None
    tool_class: ToolClass | None = None
    input_fingerprint: str | None = None
    evidence_relative_path: str | None = None
    status: str | None = None
    event_bytes: int | None = None
    summary_chars: int | None = None
    pre_usage: int | None = None
    post_usage: int | None = None
    measurement_source: str = "unmeasured"

    def __post_init__(self) -> None:
        if not isinstance(self.host, Host):
            raise ValueError("invalid host")
        _bounded_string(self.host_version, "host_version", maximum=64)
        if self.event_name not in _SUPPORTED_EVENTS:
            raise ValueError("unsupported hook event")
        _bounded_string(self.cwd, "cwd", maximum=32_768)
        if self.trigger is not None and not isinstance(self.trigger, Trigger):
            raise ValueError("invalid trigger")
        _optional_string(self.source, "source", maximum=64)
        _optional_string(self.session_id, "session_id", maximum=512)
        _optional_string(self.turn_id, "turn_id", maximum=512)
        _optional_string(self.model, "model", maximum=256)
        _optional_string(self.tool_name, "tool_name", maximum=256)
        _optional_string(self.tool_use_id, "tool_use_id", maximum=512)
        if self.tool_class is not None and not isinstance(self.tool_class, ToolClass):
            raise ValueError("invalid tool_class")
        if self.input_fingerprint is not None:
            _require_sha256(self.input_fingerprint, "input_fingerprint")
        if self.evidence_relative_path is not None:
            _require_relative_path(self.evidence_relative_path, "evidence_relative_path")
        _optional_string(self.status, "status", maximum=64)
        _optional_metric(self.event_bytes, "event_bytes")
        _optional_metric(self.summary_chars, "summary_chars")
        _optional_metric(self.pre_usage, "pre_usage")
        _optional_metric(self.post_usage, "post_usage")
        if self.measurement_source not in {"unmeasured", "host_hook"}:
            raise ValueError("invalid measurement_source")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HookEvent":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        missing = {"host", "host_version", "event_name", "cwd"} - set(value)
        if missing:
            raise ValueError(f"missing fields: {sorted(missing)}")
        event_name = _bounded_string(value["event_name"], "event_name", maximum=64)
        if event_name not in _SUPPORTED_EVENTS:
            raise ValueError("unsupported hook event")
        return cls(
            host=Host(value["host"]),
            host_version=_bounded_string(value["host_version"], "host_version", maximum=64),
            event_name=event_name,
            cwd=_bounded_string(value["cwd"], "cwd", maximum=32_768),
            trigger=Trigger(value["trigger"]) if value.get("trigger") is not None else None,
            source=_optional_string(value.get("source"), "source", maximum=64),
            session_id=_optional_string(value.get("session_id"), "session_id", maximum=512),
            turn_id=_optional_string(value.get("turn_id"), "turn_id", maximum=512),
            model=_optional_string(value.get("model"), "model", maximum=256),
            tool_name=_optional_string(value.get("tool_name"), "tool_name", maximum=256),
            tool_use_id=_optional_string(value.get("tool_use_id"), "tool_use_id", maximum=512),
            tool_class=(
                ToolClass(value["tool_class"])
                if value.get("tool_class") is not None
                else None
            ),
            input_fingerprint=_optional_sha256(
                value.get("input_fingerprint"), "input_fingerprint"
            ),
            evidence_relative_path=_optional_relative_path(
                value.get("evidence_relative_path"), "evidence_relative_path"
            ),
            status=_optional_string(value.get("status"), "status", maximum=64),
            event_bytes=_optional_metric(value.get("event_bytes"), "event_bytes"),
            summary_chars=_optional_metric(value.get("summary_chars"), "summary_chars"),
            pre_usage=_optional_metric(value.get("pre_usage"), "pre_usage"),
            post_usage=_optional_metric(value.get("post_usage"), "post_usage"),
            measurement_source=str(value.get("measurement_source", "unmeasured")),
        )


@dataclass(frozen=True)
class ActionRecord:
    action_id: str
    tool_class: ToolClass
    tool_name: str
    input_fingerprint: str
    status: ActionStatus
    started_at: str
    finished_at: str | None = None

    def __post_init__(self) -> None:
        _bounded_string(self.action_id, "action_id", maximum=512)
        _bounded_string(self.tool_name, "tool_name", maximum=256)
        _require_sha256(self.input_fingerprint, "input_fingerprint")
        _bounded_string(self.started_at, "started_at", maximum=64)
        _optional_string(self.finished_at, "finished_at", maximum=64)

    def to_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "tool_class": self.tool_class.value,
            "tool_name": self.tool_name,
            "input_fingerprint": self.input_fingerprint,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(frozen=True)
class DirtyPath:
    path: str
    status: str

    def __post_init__(self) -> None:
        _require_relative_path(self.path, "dirty path")
        _bounded_string(self.status, "dirty status", maximum=8)

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "status": self.status}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DirtyPath":
        return cls(path=str(value["path"]), status=str(value["status"]))


@dataclass(frozen=True)
class RepositorySnapshot:
    fingerprint: str
    branch: str | None
    head: str | None
    dirty_paths: tuple[DirtyPath, ...] = ()

    def __post_init__(self) -> None:
        _require_sha256(self.fingerprint, "repository fingerprint")
        _optional_string(self.branch, "branch", maximum=1024)
        if self.head is not None and not re.fullmatch(r"[0-9a-f]{40,64}", self.head):
            raise ValueError("invalid repository head")

    def to_dict(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "branch": self.branch,
            "head": self.head,
            "dirty_paths": [item.to_dict() for item in self.dirty_paths],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RepositorySnapshot":
        return cls(
            fingerprint=str(value["fingerprint"]),
            branch=value.get("branch"),
            head=value.get("head"),
            dirty_paths=tuple(
                DirtyPath.from_dict(item) for item in value.get("dirty_paths", [])
            ),
        )


@dataclass(frozen=True)
class StatePointer:
    kind: str
    stable_id: str
    relative_path: str
    anchor: str | None
    captured_hash: str

    def __post_init__(self) -> None:
        _bounded_string(self.kind, "pointer kind", maximum=64)
        _bounded_string(self.stable_id, "pointer stable_id", maximum=256)
        _require_relative_path(self.relative_path, "pointer relative_path")
        _optional_string(self.anchor, "pointer anchor", maximum=512)
        _require_sha256(self.captured_hash, "pointer captured_hash")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StatePointer":
        return cls(
            kind=str(value["kind"]),
            stable_id=str(value["stable_id"]),
            relative_path=str(value["relative_path"]),
            anchor=value.get("anchor"),
            captured_hash=str(value["captured_hash"]),
        )


@dataclass(frozen=True)
class SourceRead:
    relative_path: str
    current_hash: str
    recovery_epoch: str

    def __post_init__(self) -> None:
        _require_relative_path(self.relative_path, "source read path")
        _require_sha256(self.current_hash, "source read hash")
        _bounded_string(self.recovery_epoch, "recovery epoch", maximum=512)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceRead":
        return cls(
            relative_path=str(value["relative_path"]),
            current_hash=str(value["current_hash"]),
            recovery_epoch=str(value["recovery_epoch"]),
        )


@dataclass(frozen=True)
class ActiveStateEnvelope:
    event_id: str
    session_fingerprint: str
    host: Host
    host_version: str
    trigger: Trigger
    created_at: str
    repository: RepositorySnapshot
    task_slug: str | None
    goal_preview: str | None
    phase: int | None
    artifact_pointers: tuple[StatePointer, ...]
    actions: tuple[ActionRecord, ...]
    state: GateState
    degraded_reasons: tuple[DegradedReason, ...] = ()
    approval_status: str = "none"
    verification_status: str = "unverified"
    included_categories: tuple[str, ...] = ()
    omitted_categories: tuple[str, ...] = ()
    truncated: bool = False
    recovery_epoch: str | None = None
    source_reads: tuple[SourceRead, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        value = _to_primitive(asdict(self))
        value["repository"] = self.repository.to_dict()
        value["artifact_pointers"] = [item.to_dict() for item in self.artifact_pointers]
        value["actions"] = [item.to_dict() for item in self.actions]
        value["source_reads"] = [item.to_dict() for item in self.source_reads]
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ActiveStateEnvelope":
        if value.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported active-state schema")
        return cls(
            event_id=str(value["event_id"]),
            session_fingerprint=str(value["session_fingerprint"]),
            host=Host(value["host"]),
            host_version=str(value["host_version"]),
            trigger=Trigger(value["trigger"]),
            created_at=str(value["created_at"]),
            repository=RepositorySnapshot.from_dict(value["repository"]),
            task_slug=value.get("task_slug"),
            goal_preview=value.get("goal_preview"),
            phase=value.get("phase"),
            artifact_pointers=tuple(
                StatePointer.from_dict(item)
                for item in value.get("artifact_pointers", [])
            ),
            actions=tuple(_action_from_dict(item) for item in value.get("actions", [])),
            state=GateState(value["state"]),
            degraded_reasons=tuple(
                DegradedReason(item) for item in value.get("degraded_reasons", [])
            ),
            approval_status=str(value.get("approval_status", "none")),
            verification_status=str(value.get("verification_status", "unverified")),
            included_categories=tuple(value.get("included_categories", [])),
            omitted_categories=tuple(value.get("omitted_categories", [])),
            truncated=bool(value.get("truncated", False)),
            recovery_epoch=value.get("recovery_epoch"),
            source_reads=tuple(
                SourceRead.from_dict(item) for item in value.get("source_reads", [])
            ),
            schema_version=int(value["schema_version"]),
        )


@dataclass(frozen=True)
class DiagnosticEvent:
    event_id: str
    host: Host
    host_version: str
    trigger: str
    repository_fingerprint: str
    outcome: str
    degraded_reason_codes: tuple[str, ...] = ()
    duration_ms: int | None = None
    reentry_chars: int | None = None
    estimated_tokens: int | None = None
    included_category_names: tuple[str, ...] = ()
    omitted_category_names: tuple[str, ...] = ()
    changed_field_categories: tuple[RegistryFieldCategory, ...] = ()
    pre_usage: int | None = None
    post_usage: int | None = None
    measurement_source: str = "unmeasured"
    rollback_state: str | None = None

    def __post_init__(self) -> None:
        try:
            categories = tuple(
                RegistryFieldCategory(category)
                for category in self.changed_field_categories
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid changed_field_categories") from exc
        canonical = tuple(sorted(set(categories), key=lambda item: item.value))
        if categories != canonical:
            raise ValueError("changed_field_categories must be sorted and unique")
        object.__setattr__(self, "changed_field_categories", categories)

    def to_dict(self) -> dict[str, object]:
        return _to_primitive(asdict(self))


@dataclass(frozen=True)
class HookDecision:
    status: str
    event_id: str | None = None
    continue_: bool = True
    stop_reason: str | None = None
    system_message: str | None = None
    additional_context: str | None = None
    gate_state: GateState | None = None
    degraded_reasons: tuple[DegradedReason, ...] = ()
    updated_input: Mapping[str, Any] | None = None


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_primitive(item) for item in value]
    return value


def _bounded_string(value: Any, name: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise ValueError(f"invalid {name}")
    return value


def _optional_string(value: Any, name: str, *, maximum: int) -> str | None:
    if value is None:
        return None
    return _bounded_string(value, name, maximum=maximum)


def _optional_metric(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 10**12:
        raise ValueError(f"invalid {name}")
    return value


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _optional_sha256(value: Any, name: str) -> str | None:
    if value is None:
        return None
    _require_sha256(value, name)
    return value


def _require_relative_path(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 32_768 or "\x00" in value:
        raise ValueError(f"invalid {name}")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"invalid {name}")
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise ValueError(f"invalid {name}")
    return value


def _optional_relative_path(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_relative_path(value, name)


def _action_from_dict(value: Mapping[str, Any]) -> ActionRecord:
    return ActionRecord(
        action_id=str(value["action_id"]),
        tool_class=ToolClass(value["tool_class"]),
        tool_name=str(value["tool_name"]),
        input_fingerprint=str(value["input_fingerprint"]),
        status=ActionStatus(value["status"]),
        started_at=str(value["started_at"]),
        finished_at=value.get("finished_at"),
    )
