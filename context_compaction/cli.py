"""Operator and hook-process CLI for the context compaction pilot."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Sequence

from .activation import (
    ActivationError,
    ActivationManager,
    ActivationPlan,
    load_owned_json,
)
from .adapters import (
    MAX_HOOK_INPUT_BYTES,
    AdapterError,
    ToolCapability,
    emit_host_response,
    parse_host_event,
    validate_observable_tool_names,
)
from .lifecycle import LifecycleCore
from .models import (
    BudgetLimits,
    DegradedReason,
    GateState,
    HookDecision,
    Host,
    HostPilotConfig,
    PilotConfig,
)
from .repository import RepositoryError, RepositoryResolver
from .storage import StateStore, StorageError

_HOOK_EVENTS = ("PreCompact", "PostCompact", "SessionStart", "PreToolUse", "PostToolUse")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="context-pilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "enable", "run"):
        command = subparsers.add_parser(name)
        _add_activation_paths(command)
        command.add_argument("--host", choices=[item.value for item in Host], required=True)
        command.add_argument("--repo", required=True)
        command.add_argument("--task-slug")
        command.add_argument("--tool-inventory", required=True)
        command.add_argument("--hook-trusted", action="store_true")
        if name == "enable":
            command.add_argument("--approved-plan-hash", required=True)

    status = subparsers.add_parser("status")
    _add_activation_paths(status)
    status.add_argument("--host", choices=[item.value for item in Host], required=True)
    status.add_argument("--repo")

    validate = subparsers.add_parser("validate")
    validate.add_argument("--pilot-config", required=True)
    validate.add_argument("--event", required=True)
    validate.add_argument("--evidence", action="append", default=[])

    disable = subparsers.add_parser("disable")
    _add_activation_paths(disable)
    disable.add_argument("--host", choices=[item.value for item in Host], required=True)

    purge = subparsers.add_parser("purge-state")
    purge.add_argument("--repo", required=True)
    purge.add_argument("--fallback-base")

    hook = subparsers.add_parser("hook")
    hook.add_argument("--host", choices=[item.value for item in Host], required=True)
    hook.add_argument("--host-version", required=True)
    hook.add_argument("--pilot-config", required=True)
    hook.add_argument("--expected-event", choices=_HOOK_EVENTS, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command in {"plan", "enable", "run"}:
            manager = _manager(arguments)
            plan = _build_plan(manager, arguments)
            if arguments.command == "plan":
                _print_json(_plan_preview(plan))
                return (
                    0
                    if plan.state.value
                    in {"ready", "enabled_unobserved", "active"}
                    else 2
                )
            if arguments.command == "enable":
                result = manager.enable(
                    plan, approved_plan_hash=arguments.approved_plan_hash
                )
                _print_json(_result(result))
                return 0
            return manager.run(plan)
        if arguments.command == "status":
            manager = _manager(arguments)
            _print_json(
                manager.status(
                    Host(arguments.host), repository_root=arguments.repo
                )
            )
            return 0
        if arguments.command == "disable":
            result = _manager(arguments).disable(Host(arguments.host))
            _print_json(_result(result))
            return 0
        if arguments.command == "purge-state":
            store = StateStore(
                arguments.repo,
                fallback_base=arguments.fallback_base,
            )
            store.purge()
            _print_json({"status": "purged", "owned_state_only": True})
            return 0
        if arguments.command == "validate":
            core, _host, _version, _observable_tools = _core_from_allowlist(
                arguments.pilot_config
            )
            decision = core.validate(
                arguments.event, evidence_paths=tuple(arguments.evidence)
            )
            _print_json(_decision_status(decision))
            return 0 if decision.continue_ else 2
        if arguments.command == "hook":
            return _run_hook(arguments)
    except (
        ActivationError,
        AdapterError,
        OSError,
        RepositoryError,
        StorageError,
        ValueError,
    ) as exc:
        reason = getattr(exc, "reason", None)
        _print_json(
            {
                "status": "error",
                "code": reason.value if reason is not None else "internal_error",
            }
        )
        return 2
    except Exception:
        _print_json(
            {
                "status": "error",
                "code": DegradedReason.INTERNAL_ERROR.value,
                "correlation_id": str(uuid.uuid4()),
            }
        )
        return 2
    return 2


def _run_hook(arguments: argparse.Namespace) -> int:
    raw = sys.stdin.buffer.read(MAX_HOOK_INPUT_BYTES + 1)
    observed_event = _peek_hook_event(raw)
    try:
        if len(raw) > MAX_HOOK_INPUT_BYTES:
            raise AdapterError(
                reason=DegradedReason.STATE_OVERSIZED,
                message="hook input exceeds limit",
            )
        core, configured_host, configured_version, observable_tools = (
            _core_from_allowlist(arguments.pilot_config)
        )
        host = Host(arguments.host)
        if host is not configured_host or arguments.host_version != configured_version:
            raise ActivationError(
                DegradedReason.ACTIVATION_CONFLICT,
                "hook invocation does not match allowlist",
            )
        parsed = parse_host_event(
            host,
            arguments.host_version,
            raw,
            trusted=True,
            repository_root=core.repository.root,
        )
        if parsed.event.event_name != arguments.expected_event:
            raise ActivationError(
                DegradedReason.ACTIVATION_CONFLICT,
                "hook event does not match its registered command",
            )
        if (
            parsed.event.tool_name is not None
            and parsed.event.tool_name not in observable_tools
        ):
            decision = HookDecision(
                status="denied",
                continue_=False,
                stop_reason="uncovered_tool",
                gate_state=GateState.DEGRADED,
                degraded_reasons=(DegradedReason.ACTIVATION_CONFLICT,),
            )
            _print_json(emit_host_response(host, parsed.event.event_name, decision))
            return 0
        decision = core.handle_event(parsed.event)
        _print_json(emit_host_response(host, parsed.event.event_name, decision))
        return 0
    except Exception:
        if arguments.expected_event == "PreCompact" and observed_event in {
            None,
            "PreCompact",
        }:
            _print_json({"continue": True})
            return 0
        raise


def _peek_hook_event(raw: bytes) -> str | None:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    event = value.get("hook_event_name")
    return event if isinstance(event, str) and event in _HOOK_EVENTS else None


def _core_from_allowlist(
    path: str | Path,
) -> tuple[LifecycleCore, Host, str, frozenset[str]]:
    value = load_owned_json(path)
    host = Host(str(value["host"]))
    version = str(value["host_version"])
    observable_tools = frozenset(
        validate_observable_tool_names(value.get("observable_tools"))
    )
    budgets_value = value.get("budgets", {})
    if not isinstance(budgets_value, dict):
        raise ValueError("invalid budget configuration")
    budgets = BudgetLimits(
        reentry_chars=_strict_positive_int(
            budgets_value.get("reentry_chars", 8000), "reentry_chars"
        ),
        reentry_estimated_tokens=_strict_positive_int(
            budgets_value.get("reentry_estimated_tokens", 2000),
            "reentry_estimated_tokens",
        ),
        memory_text_chars=_strict_positive_int(
            budgets_value.get("memory_text_chars", 4000), "memory_text_chars"
        ),
        memory_item_chars=_strict_positive_int(
            budgets_value.get("memory_item_chars", 500), "memory_item_chars"
        ),
        memory_envelope_chars=_strict_positive_int(
            budgets_value.get("memory_envelope_chars", 8000),
            "memory_envelope_chars",
        ),
    )
    codex = HostPilotConfig(
        enabled=host is Host.CODEX,
        supported_versions=("0.145.0",),
        auto_token_limit=64_000,
        auto_limit_scope="body_after_prefix",
        tool_output_limit=12_000,
    )
    claude = HostPilotConfig(
        enabled=host is Host.CLAUDE,
        supported_versions=("2.1.220",),
        auto_token_limit=100_000,
        auto_percent=80,
    )
    config = PilotConfig(
        repository_root=str(value["repository_root"]),
        repository_fingerprint=str(value["repository_fingerprint"]),
        task_slug=(str(value["task_slug"]) if value.get("task_slug") else None),
        codex=codex,
        claude=claude,
        budgets=budgets,
        enabled=True,
    )
    resolver = RepositoryResolver(
        config.repository_root,
        allowed_fingerprint=config.repository_fingerprint,
        explicit_task_slug=config.task_slug,
    )
    fallback = value.get("state_fallback_root")
    core = LifecycleCore(
        config,
        resolver,
        StateStore(
            config.repository_root,
            fallback_base=str(fallback) if fallback is not None else None,
        ),
    )
    return core, host, version, observable_tools


def _add_activation_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--codex-home", default=_default_codex_home())
    parser.add_argument("--app-data", default=_default_app_data())
    parser.add_argument("--host-executable")
    parser.add_argument("--python-executable", default=sys.executable)


def _manager(arguments: argparse.Namespace) -> ActivationManager:
    executables = (
        {Host(arguments.host): arguments.host_executable}
        if getattr(arguments, "host_executable", None)
        else None
    )
    return ActivationManager(
        source_root=arguments.source_root,
        codex_home=arguments.codex_home,
        app_data=arguments.app_data,
        executables=executables,
        python_executable=arguments.python_executable,
    )


def _build_plan(
    manager: ActivationManager, arguments: argparse.Namespace
) -> ActivationPlan:
    capabilities = _load_inventory(arguments.tool_inventory)
    return manager.plan(
        Host(arguments.host),
        arguments.repo,
        task_slug=arguments.task_slug,
        capabilities=capabilities,
        hook_trusted=arguments.hook_trusted,
    )


def _load_inventory(path: str | Path) -> tuple[ToolCapability, ...]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("tool inventory must be a list")
    result: list[ToolCapability] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "name",
            "write_capable",
            "hook_observable",
        }:
            raise ValueError("invalid tool inventory record")
        result.append(
            ToolCapability(
                name=item["name"],
                write_capable=item["write_capable"],
                hook_observable=item["hook_observable"],
            )
        )
    return tuple(result)


def _plan_preview(plan: ActivationPlan) -> dict[str, object]:
    return {
        "host": plan.host.value,
        "host_version": plan.host_version,
        "repository_fingerprint": plan.repository_fingerprint,
        "task_slug": plan.task_slug,
        "state": plan.state.value,
        "plan_sha256": plan.plan_sha256,
        "degraded_reasons": [item.value for item in plan.degraded_reasons],
        "files": [
            {
                "path": str(item.path),
                "mutation": item.mutation,
                "content_sha256": item.content_sha256,
                "content": item.content,
            }
            for item in plan.files
        ],
        "launch": {
            "executable_sha256": plan.launch.executable_sha256,
            "arguments": list(plan.launch.arguments),
            "environment": dict(plan.launch.environment),
            "path_prepend": [str(path) for path in plan.launch.path_prepend],
        },
    }


def _result(result) -> dict[str, object]:
    return {
        "host": result.host.value,
        "state": result.state.value,
        "changed_target_count": result.changed_target_count,
    }


def _decision_status(decision) -> dict[str, object]:
    return {
        "status": decision.status,
        "event_id": decision.event_id,
        "continue": decision.continue_,
        "gate_state": decision.gate_state.value if decision.gate_state else None,
        "degraded_reasons": [item.value for item in decision.degraded_reasons],
    }


def _default_codex_home() -> str:
    configured = os.environ.get("CODEX_HOME")
    return configured if configured else str(Path.home() / ".codex")


def _strict_positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"invalid {name}")
    return value


def _default_app_data() -> str:
    configured = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    if configured:
        return str(Path(configured) / "coding-cli")
    return str(Path.home() / ".local" / "state" / "coding-cli")


def _print_json(value: object) -> None:
    sys.stdout.write(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
