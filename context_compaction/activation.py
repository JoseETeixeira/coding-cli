"""Opt-in, isolated activation planning and owned-file rollback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .adapters import (
    SUPPORTED_HOST_VERSIONS,
    ToolCapability,
    audit_tool_inventory,
    validate_observable_tool_names,
)
from .claude_registry import (
    ClaudeRegistryError,
    ClaudeRegistryGuard,
    ClaudeRegistryManifest,
    ClaudeRegistryObservation,
)
from .contracts import ContractAssets, validate_contract_assets
from .models import DegradedReason, Host, SCHEMA_VERSION
from .repository import canonical_repository_root, repository_fingerprint
from .storage import StateStore, StorageError

OWNER_ID = "coding-cli-context-compaction-pilot"
GENERATOR_VERSION = "0.1.1"
CODEX_PROFILE_NAME = "context-pilot"
_CODEX_PROFILE_FILE = "context-pilot.config.toml"
_CLAUDE_OVERLAY_FILE = "claude-context-pilot.settings.json"
_CODEX_TRUST_EVENTS = (
    "pre_tool_use",
    "post_tool_use",
    "pre_compact",
    "post_compact",
    "session_start",
)
_CODEX_TRUST_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ActivationState(str, Enum):
    INACTIVE = "inactive"
    READY = "ready"
    ENABLED_UNOBSERVED = "enabled_unobserved"
    ACTIVE = "active"
    CONFLICT = "conflict"
    ROLLED_BACK = "rolled_back"


class ActivationError(RuntimeError):
    def __init__(self, reason: DegradedReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class OwnedFilePlan:
    path: Path
    content: str
    content_sha256: str
    mutation: str


@dataclass(frozen=True)
class LaunchSpec:
    executable: Path
    executable_sha256: str
    arguments: tuple[str, ...]
    environment: Mapping[str, str]
    path_prepend: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ActivationPlan:
    host: Host
    host_version: str
    repository_fingerprint: str
    task_slug: str | None
    state: ActivationState
    files: tuple[OwnedFilePlan, ...]
    launch: LaunchSpec
    degraded_reasons: tuple[DegradedReason, ...]
    plan_sha256: str


@dataclass(frozen=True)
class ActivationResult:
    host: Host
    state: ActivationState
    changed_target_count: int


class ActivationManager:
    """Generate and mutate only pilot-owned profile/overlay/allowlist files."""

    def __init__(
        self,
        *,
        source_root: str | Path,
        codex_home: str | Path,
        app_data: str | Path,
        executables: Mapping[Host, str | Path] | None = None,
        version_provider: Callable[[Host, Path], str] | None = None,
        python_executable: str | Path | None = None,
        claude_registry: str | Path | None = None,
        process_factory: Callable[..., subprocess.Popen] | None = None,
    ) -> None:
        self.source_root = canonical_repository_root(source_root)
        self.codex_home = Path(codex_home).expanduser().resolve(strict=False)
        self.app_data = Path(app_data).expanduser().resolve(strict=False)
        self._executables = {
            host: Path(path).expanduser().resolve(strict=False)
            for host, path in (executables or {}).items()
        }
        self._version_provider = version_provider or _default_version_provider
        self.python_executable = Path(
            python_executable or shutil.which("python") or os.sys.executable
        ).resolve(strict=False)
        self.claude_registry = Path(
            claude_registry or Path.home() / ".claude.json"
        ).expanduser().resolve(strict=False)
        self._process_factory = process_factory or subprocess.Popen

    def plan(
        self,
        host: Host,
        repository_root: str | Path,
        *,
        task_slug: str | None,
        capabilities: Sequence[ToolCapability],
        hook_trusted: bool,
    ) -> ActivationPlan:
        if not isinstance(host, Host):
            raise ActivationError(DegradedReason.ACTIVATION_CONFLICT, "unknown host")
        assets = validate_contract_assets(self.source_root)
        repository = canonical_repository_root(repository_root)
        fingerprint = repository_fingerprint(repository)
        executable = self._resolve_executable(host)
        executable_hash = _hash_file(executable)
        try:
            version = self._version_provider(host, executable).strip()
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise ActivationError(
                DegradedReason.UNSUPPORTED_HOST_VERSION, "host version cannot be verified"
            ) from exc

        reasons: list[DegradedReason] = []
        if version not in SUPPORTED_HOST_VERSIONS[host]:
            reasons.append(DegradedReason.UNSUPPORTED_HOST_VERSION)
        if not hook_trusted:
            reasons.append(DegradedReason.INACTIVE_OR_UNTRUSTED_HOOK)
        inventory = audit_tool_inventory(capabilities)
        if inventory.uncovered_write_capable:
            reasons.append(DegradedReason.ACTIVATION_CONFLICT)
        if not self.python_executable.is_file():
            reasons.append(DegradedReason.ACTIVATION_CONFLICT)

        hook_entry = self.source_root / "context_compaction" / "hook_entry.py"
        if not hook_entry.is_file():
            reasons.append(DegradedReason.ACTIVATION_CONFLICT)

        targets = self._targets(host)
        allowlist_path = targets[1]
        hook_command = _command_line(
            (
                str(self.python_executable),
                str(hook_entry),
                "hook",
                "--host",
                host.value,
                "--pilot-config",
                str(allowlist_path),
                "--host-version",
                version,
            )
        )
        allowlist = self._allowlist_content(
            host,
            version,
            executable,
            executable_hash,
            repository,
            fingerprint,
            task_slug,
            assets,
            inventory.observable,
        )
        if host is Host.CODEX:
            primary = self._codex_profile_content(assets, hook_command)
            launch = LaunchSpec(
                executable,
                executable_hash,
                ("--profile", CODEX_PROFILE_NAME, "--cd", str(repository)),
                {},
                self._codex_path_prepend(executable),
            )
        else:
            primary = self._claude_overlay_content(hook_command)
            launch = LaunchSpec(
                executable,
                executable_hash,
                (
                    "--settings",
                    str(targets[0]),
                    "--append-system-prompt-file",
                    str(self.source_root / assets.prompt_relative_path),
                    "--disallowedTools",
                    "WebFetch,WebSearch",
                ),
                {
                    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "100000",
                    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80",
                },
            )
        generated = (primary, allowlist)
        file_plans: list[OwnedFilePlan] = []
        conflict = False
        for target, content in zip(targets, generated, strict=True):
            self._validate_target(target, host)
            mutation, drift = _planned_mutation(target, content)
            if drift:
                conflict = True
                reasons.append(DegradedReason.OWNED_FILE_DRIFT)
            file_plans.append(
                OwnedFilePlan(target, content, _sha256_text(content), mutation)
            )
        reasons = _dedupe(reasons)
        if conflict:
            state = ActivationState.CONFLICT
        elif reasons:
            state = ActivationState.INACTIVE
        elif all(item.mutation == "none" for item in file_plans):
            state = (
                ActivationState.ACTIVE
                if self._activation_observed(host, version, repository)
                else ActivationState.ENABLED_UNOBSERVED
            )
        else:
            state = ActivationState.READY
        plan_hash = _plan_hash(
            host,
            version,
            fingerprint,
            task_slug,
            state,
            file_plans,
            launch,
            reasons,
        )
        return ActivationPlan(
            host,
            version,
            fingerprint,
            task_slug,
            state,
            tuple(file_plans),
            launch,
            tuple(reasons),
            plan_hash,
        )

    def enable(
        self, plan: ActivationPlan, *, approved_plan_hash: str
    ) -> ActivationResult:
        if approved_plan_hash != plan.plan_sha256:
            raise ActivationError(
                DegradedReason.ACTIVATION_CONFLICT, "approved plan hash does not match"
            )
        if plan.state in {
            ActivationState.ENABLED_UNOBSERVED,
            ActivationState.ACTIVE,
        }:
            return ActivationResult(plan.host, plan.state, 0)
        if plan.state is not ActivationState.READY:
            raise ActivationError(
                plan.degraded_reasons[0]
                if plan.degraded_reasons
                else DegradedReason.ACTIVATION_CONFLICT,
                "activation plan is not ready",
            )
        created: list[OwnedFilePlan] = []
        created_directories: list[Path] = []
        try:
            for item in plan.files:
                mutation, drift = _planned_mutation(item.path, item.content)
                if drift or mutation not in {"create", "none"}:
                    raise ActivationError(
                        DegradedReason.OWNED_FILE_DRIFT, "activation target changed after planning"
                    )
                if mutation == "none":
                    continue
                missing: list[Path] = []
                cursor = item.path.parent
                while not cursor.exists():
                    missing.append(cursor)
                    cursor = cursor.parent
                item.path.parent.mkdir(parents=True, exist_ok=True)
                created_directories.extend(reversed(missing))
                created.append(item)
                _atomic_write(item.path, item.content)
        except Exception:
            for item in reversed(created):
                if item.path.exists() and _sha256_text(
                    item.path.read_text(encoding="utf-8")
                ) == item.content_sha256:
                    item.path.unlink(missing_ok=True)
            for directory in sorted(
                set(created_directories), key=lambda item: len(item.parts), reverse=True
            ):
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            raise
        return ActivationResult(
            plan.host, ActivationState.ENABLED_UNOBSERVED, len(created)
        )

    def disable(self, host: Host) -> ActivationResult:
        targets = self._targets(host)
        existing = [path for path in targets if path.exists()]
        if not existing:
            return ActivationResult(host, ActivationState.INACTIVE, 0)
        for path in existing:
            valid, _payload_hash = _validate_owned_file(path)
            if not valid:
                raise ActivationError(
                    DegradedReason.OWNED_FILE_DRIFT, "owned activation file drifted"
                )
        allowlist_path = next(
            (path for path in existing if path.name.endswith(".allowlist.json")),
            None,
        )
        if allowlist_path is not None:
            self._record_deactivation(host, load_owned_json(allowlist_path))
        for path in existing:
            path.unlink()
        return ActivationResult(host, ActivationState.INACTIVE, len(existing))

    def run(
        self,
        plan: ActivationPlan,
        *,
        launcher: Callable[[Sequence[str], Mapping[str, str]], int] | None = None,
    ) -> int:
        if plan.state not in {
            ActivationState.ENABLED_UNOBSERVED,
            ActivationState.ACTIVE,
        }:
            raise ActivationError(
                DegradedReason.INACTIVE_OR_UNTRUSTED_HOOK, "pilot is not active"
            )
        if _hash_file(plan.launch.executable) != plan.launch.executable_sha256:
            raise ActivationError(
                DegradedReason.OWNED_FILE_DRIFT, "host executable identity changed"
            )
        for item in plan.files:
            if not item.path.is_file():
                raise ActivationError(
                    DegradedReason.OWNED_FILE_DRIFT, "activation file changed"
                )
            try:
                actual = item.path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise ActivationError(
                    DegradedReason.OWNED_FILE_DRIFT, "activation file changed"
                ) from exc
            if not _matches_planned_content(item.path, actual, item.content):
                raise ActivationError(
                    DegradedReason.OWNED_FILE_DRIFT, "activation file changed"
                )
        arguments = (str(plan.launch.executable), *plan.launch.arguments)
        launch_environment = dict(plan.launch.environment)
        if plan.launch.path_prepend:
            inherited = os.environ.get("PATH", "")
            segments = [str(path) for path in plan.launch.path_prepend]
            if inherited:
                segments.append(inherited)
            launch_environment["PATH"] = os.pathsep.join(segments)
        if plan.host is Host.CLAUDE:
            repository = _repository_from_plan(plan)
            return self._run_claude_guarded(
                plan,
                repository,
                arguments,
                launch_environment,
                launcher=launcher,
            )
        if launcher is not None:
            return launcher(arguments, launch_environment)
        environment = os.environ.copy()
        environment.update(launch_environment)
        return subprocess.call(arguments, env=environment)

    def _run_claude_guarded(
        self,
        plan: ActivationPlan,
        repository: Path,
        arguments: Sequence[str],
        launch_environment: Mapping[str, str],
        *,
        launcher: Callable[[Sequence[str], Mapping[str, str]], int] | None,
    ) -> int:
        store = StateStore(
            repository,
            fallback_base=self.app_data / "context-compaction" / "state",
        )
        started = time.perf_counter()
        try:
            guard = ClaudeRegistryGuard.capture(self.claude_registry, repository)
        except ClaudeRegistryError as exc:
            _append_registry_guard_event(
                store,
                plan,
                outcome="rejected",
                duration_ms=_elapsed_ms(started),
                error_code=exc.code,
                changed_field_categories=exc.changed_field_categories,
            )
            raise ActivationError(
                DegradedReason.HOST_REGISTRY_DRIFT,
                "Claude registry baseline rejected",
            ) from exc
        _append_registry_guard_event(
            store,
            plan,
            outcome="captured",
            duration_ms=_elapsed_ms(started),
            manifest=guard.manifest,
        )

        if launcher is not None:
            result = launcher(arguments, launch_environment)
            self._finish_claude_registry_guard(store, plan, guard, started)
            return result

        environment = os.environ.copy()
        environment.update(launch_environment)
        last_signature = _file_signature(self.claude_registry)
        process = self._process_factory(arguments, env=environment, cwd=repository)
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            signature = _file_signature(self.claude_registry)
            if signature != last_signature:
                try:
                    guard.validate_current(final=False)
                except ClaudeRegistryError as exc:
                    _terminate_exact_process(process)
                    _append_registry_guard_event(
                        store,
                        plan,
                        outcome="rejected",
                        duration_ms=_elapsed_ms(started),
                        manifest=guard.manifest,
                        error_code=exc.code,
                        changed_field_categories=exc.changed_field_categories,
                    )
                    raise ActivationError(
                        DegradedReason.HOST_REGISTRY_DRIFT,
                        "Claude registry changed outside the approved semantics",
                    ) from exc
                last_signature = signature
            time.sleep(0.25)

        self._finish_claude_registry_guard(store, plan, guard, started)
        return returncode

    def _finish_claude_registry_guard(
        self,
        store: StateStore,
        plan: ActivationPlan,
        guard: ClaudeRegistryGuard,
        started: float,
    ) -> None:
        try:
            observation = guard.validate_current(final=True)
        except ClaudeRegistryError as exc:
            _append_registry_guard_event(
                store,
                plan,
                outcome="rejected",
                duration_ms=_elapsed_ms(started),
                manifest=guard.manifest,
                error_code=exc.code,
                changed_field_categories=exc.changed_field_categories,
            )
            raise ActivationError(
                DegradedReason.HOST_REGISTRY_DRIFT,
                "Claude registry final state rejected",
            ) from exc
        _append_registry_guard_event(
            store,
            plan,
            outcome="validated",
            duration_ms=_elapsed_ms(started),
            observation=observation,
        )

    def status(
        self, host: Host, *, repository_root: str | Path | None = None
    ) -> dict[str, object]:
        targets = self._targets(host)
        states: list[str] = []
        drift = False
        allowlist: dict[str, object] | None = None
        inventory_enforced = False
        observable_tool_count = 0
        for path in targets:
            if not path.exists():
                states.append("missing")
                continue
            valid, _ = _validate_owned_file(path)
            states.append("owned" if valid else "drifted")
            drift = drift or not valid
            if valid and path.name.endswith(".allowlist.json"):
                allowlist = load_owned_json(path)
                try:
                    observable_tools = validate_observable_tool_names(
                        allowlist.get("observable_tools")
                    )
                except ValueError:
                    pass
                else:
                    inventory_enforced = True
                    observable_tool_count = len(observable_tools)
        targets_conflict = drift or ("owned" in states and "missing" in states)
        targets_owned = bool(states) and all(item == "owned" for item in states)
        fingerprint = (
            repository_fingerprint(repository_root) if repository_root is not None else None
        )
        allowlist_version = (
            allowlist.get("host_version") if allowlist is not None else None
        )
        allowlist_fingerprint = (
            allowlist.get("repository_fingerprint") if allowlist is not None else None
        )
        allowlist_binding_valid = bool(
            allowlist is not None
            and allowlist.get("host") == host.value
            and isinstance(allowlist_version, str)
            and allowlist_version in SUPPORTED_HOST_VERSIONS[host]
            and isinstance(allowlist_fingerprint, str)
            and (
                fingerprint is None
                or allowlist_fingerprint == fingerprint
            )
        )
        events: list[dict[str, object]] = []
        diagnostic_degraded = False
        if repository_root is not None:
            try:
                events = StateStore(
                    repository_root,
                    fallback_base=self.app_data / "context-compaction" / "state",
                ).read_events()
            except (StorageError, OSError, ValueError):
                diagnostic_degraded = True
        latest = _latest_bound_host_event(
            events,
            host=host,
            host_version=allowlist_version if isinstance(allowlist_version, str) else "",
            repository_fingerprint=(
                fingerprint
                if fingerprint is not None
                else allowlist_fingerprint
                if isinstance(allowlist_fingerprint, str)
                else ""
            ),
        )
        registry_latest = next(
            (
                item
                for item in reversed(events)
                if item.get("host") == "claude_registry"
                and item.get("guard_host") == host.value
                and item.get("host_version") == allowlist_version
                and item.get("repository_fingerprint")
                == (
                    fingerprint
                    if fingerprint is not None
                    else allowlist_fingerprint
                )
            ),
            None,
        )
        activation_observed = bool(
            latest is not None and latest.get("outcome") != "disabled"
        )
        if targets_conflict or (
            targets_owned
            and (not inventory_enforced or not allowlist_binding_valid)
        ):
            state = ActivationState.CONFLICT.value
        elif targets_owned and activation_observed:
            state = ActivationState.ACTIVE.value
        elif targets_owned:
            state = ActivationState.ENABLED_UNOBSERVED.value
        else:
            state = ActivationState.INACTIVE.value
        result: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "host": host.value,
            "host_version": (
                str(allowlist.get("host_version"))
                if allowlist is not None
                else "unmeasured"
            ),
            "state": state,
            "repository_fingerprint": fingerprint,
            "owned_target_count": sum(item == "owned" for item in states),
            "missing_target_count": sum(item == "missing" for item in states),
            "drifted_target_count": sum(item == "drifted" for item in states),
            "activation_observed": activation_observed,
            "tool_inventory_enforced": inventory_enforced,
            "observable_tool_count": observable_tool_count,
            "diagnostic_event_count": len(events),
            "diagnostic_degraded": diagnostic_degraded,
            "measurement_source": (
                str(latest.get("measurement_source", "unmeasured"))
                if latest is not None
                else "unmeasured"
            ),
        }
        if latest is not None:
            allowed = (
                "event_id",
                "event_name",
                "model_class",
                "trigger",
                "outcome",
                "gate_state",
                "duration_ms",
                "event_bytes",
                "summary_chars",
                "reentry_chars",
                "estimated_tokens",
                "included_category_names",
                "omitted_category_names",
                "truncated",
                "pre_usage",
                "post_usage",
                "degraded_reason_codes",
            )
            result["latest_event"] = {key: latest.get(key) for key in allowed}
        if registry_latest is not None:
            allowed = (
                "event_id",
                "outcome",
                "gate_state",
                "duration_ms",
                "registry_bytes",
                "semantic_manifest_sha256",
                "change_names",
                "changed_field_categories",
                "target_trusted",
                "error_code",
                "degraded_reason_codes",
                "measurement_source",
            )
            result["registry_guard"] = {
                key: registry_latest.get(key) for key in allowed
            }
        if len(json.dumps(result, ensure_ascii=False, sort_keys=True)) > 8_000:
            raise ActivationError(
                DegradedReason.STATE_OVERSIZED, "bounded status exceeded its limit"
            )
        return result

    def _activation_observed(
        self, host: Host, host_version: str, repository: Path
    ) -> bool:
        try:
            events = StateStore(
                repository,
                fallback_base=self.app_data / "context-compaction" / "state",
            ).read_events()
        except (StorageError, OSError, ValueError):
            return False
        latest = _latest_bound_host_event(
            events,
            host=host,
            host_version=host_version,
            repository_fingerprint=repository_fingerprint(repository),
        )
        return bool(latest is not None and latest.get("outcome") != "disabled")

    def _record_deactivation(
        self, host: Host, allowlist: Mapping[str, object]
    ) -> None:
        try:
            if allowlist.get("host") != host.value:
                return
            repository = canonical_repository_root(allowlist["repository_root"])
            fingerprint = repository_fingerprint(repository)
            if fingerprint != allowlist.get("repository_fingerprint"):
                return
            fallback = allowlist.get("state_fallback_root")
            store = StateStore(
                repository,
                fallback_base=str(fallback) if fallback is not None else None,
            )
            if not store.directory.exists():
                return
            event_id = str(uuid.uuid4())
            store.append_event(
                {
                    "schema_version": SCHEMA_VERSION,
                    "event_id": event_id,
                    "host": host.value,
                    "host_version": str(allowlist["host_version"]),
                    "event_name": "ActivationDisabled",
                    "trigger": "operator",
                    "repository_fingerprint": fingerprint,
                    "outcome": "disabled",
                    "degraded_reason_codes": [],
                    "measurement_source": "local_operator",
                },
                dedupe_key=f"activation-disabled:{event_id}",
            )
        except (KeyError, OSError, StorageError, TypeError, ValueError):
            # Diagnostics never prevent removal of otherwise valid owned files.
            return

    def _targets(self, host: Host) -> tuple[Path, Path]:
        if not isinstance(host, Host):
            raise ActivationError(
                DegradedReason.ACTIVATION_CONFLICT, "unknown host"
            )
        pilot_dir = self.app_data / "context-compaction"
        if host is Host.CODEX:
            return (
                self.codex_home / _CODEX_PROFILE_FILE,
                pilot_dir / "codex.allowlist.json",
            )
        return (
            pilot_dir / _CLAUDE_OVERLAY_FILE,
            pilot_dir / "claude.allowlist.json",
        )

    def _resolve_executable(self, host: Host) -> Path:
        configured = self._executables.get(host)
        if configured is None:
            discovered = shutil.which(host.value)
            if discovered is None:
                raise ActivationError(
                    DegradedReason.UNSUPPORTED_HOST_VERSION, "host executable not found"
                )
            configured = Path(discovered).resolve(strict=False)
        if not configured.is_file():
            raise ActivationError(
                DegradedReason.UNSUPPORTED_HOST_VERSION, "host executable is not a file"
            )
        return configured

    def _codex_path_prepend(self, executable: Path) -> tuple[Path, ...]:
        if os.name != "nt":
            return ()
        resources = executable.parent.parent / "codex-resources"
        required = (
            resources / "codex-windows-sandbox-setup.exe",
            resources / "codex-command-runner.exe",
        )
        if not all(path.is_file() for path in required):
            raise ActivationError(
                DegradedReason.ACTIVATION_CONFLICT,
                "Codex sandbox helper package is incomplete",
            )
        return (resources,)

    def _validate_target(self, target: Path, host: Host) -> None:
        base = self.codex_home if host is Host.CODEX and target.parent == self.codex_home else self.app_data
        resolved = target.resolve(strict=False)
        if not resolved.is_relative_to(base):
            raise ActivationError(
                DegradedReason.ACTIVATION_CONFLICT, "activation target escapes owned root"
            )
        cursor = resolved.parent
        while cursor != base.parent and cursor != cursor.parent:
            if cursor.exists() and cursor.is_symlink():
                raise ActivationError(
                    DegradedReason.ACTIVATION_CONFLICT, "activation target crosses a symlink"
                )
            if cursor == base:
                break
            cursor = cursor.parent

    def _codex_profile_content(
        self, assets: ContractAssets, hook_command: str
    ) -> str:
        prompt = str(self.source_root / assets.prompt_relative_path)
        body = (
            f"experimental_compact_prompt_file = {json.dumps(prompt)}\n"
            "model_auto_compact_token_limit = 64000\n"
            'model_auto_compact_token_limit_scope = "body_after_prefix"\n'
            "tool_output_token_limit = 12000\n"
            'web_search = "disabled"\n\n'
            "[features]\n"
            "hooks = true\n"
            "apps = false\n\n"
            "browser_use = false\n"
            "browser_use_external = false\n"
            "browser_use_full_cdp_access = false\n"
            "computer_use = false\n"
            "image_generation = false\n"
            "in_app_browser = false\n"
            "skill_mcp_dependency_install = false\n\n"
            + _toml_hook(
                "PreCompact",
                "^(manual|auto)$",
                _event_hook_command(hook_command, "PreCompact"),
            )
            + _toml_hook(
                "PostCompact",
                "^(manual|auto)$",
                _event_hook_command(hook_command, "PostCompact"),
            )
            + _toml_hook(
                "SessionStart",
                "^compact$",
                _event_hook_command(hook_command, "SessionStart"),
                context_limit=8000,
            )
            + _toml_hook(
                "PreToolUse", ".*", _event_hook_command(hook_command, "PreToolUse")
            )
            + _toml_hook(
                "PostToolUse", ".*", _event_hook_command(hook_command, "PostToolUse")
            )
        )
        return _owned_toml(body)

    def _claude_overlay_content(self, hook_command: str) -> str:
        events: dict[str, list[dict[str, object]]] = {}
        for name, matcher in (
            ("PreCompact", "manual|auto"),
            ("PostCompact", "manual|auto"),
            ("SessionStart", "compact"),
            ("PreToolUse", ".*"),
            ("PostToolUse", ".*"),
        ):
            events[name] = [
                {
                    "matcher": matcher,
                    "hooks": [
                        {
                            "type": "command",
                            "command": _event_hook_command(hook_command, name),
                            "timeout": 2,
                        }
                    ],
                }
            ]
        payload = {
            "autoCompactEnabled": True,
            "hooks": events,
            "permissions": {"deny": ["WebFetch", "WebSearch"]},
        }
        return _owned_json(payload)

    def _allowlist_content(
        self,
        host: Host,
        version: str,
        executable: Path,
        executable_hash: str,
        repository: Path,
        fingerprint: str,
        task_slug: str | None,
        assets: ContractAssets,
        observable_tools: Sequence[str],
    ) -> str:
        payload = {
            "host": host.value,
            "host_version": version,
            "host_executable": str(executable),
            "host_executable_sha256": executable_hash,
            "python_executable": str(self.python_executable),
            "repository_root": str(repository),
            "repository_fingerprint": fingerprint,
            "task_slug": task_slug,
            "source_root": str(self.source_root),
            "state_fallback_root": str(
                self.app_data / "context-compaction" / "state"
            ),
            "contract_relative_path": assets.prompt_relative_path,
            "contract_sha256": assets.prompt_sha256,
            "observable_tools": list(observable_tools),
            "budgets": {
                "reentry_chars": 8000,
                "reentry_estimated_tokens": 2000,
                "memory_text_chars": 4000,
                "memory_item_chars": 500,
                "memory_envelope_chars": 8000,
            },
        }
        return _owned_json(payload)


def load_owned_json(path: str | Path) -> dict[str, object]:
    """Load one self-verifying pilot JSON file and remove ownership metadata."""

    target = Path(path).resolve(strict=True)
    valid, _ = _validate_owned_file(target)
    if not valid:
        raise ActivationError(
            DegradedReason.OWNED_FILE_DRIFT, "pilot JSON ownership or hash is invalid"
        )
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ActivationError(
            DegradedReason.STATE_MALFORMED, "pilot JSON cannot be decoded"
        ) from exc
    value.pop("_context_pilot", None)
    return value


def _repository_from_plan(plan: ActivationPlan) -> Path:
    allowlist = next(
        (item for item in plan.files if item.path.name.endswith(".allowlist.json")),
        None,
    )
    if allowlist is None:
        raise ActivationError(
            DegradedReason.ACTIVATION_CONFLICT, "activation allowlist is missing"
        )
    try:
        value = json.loads(allowlist.content)
        repository = canonical_repository_root(value["repository_root"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ActivationError(
            DegradedReason.ACTIVATION_CONFLICT, "activation allowlist is invalid"
        ) from exc
    if repository_fingerprint(repository) != plan.repository_fingerprint:
        raise ActivationError(
            DegradedReason.ALLOWLIST_MISMATCH, "activation repository changed"
        )
    return repository


def _append_registry_guard_event(
    store: StateStore,
    plan: ActivationPlan,
    *,
    outcome: str,
    duration_ms: int,
    manifest: ClaudeRegistryManifest | None = None,
    observation: ClaudeRegistryObservation | None = None,
    error_code: str | None = None,
    changed_field_categories: Sequence[str] = (),
) -> None:
    event_id = str(uuid.uuid4())
    source = observation.to_dict() if observation is not None else (
        manifest.to_dict() if manifest is not None else {}
    )
    fingerprint = source.get(
        "observation_sha256", source.get("manifest_sha256")
    )
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "host": "claude_registry",
        "guard_host": Host.CLAUDE.value,
        "host_version": plan.host_version,
        "event_name": "ClaudeRegistryGuard",
        "trigger": "startup",
        "repository_fingerprint": plan.repository_fingerprint,
        "outcome": outcome,
        "gate_state": (
            "validated"
            if outcome == "validated"
            else "degraded"
            if outcome == "rejected"
            else "captured"
        ),
        "duration_ms": duration_ms,
        "registry_bytes": source.get("byte_count"),
        "semantic_manifest_sha256": fingerprint,
        "change_names": source.get("change_names", []),
        "changed_field_categories": list(changed_field_categories),
        "target_trusted": source.get("target_trusted", False),
        "error_code": error_code,
        "degraded_reason_codes": (
            [DegradedReason.HOST_REGISTRY_DRIFT.value]
            if outcome == "rejected"
            else []
        ),
        "measurement_source": "semantic_manifest",
    }
    store.append_event(payload, dedupe_key=f"registry:{event_id}")


def _latest_bound_host_event(
    events: Sequence[Mapping[str, object]],
    *,
    host: Host,
    host_version: str,
    repository_fingerprint: str,
) -> Mapping[str, object] | None:
    return next(
        (
            item
            for item in reversed(events)
            if item.get("host") == host.value
            and item.get("host_version") == host_version
            and item.get("repository_fingerprint") == repository_fingerprint
        ),
        None,
    )


def _file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _terminate_exact_process(process) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1_000))


def _default_version_provider(host: Host, executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=True,
        timeout=10,
    )
    match = next(
        (token for token in result.stdout.split() if token and token[0].isdigit()), None
    )
    if match is None:
        raise ValueError(f"{host.value} version was not reported")
    return match


def _owned_toml(body: str) -> str:
    digest = _sha256_text(body)
    return (
        f"# context-pilot-owner: {OWNER_ID}\n"
        f"# context-pilot-schema: {SCHEMA_VERSION}\n"
        f"# context-pilot-generator: {GENERATOR_VERSION}\n"
        f"# context-pilot-content-sha256: {digest}\n\n"
        f"{body}"
    )


def _owned_json(payload: Mapping[str, object]) -> str:
    digest = _sha256_json(payload)
    value = {
        "_context_pilot": {
            "owner": OWNER_ID,
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "content_sha256": digest,
        },
        **payload,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _validate_owned_file(path: Path) -> tuple[bool, str | None]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False, None
    if path.suffix == ".toml":
        lines = content.splitlines(keepends=True)
        if len(lines) < 6:
            return False, None
        expected = {
            "owner": OWNER_ID,
            "schema": str(SCHEMA_VERSION),
            "generator": GENERATOR_VERSION,
        }
        headers: dict[str, str] = {}
        digest: str | None = None
        for line in lines[:4]:
            if not line.startswith("# context-pilot-") or ":" not in line:
                return False, None
            key, value = line[2:].split(":", 1)
            short = key.removeprefix("context-pilot-")
            if short == "content-sha256":
                digest = value.strip()
            else:
                headers[short] = value.strip()
        body = "".join(lines[5:])
        body_for_digest = body
        marker = "[hooks.state]\n"
        marker_index = body.find(marker)
        if marker_index >= 0:
            if path.name != _CODEX_PROFILE_FILE or marker_index != body.rfind(marker):
                return False, digest
            suffix = body[marker_index:]
            if not _valid_codex_trust_suffix(path, suffix):
                return False, digest
            body_for_digest = body[:marker_index]
        valid = headers == expected and digest == _sha256_text(body_for_digest)
        return valid, digest
    try:
        value = json.loads(content)
        metadata = value.pop("_context_pilot")
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return False, None
    if not isinstance(metadata, dict):
        return False, None
    digest = metadata.get("content_sha256")
    valid = metadata == {
        "owner": OWNER_ID,
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "content_sha256": _sha256_json(value),
    }
    return valid, digest if isinstance(digest, str) else None


def _planned_mutation(path: Path, expected: str) -> tuple[str, bool]:
    if not path.exists():
        return "create", False
    if not path.is_file():
        return "conflict", True
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "conflict", True
    if _matches_planned_content(path, actual, expected):
        return "none", False
    return "conflict", True


def _matches_planned_content(path: Path, actual: str, expected: str) -> bool:
    if actual == expected:
        valid, _ = _validate_owned_file(path)
        return valid
    if path.name != _CODEX_PROFILE_FILE or not actual.startswith(expected):
        return False
    return _valid_codex_trust_suffix(path, actual[len(expected) :])


def _valid_codex_trust_suffix(path: Path, suffix: str) -> bool:
    if not suffix.startswith("[hooks.state]\n") or not suffix.endswith("\n"):
        return False
    try:
        value = tomllib.loads(suffix)
    except tomllib.TOMLDecodeError:
        return False
    if set(value) != {"hooks"} or not isinstance(value["hooks"], dict):
        return False
    hooks = value["hooks"]
    if set(hooks) != {"state"} or not isinstance(hooks["state"], dict):
        return False
    state = hooks["state"]
    expected_keys = {f"{path}:{event}:0:0" for event in _CODEX_TRUST_EVENTS}
    if set(state) != expected_keys:
        return False
    for entry in state.values():
        if (
            not isinstance(entry, dict)
            or "trusted_hash" not in entry
            or not set(entry).issubset({"trusted_hash", "enabled"})
        ):
            return False
        trusted_hash = entry["trusted_hash"]
        if not isinstance(trusted_hash, str) or _CODEX_TRUST_HASH.fullmatch(
            trusted_hash
        ) is None:
            return False
        if "enabled" in entry and entry["enabled"] is not True:
            return False
    return True


def _toml_hook(
    event: str, matcher: str, command: str, *, context_limit: int | None = None
) -> str:
    value = (
        f"[[hooks.{event}]]\n"
        f"matcher = {json.dumps(matcher)}\n"
        f"[[hooks.{event}.hooks]]\n"
        'type = "command"\n'
        f"command = {json.dumps(command)}\n"
        f"command_windows = {json.dumps(command)}\n"
        "timeout = 2\n"
    )
    if context_limit is not None:
        value += f"additionalContextLimit = {context_limit}\n"
    return value + "\n"


def _command_line(arguments: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(arguments))


def _event_hook_command(command: str, event: str) -> str:
    return f"{command} --expected-event {event}"


def _atomic_write(path: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)


def _plan_hash(
    host: Host,
    version: str,
    fingerprint: str,
    task_slug: str | None,
    state: ActivationState,
    files: Sequence[OwnedFilePlan],
    launch: LaunchSpec,
    reasons: Sequence[DegradedReason],
) -> str:
    payload = {
        "host": host.value,
        "version": version,
        "repository_fingerprint": fingerprint,
        "task_slug": task_slug,
        "state": state.value,
        "files": [
            {
                "target_fingerprint": _sha256_text(os.path.normcase(str(item.path))),
                "content_sha256": item.content_sha256,
                "mutation": item.mutation,
            }
            for item in files
        ],
        "executable_sha256": launch.executable_sha256,
        "arguments_fingerprint": _sha256_json(list(launch.arguments)),
        "environment_fingerprint": _sha256_json(dict(launch.environment)),
        "path_prepend_fingerprint": _sha256_json(
            [os.path.normcase(str(path)) for path in launch.path_prepend]
        ),
        "reasons": [item.value for item in reasons],
    }
    return _sha256_json(payload)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dedupe(values: Sequence[DegradedReason]) -> list[DegradedReason]:
    result: list[DegradedReason] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
