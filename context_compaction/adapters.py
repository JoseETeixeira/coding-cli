"""Strict Codex and Claude Code hook adapters over one semantic core."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import DegradedReason, HookDecision, HookEvent, Host, ToolClass, Trigger

MAX_HOOK_INPUT_BYTES = 1_048_576
SUPPORTED_HOST_VERSIONS: Mapping[Host, tuple[str, ...]] = {
    Host.CODEX: ("0.145.0",),
    Host.CLAUDE: ("2.1.220",),
}
_EVENTS = {"PreCompact", "PostCompact", "SessionStart", "PreToolUse", "PostToolUse"}
_TRIGGERS = {"manual", "auto"}
_SOURCES = {"startup", "resume", "clear", "compact", "fork"}
_UNTRUSTED_MARKER = re.compile(
    r"(?i)(?:ignore\s+(?:all\s+)?previous|<\s*system|system\s+prompt|assistant\s+to=)"
)
_SHELL_META = re.compile(r"[;&|><`\r\n]|\$\(|\$\{|%[A-Za-z_][A-Za-z0-9_]*%")
_DIRECT_READS = {
    "askuserquestion",
    "read",
    "read_file",
    "glob",
    "grep",
    "request_user_input",
    "skill",
    "taskget",
    "tasklist",
    "view_image",
    "mcp__filesystem__read_file",
    "mcp__filesystem__read_text_file",
    "mcp__filesystem__list_directory",
    "mcp__mnemo__code_index_status",
    "mcp__mnemo__code_search",
    "mcp__mnemo__memory_get",
    "mcp__mnemo__memory_list",
    "mcp__mnemo__memory_search",
    "mcp__mnemo__memory_stats",
    "mcp__mnemo__memory_status",
    "mcp__mnemo__task_context",
}
_FILE_EVIDENCE_READS = {
    "read",
    "read_file",
    "view_image",
    "mcp__filesystem__read_file",
    "mcp__filesystem__read_text_file",
}
_LOCAL_WRITES = {
    "apply_patch",
    "edit",
    "write",
    "write_file",
    "notebookedit",
    "multiedit",
}
_EXTERNAL_NAME_MARKERS = (
    "create_pull_request",
    "send_message",
    "add_comment",
    "delete_",
    "deploy",
    "publish",
    "merge_pull_request",
    "update_pull_request",
    "push",
)
_READ_SHELL = {
    "cat",
    "get-childitem",
    "get-content",
    "head",
    "ls",
    "pwd",
    "resolve-path",
    "select-string",
    "sort-object",
    "tail",
    "test-path",
    "wc",
}


class AdapterError(ValueError):
    def __init__(self, reason: DegradedReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class HookMetadata:
    raw_bytes: int
    summary_chars: int | None = None
    summary_sha256: str | None = None
    untrusted_marker_present: bool = False
    pre_usage: int | None = None
    post_usage: int | None = None
    measurement_source: str = "unmeasured"


@dataclass(frozen=True)
class ParsedHook:
    event: HookEvent
    metadata: HookMetadata


@dataclass(frozen=True)
class ToolClassification:
    tool_class: ToolClass
    reason: str


@dataclass(frozen=True)
class ToolCapability:
    name: str
    write_capable: bool
    hook_observable: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name
            or self.name != self.name.strip()
            or len(self.name) > 256
            or "\x00" in self.name
        ):
            raise ValueError("invalid tool capability name")
        if not isinstance(self.write_capable, bool) or not isinstance(
            self.hook_observable, bool
        ):
            raise ValueError("tool capability flags must be boolean")


@dataclass(frozen=True)
class ToolInventoryResult:
    activation_allowed: bool
    observable: tuple[str, ...]
    uncovered_write_capable: tuple[str, ...]


def parse_host_event(
    host: Host,
    host_version: str,
    raw: str | bytes,
    *,
    trusted: bool = True,
    repository_root: str | Path | None = None,
    supported_versions: Mapping[Host, Sequence[str]] = SUPPORTED_HOST_VERSIONS,
) -> ParsedHook:
    """Normalize documented fields without opening transcripts or retaining bodies."""

    if not isinstance(host, Host):
        raise AdapterError(DegradedReason.STATE_MALFORMED, "unknown hook host")
    if not trusted:
        raise AdapterError(
            DegradedReason.INACTIVE_OR_UNTRUSTED_HOOK, "hook trust is not confirmed"
        )
    if host_version not in supported_versions.get(host, ()):
        raise AdapterError(
            DegradedReason.UNSUPPORTED_HOST_VERSION, "unsupported host version"
        )
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if not isinstance(encoded, bytes):
        raise AdapterError(DegradedReason.STATE_MALFORMED, "hook input must be bytes or text")
    if len(encoded) > MAX_HOOK_INPUT_BYTES:
        raise AdapterError(DegradedReason.STATE_OVERSIZED, "hook input exceeds limit")
    try:
        value = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(DegradedReason.STATE_MALFORMED, "invalid hook JSON") from exc
    if not isinstance(value, dict):
        raise AdapterError(DegradedReason.STATE_MALFORMED, "hook input must be an object")

    event_name = _required_string(value, "hook_event_name", 64)
    if event_name not in _EVENTS:
        raise AdapterError(DegradedReason.STATE_MALFORMED, "unsupported hook event")
    cwd = _required_string(value, "cwd", 32_768)
    session_id = _required_string(value, "session_id", 512)
    trigger_value = _optional_string(value, "trigger", 16)
    if trigger_value is not None and trigger_value not in _TRIGGERS:
        raise AdapterError(DegradedReason.STATE_MALFORMED, "invalid compact trigger")
    source = _optional_string(value, "source", 32)
    if source is not None and source not in _SOURCES:
        raise AdapterError(DegradedReason.STATE_MALFORMED, "invalid session source")

    tool_name = _optional_string(value, "tool_name", 256)
    tool_use_id = _optional_string(value, "tool_use_id", 512)
    tool_input = value.get("tool_input")
    if tool_input is not None and not isinstance(tool_input, dict):
        raise AdapterError(DegradedReason.STATE_MALFORMED, "tool_input must be an object")
    classification = (
        classify_tool(tool_name, tool_input or {})
        if tool_name is not None
        else ToolClassification(ToolClass.UNKNOWN, "no_tool")
    )
    fingerprint = _fingerprint_json(tool_input) if tool_input is not None else None
    root = Path(repository_root).resolve(strict=False) if repository_root else Path(cwd).resolve(strict=False)
    evidence = _evidence_path(tool_name, tool_input or {}, root)
    if (
        tool_name
        and tool_name.casefold() in _FILE_EVIDENCE_READS
        and evidence is None
    ):
        classification = ToolClassification(ToolClass.UNKNOWN, "unsafe_read_path")

    summary = value.get("compact_summary") if host is Host.CLAUDE else None
    if summary is not None and not isinstance(summary, str):
        raise AdapterError(DegradedReason.STATE_MALFORMED, "compact_summary must be text")
    summary_chars = len(summary) if summary is not None else None
    summary_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest() if summary is not None else None
    marker = bool(_UNTRUSTED_MARKER.search(summary)) if summary is not None else False
    pre_usage = _optional_nonnegative_int(value.get("pre_compact_tokens"))
    post_usage = _optional_nonnegative_int(value.get("post_compact_tokens"))
    measurement = "host_hook" if pre_usage is not None or post_usage is not None else "unmeasured"

    status = None
    if event_name == "PostToolUse":
        status = "failed" if value.get("tool_error") else "completed"
    event = HookEvent(
        host=host,
        host_version=host_version,
        event_name=event_name,
        cwd=cwd,
        trigger=Trigger(trigger_value) if trigger_value else None,
        source=source,
        session_id=session_id,
        turn_id=_optional_string(value, "turn_id", 512),
        model=_optional_string(value, "model", 256),
        tool_name=tool_name,
        tool_use_id=tool_use_id,
        tool_class=classification.tool_class if tool_name else None,
        input_fingerprint=fingerprint,
        evidence_relative_path=evidence,
        status=status,
        event_bytes=len(encoded),
        summary_chars=summary_chars,
        pre_usage=pre_usage,
        post_usage=post_usage,
        measurement_source=measurement,
    )
    # `summary`, `tool_input`, and the decoded object fall out of scope here.
    return ParsedHook(
        event,
        HookMetadata(
            raw_bytes=len(encoded),
            summary_chars=summary_chars,
            summary_sha256=summary_hash,
            untrusted_marker_present=marker,
            pre_usage=pre_usage,
            post_usage=post_usage,
            measurement_source=measurement,
        ),
    )


def classify_tool(tool_name: str | None, tool_input: Mapping[str, Any]) -> ToolClassification:
    if not tool_name:
        return ToolClassification(ToolClass.UNKNOWN, "missing_name")
    normalized = tool_name.casefold()
    if normalized in _DIRECT_READS:
        return ToolClassification(ToolClass.READ, "direct_read")
    if normalized in _LOCAL_WRITES or normalized.endswith("__write_file"):
        return ToolClassification(ToolClass.LOCAL_WRITE, "known_local_write")
    if any(marker in normalized for marker in _EXTERNAL_NAME_MARKERS):
        return ToolClassification(ToolClass.EXTERNAL_SIDE_EFFECT, "known_external_effect")
    if normalized in {"bash", "shell_command", "exec_command"}:
        command = tool_input.get("command")
        if not isinstance(command, str) or not command or len(command) > 32_768:
            return ToolClassification(ToolClass.UNKNOWN, "invalid_shell_input")
        return _classify_shell(command)
    return ToolClassification(ToolClass.UNKNOWN, "uncovered_tool")


def audit_tool_inventory(capabilities: Sequence[ToolCapability]) -> ToolInventoryResult:
    observable = tuple(sorted({item.name for item in capabilities if item.hook_observable}))
    uncovered = tuple(
        sorted(
            {
                item.name
                for item in capabilities
                if item.write_capable and not item.hook_observable
            }
        )
    )
    return ToolInventoryResult(not uncovered, observable, uncovered)


def validate_observable_tool_names(value: object) -> tuple[str, ...]:
    """Validate the exact runtime inventory stored in an owned allowlist."""

    if not isinstance(value, list):
        raise ValueError("invalid observable tool inventory")
    items: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or item != item.strip()
            or len(item) > 256
            or "\x00" in item
        ):
            raise ValueError("invalid observable tool inventory")
        items.append(item)
    if len(set(items)) != len(items):
        raise ValueError("invalid observable tool inventory")
    if items != sorted(items):
        raise ValueError("observable tool inventory must be sorted")
    return tuple(items)


def emit_host_response(
    host: Host, event_name: str, decision: HookDecision
) -> dict[str, Any]:
    """Emit only response fields documented by both supported host versions."""

    if host not in (Host.CODEX, Host.CLAUDE):
        raise AdapterError(DegradedReason.STATE_MALFORMED, "unknown response host")
    if event_name == "PreCompact":
        return {"continue": True}
    if event_name == "PreToolUse":
        if decision.continue_:
            return {}
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (decision.stop_reason or "validation_required")[:1_000],
            }
        }
    if event_name == "SessionStart":
        response: dict[str, Any] = {"continue": bool(decision.continue_)}
        if not decision.continue_:
            response["stopReason"] = (decision.stop_reason or "reconstruction_required")[:1_000]
        if decision.system_message:
            response["systemMessage"] = decision.system_message[:1_000]
        if decision.additional_context:
            response["hookSpecificOutput"] = {
                "hookEventName": "SessionStart",
                "additionalContext": decision.additional_context[:8_000],
            }
        return response
    if event_name == "PostToolUse" and not decision.continue_:
        return {
            "decision": "block",
            "reason": (decision.stop_reason or "validation_required")[:1_000],
        }
    if event_name == "PostCompact":
        return {}
    return {}


def _classify_shell(command: str) -> ToolClassification:
    if _SHELL_META.search(command):
        return ToolClassification(ToolClass.UNKNOWN, "shell_metacharacter")
    try:
        tokens = [_strip_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return ToolClassification(ToolClass.UNKNOWN, "shell_parse_error")
    if not tokens:
        return ToolClassification(ToolClass.UNKNOWN, "empty_shell")
    executable = tokens[0].casefold()
    arguments = tokens[1:]
    if executable == "git":
        if not arguments:
            return ToolClassification(ToolClass.UNKNOWN, "git_subcommand_missing")
        subcommand = arguments[0].casefold()
        if subcommand in {"status", "rev-parse", "show-ref", "ls-files"}:
            return ToolClassification(ToolClass.READ, "read_only_git")
        if subcommand == "branch" and all(item.startswith("-") for item in arguments[1:]):
            return ToolClassification(ToolClass.READ, "read_only_git")
        if subcommand in {"push", "pull", "fetch", "clone", "ls-remote"}:
            return ToolClassification(ToolClass.EXTERNAL_SIDE_EFFECT, "network_git")
        return ToolClassification(ToolClass.LOCAL_WRITE, "mutating_or_unproven_git")
    if executable in {"rg", "ripgrep"}:
        if any(
            item.casefold().startswith(("--pre", "--config")) for item in arguments
        ):
            return ToolClassification(ToolClass.UNKNOWN, "rg_external_program")
        return ToolClassification(ToolClass.READ, "read_only_search")
    if executable == "find":
        if any(item.casefold() in {"-delete", "-exec", "-execdir", "-ok"} for item in arguments):
            return ToolClassification(ToolClass.UNKNOWN, "find_mutation")
        return ToolClassification(ToolClass.READ, "read_only_find")
    if executable == "sed":
        if any(item == "-i" or item.startswith("--in-place") for item in arguments):
            return ToolClassification(ToolClass.LOCAL_WRITE, "sed_in_place")
        return ToolClassification(ToolClass.READ, "read_only_sed")
    if executable in _READ_SHELL:
        return ToolClassification(ToolClass.READ, "read_only_shell")
    return ToolClassification(ToolClass.UNKNOWN, "unknown_shell_executable")


def _evidence_path(
    tool_name: str | None, tool_input: Mapping[str, Any], root: Path
) -> str | None:
    if not tool_name:
        return None
    normalized = tool_name.casefold()
    if normalized in _DIRECT_READS:
        raw = tool_input.get("file_path", tool_input.get("path"))
    elif normalized in {"bash", "shell_command", "exec_command"}:
        command = tool_input.get("command")
        raw = _shell_evidence_path(command) if isinstance(command, str) else None
    else:
        return None
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        return None
    if any(marker in raw for marker in "*?[]"):
        return None
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve(strict=False)
    if not resolved.is_relative_to(root):
        return None
    if not resolved.is_file():
        return None
    relative = resolved.relative_to(root).as_posix()
    if not relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        return None
    return relative


def _shell_evidence_path(command: str) -> str | None:
    if _classify_shell(command).tool_class is not ToolClass.READ:
        return None
    try:
        tokens = [_strip_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return None
    if len(tokens) != 2 or tokens[0].casefold() not in {"cat", "get-content"}:
        return None
    path = tokens[1]
    return path if path and not path.startswith("-") else None


def _required_string(value: Mapping[str, Any], key: str, maximum: int) -> str:
    result = _optional_string(value, key, maximum)
    if result is None:
        raise AdapterError(DegradedReason.STATE_MALFORMED, f"missing {key}")
    return result


def _optional_string(value: Mapping[str, Any], key: str, maximum: int) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str) or not item or len(item) > maximum or "\x00" in item:
        raise AdapterError(DegradedReason.STATE_MALFORMED, f"invalid {key}")
    return item


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AdapterError(DegradedReason.STATE_MALFORMED, "invalid usage metric")
    return value


def _fingerprint_json(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
