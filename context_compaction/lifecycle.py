"""Host-neutral compaction lifecycle, action journal, and validation gate."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable

from .budget import BudgetCategory, allocate_categories, estimate_tokens
from .models import (
    ActionRecord,
    ActionStatus,
    ActiveStateEnvelope,
    DegradedReason,
    GateState,
    HookDecision,
    HookEvent,
    Host,
    PilotConfig,
    SCHEMA_VERSION,
    SourceRead,
    StatePointer,
    ToolClass,
    Trigger,
)
from .repository import RepositoryError, RepositoryResolver, RepositoryState
from .storage import StateStore, StorageError

_NON_IDEMPOTENT = {ToolClass.LOCAL_WRITE, ToolClass.EXTERNAL_SIDE_EFFECT, ToolClass.UNKNOWN}
_INCOMPLETE_ACTIONS = {
    ActionStatus.PLANNED,
    ActionStatus.STARTED,
    ActionStatus.FAILED,
    ActionStatus.AWAITING_APPROVAL,
    ActionStatus.AMBIGUOUS,
}


class LifecycleCore:
    """Apply idempotent normalized lifecycle transitions to private state."""

    def __init__(
        self,
        config: PilotConfig,
        repository: RepositoryResolver,
        store: StateStore,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.config = config
        self.repository = repository
        self.store = store
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        self._memory_available = True

    def set_memory_available(self, available: bool) -> None:
        self._memory_available = bool(available)

    def handle_event(self, event: HookEvent) -> HookDecision:
        started_ns = time.perf_counter_ns()
        event_id = self._id_factory()
        correlation_available = bool(event.turn_id or event.tool_use_id)
        event_key = self._event_key(
            event,
            invocation_id=None if correlation_available else event_id,
        )
        try:
            existing = next(
                (
                    record
                    for record in self.store.read_events()
                    if record.get("event_key") == event_key
                ),
                None,
            )
        except (StorageError, OSError, ValueError):
            existing = None
        if existing is not None:
            return HookDecision(
                status="duplicate",
                event_id=str(existing["event_id"]),
                continue_=True,
                gate_state=self._current_gate(),
            )

        inactive = self._activation_reason(event)
        if inactive is not None:
            decision = HookDecision(
                status="inactive",
                event_id=event_id,
                continue_=True,
                gate_state=GateState.DEGRADED,
                degraded_reasons=(inactive,),
            )
            self._safe_record(
                event, event_id, event_key, decision, _elapsed_ms(started_ns)
            )
            return decision

        try:
            if event.event_name == "PreCompact":
                decision = self._pre_compact(event, event_id)
            elif event.event_name == "PostCompact":
                decision = HookDecision(
                    status="recorded",
                    event_id=event_id,
                    continue_=True,
                    gate_state=self._current_gate(),
                )
            elif event.event_name == "SessionStart":
                decision = self._session_start(event, event_id)
            elif event.event_name == "PreToolUse":
                decision = self._pre_tool_use(event, event_id)
            elif event.event_name == "PostToolUse":
                decision = self._post_tool_use(event, event_id)
            else:  # HookEvent validation makes this unreachable.
                decision = HookDecision(status="ignored", event_id=event_id)
        except (RepositoryError, StorageError, ValueError, OSError) as exc:
            reason = getattr(exc, "reason", DegradedReason.INTERNAL_ERROR)
            decision = HookDecision(
                status="degraded",
                event_id=event_id,
                continue_=event.event_name != "PreToolUse",
                stop_reason="validation_required" if event.event_name == "PreToolUse" else None,
                gate_state=GateState.DEGRADED,
                degraded_reasons=(reason,),
                system_message="Context pilot degraded; reconstruct from current source.",
            )
        self._safe_record(
            event, event_id, event_key, decision, _elapsed_ms(started_ns)
        )
        return decision

    def validate(
        self, event_id: str, *, evidence_paths: Iterable[str]
    ) -> HookDecision:
        current = self._read_current()
        validation_id = self._id_factory()
        if current is None:
            return HookDecision(
                status="degraded",
                event_id=validation_id,
                continue_=False,
                stop_reason="state_missing",
                gate_state=GateState.DEGRADED,
                degraded_reasons=(DegradedReason.STATE_MISSING,),
            )
        if current.event_id != event_id or current.recovery_epoch != event_id:
            return HookDecision(
                status="degraded",
                event_id=validation_id,
                continue_=False,
                stop_reason="state_stale",
                gate_state=GateState.DEGRADED,
                degraded_reasons=(DegradedReason.STATE_STALE,),
            )

        reasons: list[DegradedReason] = []
        try:
            rebuilt = self.repository.resolve()
        except RepositoryError as exc:
            rebuilt = None
            reasons.append(exc.reason)

        evidence = set(evidence_paths)
        reads = {
            item.relative_path: item
            for item in current.source_reads
            if item.recovery_epoch == current.recovery_epoch
        }
        if rebuilt is not None:
            if rebuilt.repository.fingerprint != current.repository.fingerprint:
                reasons.append(DegradedReason.ALLOWLIST_MISMATCH)
            for pointer in _unique_file_pointers(current.artifact_pointers):
                try:
                    now = self.repository.hash_relative_path(pointer.relative_path)
                except RepositoryError:
                    reasons.append(DegradedReason.ARTIFACT_MISSING)
                    continue
                if now != pointer.captured_hash:
                    reasons.append(DegradedReason.SOURCE_CHANGED)
                    continue
                read = reads.get(pointer.relative_path)
                if pointer.relative_path not in evidence or read is None or read.current_hash != now:
                    reason = (
                        DegradedReason.SCOPED_RULES_UNVALIDATED
                        if pointer.kind == "scoped_rule"
                        else DegradedReason.ARTIFACT_MISSING
                    )
                    reasons.append(reason)

        if current.approval_status == "pending":
            reasons.append(DegradedReason.APPROVAL_UNRESOLVED)
        if any(action.status is ActionStatus.AMBIGUOUS for action in current.actions):
            reasons.append(DegradedReason.ACTION_AMBIGUOUS)

        reasons = _dedupe_reasons(reasons)
        if reasons:
            refreshed = current
            if rebuilt is not None and DegradedReason.SOURCE_CHANGED in reasons:
                refreshed = replace(
                    current,
                    repository=rebuilt.repository,
                    artifact_pointers=self._combined_pointers(rebuilt),
                )
            refreshed = replace(
                refreshed,
                state=GateState.DEGRADED,
                degraded_reasons=tuple(reasons),
            )
            self.store.write_current(refreshed.to_dict())
            decision = HookDecision(
                status="degraded",
                event_id=validation_id,
                continue_=False,
                stop_reason="validation_failed",
                gate_state=GateState.DEGRADED,
                degraded_reasons=tuple(reasons),
            )
        else:
            validated = replace(
                current,
                state=GateState.VALIDATED,
                degraded_reasons=(),
                verification_status="source_validated",
            )
            self.store.write_current(validated.to_dict())
            decision = HookDecision(
                status="validated",
                event_id=validation_id,
                continue_=True,
                gate_state=GateState.VALIDATED,
            )
        self._record_validation(validation_id, event_id, decision)
        return decision

    def current_actions(self) -> tuple[ActionRecord, ...]:
        current = self._read_current()
        return current.actions if current else ()

    def diagnostics(self) -> list[dict[str, object]]:
        return self.store.read_events()

    def _pre_compact(self, event: HookEvent, event_id: str) -> HookDecision:
        previous = self._read_current()
        actions = previous.actions if previous else ()
        state = self.repository.resolve()
        degraded = (
            (state.task.degraded_reason,) if state.task.degraded_reason is not None else ()
        )
        gate = GateState.DEGRADED if degraded else GateState.CAPTURED
        envelope = ActiveStateEnvelope(
            event_id=event_id,
            session_fingerprint=self._session_fingerprint(event),
            host=event.host,
            host_version=event.host_version,
            trigger=event.trigger or Trigger.AUTO,
            created_at=self._clock(),
            repository=state.repository,
            task_slug=state.task.slug,
            goal_preview=state.task.goal_preview,
            phase=state.task.phase,
            artifact_pointers=self._combined_pointers(state),
            actions=_bounded_actions(actions),
            state=gate,
            degraded_reasons=degraded,
            approval_status=state.task.approval_status,
            verification_status=state.task.verification_status,
        )
        self.store.write_current(envelope.to_dict())
        return HookDecision(
            status="captured" if not degraded else "degraded",
            event_id=event_id,
            continue_=True,
            gate_state=gate,
            degraded_reasons=degraded,
        )

    def _session_start(self, event: HookEvent, event_id: str) -> HookDecision:
        if event.source != "compact":
            return HookDecision(
                status="ignored",
                event_id=event_id,
                continue_=True,
                gate_state=self._current_gate(),
            )
        current = self._read_current()
        if current is None:
            return self._missing_recovery(event, event_id)

        reasons: list[DegradedReason] = list(current.degraded_reasons)
        rebuilt = self.repository.resolve()
        if rebuilt.repository != current.repository:
            reasons.append(DegradedReason.SOURCE_CHANGED)
        actions = tuple(
            replace(action, status=ActionStatus.AMBIGUOUS)
            if action.status is ActionStatus.STARTED
            else action
            for action in current.actions
        )
        if any(action.status is ActionStatus.AMBIGUOUS for action in actions):
            reasons.append(DegradedReason.ACTION_AMBIGUOUS)
        reasons = _dedupe_reasons(reasons)
        gate = GateState.DEGRADED if reasons else GateState.VALIDATION_REQUIRED
        resumed = replace(
            current,
            event_id=event_id,
            host=event.host,
            host_version=event.host_version,
            repository=rebuilt.repository if DegradedReason.SOURCE_CHANGED in reasons else current.repository,
            artifact_pointers=(
                self._combined_pointers(rebuilt)
                if DegradedReason.SOURCE_CHANGED in reasons
                else current.artifact_pointers
            ),
            actions=_bounded_actions(actions),
            state=gate,
            degraded_reasons=tuple(reasons),
            recovery_epoch=event_id,
            source_reads=(),
        )
        context, included, omitted, truncated = self._serialize_reentry(resumed)
        resumed = replace(
            resumed,
            included_categories=included,
            omitted_categories=omitted,
            truncated=truncated,
        )
        self.store.write_current(resumed.to_dict())
        return HookDecision(
            status="degraded" if reasons else "validation_required",
            event_id=event_id,
            continue_=True,
            additional_context=context,
            gate_state=gate,
            degraded_reasons=tuple(reasons),
            system_message=(
                "Context recovered as pointers only; reopen current source before material work."
            ),
        )

    def _missing_recovery(self, event: HookEvent, event_id: str) -> HookDecision:
        state = self.repository.resolve()
        envelope = ActiveStateEnvelope(
            event_id=event_id,
            session_fingerprint=self._session_fingerprint(event),
            host=event.host,
            host_version=event.host_version,
            trigger=event.trigger or Trigger.AUTO,
            created_at=self._clock(),
            repository=state.repository,
            task_slug=state.task.slug,
            goal_preview=state.task.goal_preview,
            phase=state.task.phase,
            artifact_pointers=self._combined_pointers(state),
            actions=(),
            state=GateState.DEGRADED,
            degraded_reasons=(DegradedReason.STATE_MISSING,),
            approval_status=state.task.approval_status,
            verification_status=state.task.verification_status,
            recovery_epoch=event_id,
        )
        context, included, omitted, truncated = self._serialize_reentry(envelope)
        envelope = replace(
            envelope,
            included_categories=included,
            omitted_categories=omitted,
            truncated=truncated,
        )
        self.store.write_current(envelope.to_dict())
        return HookDecision(
            status="degraded",
            event_id=event_id,
            continue_=True,
            gate_state=GateState.DEGRADED,
            degraded_reasons=(DegradedReason.STATE_MISSING,),
            additional_context=context,
            system_message="Recovery state missing; reconstruct from current source.",
        )

    def _pre_tool_use(self, event: HookEvent, event_id: str) -> HookDecision:
        current = self._read_current()
        tool_class = event.tool_class or ToolClass.UNKNOWN
        fingerprint = event.input_fingerprint or hashlib.sha256(b"unmeasured").hexdigest()
        if current is not None and any(
            action.tool_class in _NON_IDEMPOTENT
            and action.status is ActionStatus.COMPLETED
            and action.input_fingerprint == fingerprint
            for action in current.actions
        ):
            return HookDecision(
                status="denied",
                event_id=event_id,
                continue_=False,
                stop_reason="completed_non_idempotent_action",
                gate_state=current.state,
            )
        if current is not None and current.state in {
            GateState.CAPTURED,
            GateState.VALIDATION_REQUIRED,
            GateState.DEGRADED,
        } and tool_class is not ToolClass.READ:
            return HookDecision(
                status="denied",
                event_id=event_id,
                continue_=False,
                stop_reason="validation_required",
                gate_state=current.state,
                degraded_reasons=current.degraded_reasons,
            )

        current = current or self._runtime_envelope(event, event_id)
        action_id = event.tool_use_id or event_id
        status = (
            ActionStatus.AWAITING_APPROVAL
            if event.status == "awaiting_approval"
            else ActionStatus.STARTED
        )
        action = ActionRecord(
            action_id=action_id,
            tool_class=tool_class,
            tool_name=event.tool_name or "unknown",
            input_fingerprint=fingerprint,
            status=status,
            started_at=self._clock(),
        )
        actions = [item for item in current.actions if item.action_id != action_id]
        actions.append(action)
        self.store.write_current(replace(current, actions=_bounded_actions(actions)).to_dict())
        return HookDecision(
            status="allowed",
            event_id=event_id,
            continue_=True,
            gate_state=current.state,
        )

    def _post_tool_use(self, event: HookEvent, event_id: str) -> HookDecision:
        current = self._read_current()
        if current is None:
            return HookDecision(status="recorded", event_id=event_id, continue_=True)
        action_id = event.tool_use_id or event_id
        status = {
            "completed": ActionStatus.COMPLETED,
            "failed": ActionStatus.FAILED,
            "ambiguous": ActionStatus.AMBIGUOUS,
            "awaiting_approval": ActionStatus.AWAITING_APPROVAL,
        }.get(event.status or "", ActionStatus.AMBIGUOUS)
        actions: list[ActionRecord] = []
        matched = False
        for action in current.actions:
            if action.action_id == action_id:
                matched = True
                actions.append(
                    replace(
                        action,
                        status=status,
                        finished_at=self._clock()
                        if status in {ActionStatus.COMPLETED, ActionStatus.FAILED}
                        else None,
                    )
                )
            else:
                actions.append(action)
        if not matched and event.input_fingerprint and event.tool_name:
            actions.append(
                ActionRecord(
                    action_id=action_id,
                    tool_class=event.tool_class or ToolClass.UNKNOWN,
                    tool_name=event.tool_name,
                    input_fingerprint=event.input_fingerprint,
                    status=status,
                    started_at=self._clock(),
                    finished_at=self._clock() if status is ActionStatus.COMPLETED else None,
                )
            )

        reads = list(current.source_reads)
        if (
            status is ActionStatus.COMPLETED
            and (event.tool_class or ToolClass.UNKNOWN) is ToolClass.READ
            and event.evidence_relative_path
            and current.recovery_epoch
        ):
            current_hash = self.repository.hash_relative_path(event.evidence_relative_path)
            reads = [
                item
                for item in reads
                if item.relative_path != event.evidence_relative_path
                or item.recovery_epoch != current.recovery_epoch
            ]
            reads.append(
                SourceRead(
                    event.evidence_relative_path,
                    current_hash,
                    current.recovery_epoch,
                )
            )
        updated = replace(
            current,
            actions=_bounded_actions(actions),
            source_reads=tuple(reads[-256:]),
        )
        self.store.write_current(updated.to_dict())
        return HookDecision(
            status="recorded",
            event_id=event_id,
            continue_=True,
            gate_state=updated.state,
        )

    def _runtime_envelope(self, event: HookEvent, event_id: str) -> ActiveStateEnvelope:
        state = self.repository.resolve()
        return ActiveStateEnvelope(
            event_id=event_id,
            session_fingerprint=self._session_fingerprint(event),
            host=event.host,
            host_version=event.host_version,
            trigger=event.trigger or Trigger.AUTO,
            created_at=self._clock(),
            repository=state.repository,
            task_slug=state.task.slug,
            goal_preview=state.task.goal_preview,
            phase=state.task.phase,
            artifact_pointers=self._combined_pointers(state),
            actions=(),
            state=GateState.VALIDATED,
            degraded_reasons=(),
            approval_status=state.task.approval_status,
            verification_status=state.task.verification_status,
        )

    def _serialize_reentry(
        self, envelope: ActiveStateEnvelope
    ) -> tuple[str, tuple[str, ...], tuple[str, ...], bool]:
        status = {
            "gate": envelope.state.value,
            "degraded": [item.value for item in envelope.degraded_reasons],
            "authority": "Pointers and memory are non-authoritative; reopen current source.",
        }
        task = {
            "task": envelope.task_slug,
            "goal": envelope.goal_preview,
            "phase": envelope.phase,
            "approval": envelope.approval_status,
        }
        actions = [item.to_dict() for item in envelope.actions if item.status in _INCOMPLETE_ACTIONS]
        repository = {
            "fingerprint": envelope.repository.fingerprint,
            "branch": envelope.repository.branch,
            "head": envelope.repository.head,
            "dirty": [item.to_dict() for item in envelope.repository.dirty_paths],
        }
        pointers = [
            {
                "kind": item.kind,
                "id": item.stable_id,
                "path": item.relative_path,
                "anchor": item.anchor,
                "hash": item.captured_hash,
            }
            for item in envelope.artifact_pointers
        ]
        categories = [
            BudgetCategory("lifecycle_status", _compact(status), 0, required=True),
            BudgetCategory("task_identity", _compact(task), 1, required=True),
            BudgetCategory("pending_actions", _compact(actions), 2, required=True),
            BudgetCategory("repository_state", _compact(repository), 3, required=True),
            BudgetCategory("artifact_pointers", _compact(pointers), 4),
        ]
        if self._memory_available:
            categories.append(BudgetCategory("memory_pointers", "[]", 5))
        result = allocate_categories(
            categories,
            max_chars=self.config.budgets.reentry_chars,
            max_tokens=self.config.budgets.reentry_estimated_tokens,
        )
        return (
            result.text,
            result.included_categories,
            result.omitted_categories,
            result.truncated,
        )

    def _combined_pointers(self, state: RepositoryState) -> tuple[StatePointer, ...]:
        values = [
            *state.artifact_pointers,
            *state.scoped_rule_pointers,
            *state.critical_pointers,
            *state.task.blocker_pointers,
        ]
        if state.task.active_plan_pointer is not None:
            values.append(state.task.active_plan_pointer)
        seen: set[tuple[str, str, str | None]] = set()
        result: list[StatePointer] = []
        for pointer in values:
            key = (pointer.kind, pointer.relative_path, pointer.anchor)
            if key not in seen:
                seen.add(key)
                result.append(pointer)
            if len(result) == 256:
                break
        return tuple(result)

    def _read_current(self) -> ActiveStateEnvelope | None:
        value = self.store.read_current()
        if value is None:
            return None
        try:
            return ActiveStateEnvelope.from_dict(value)
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageError(DegradedReason.STATE_MALFORMED, "invalid active state") from exc

    def _current_gate(self) -> GateState | None:
        try:
            current = self._read_current()
        except StorageError:
            return GateState.DEGRADED
        return current.state if current else None

    def _activation_reason(self, event: HookEvent) -> DegradedReason | None:
        if not self.config.enabled:
            return DegradedReason.INACTIVE_OR_UNTRUSTED_HOOK
        host = self.config.codex if event.host is Host.CODEX else self.config.claude
        if not host.enabled:
            return DegradedReason.INACTIVE_OR_UNTRUSTED_HOOK
        if event.host_version not in host.supported_versions:
            return DegradedReason.UNSUPPORTED_HOST_VERSION
        try:
            cwd = Path(event.cwd).resolve(strict=True)
        except OSError:
            return DegradedReason.ALLOWLIST_MISMATCH
        if not cwd.is_dir() or not cwd.is_relative_to(self.repository.root):
            return DegradedReason.ALLOWLIST_MISMATCH
        return None

    def _session_fingerprint(self, event: HookEvent) -> str:
        value = f"{event.host.value}\0{event.session_id or 'unknown'}\0{self.config.repository_fingerprint}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _event_key(self, event: HookEvent, *, invocation_id: str | None = None) -> str:
        fields = (
            event.host.value,
            self._session_fingerprint(event),
            event.event_name,
            event.turn_id or "",
            event.tool_use_id or "",
            event.trigger.value if event.trigger else "",
            event.source or "",
            event.status or "",
            event.input_fingerprint or "",
            invocation_id or "",
        )
        return hashlib.sha256("\0".join(fields).encode("utf-8")).hexdigest()

    def _record(
        self,
        event: HookEvent,
        event_id: str,
        event_key: str,
        decision: HookDecision,
        duration_ms: int,
    ) -> None:
        try:
            current = self._read_current()
        except (StorageError, OSError, ValueError):
            current = None
        reentry = decision.additional_context
        payload = {
            "schema_version": SCHEMA_VERSION,
            "event_id": event_id,
            "event_key": event_key,
            "host": event.host.value,
            "host_version": event.host_version,
            "event_name": event.event_name,
            "model_class": _model_class(event.model),
            "trigger": event.trigger.value if event.trigger else event.source or "unmeasured",
            "repository_fingerprint": self.config.repository_fingerprint,
            "outcome": decision.status,
            "gate_state": decision.gate_state.value if decision.gate_state else None,
            "degraded_reason_codes": [item.value for item in decision.degraded_reasons],
            "duration_ms": duration_ms,
            "event_bytes": event.event_bytes,
            "summary_chars": event.summary_chars,
            "reentry_chars": len(reentry) if reentry is not None else None,
            "estimated_tokens": estimate_tokens(reentry) if reentry is not None else None,
            "included_category_names": (
                list(current.included_categories) if current is not None else []
            ),
            "omitted_category_names": (
                list(current.omitted_categories) if current is not None else []
            ),
            "truncated": current.truncated if current is not None else False,
            "pre_usage": event.pre_usage,
            "post_usage": event.post_usage,
            "measurement_source": event.measurement_source,
        }
        self.store.append_event(payload, dedupe_key=event_key)

    def _safe_record(
        self,
        event: HookEvent,
        event_id: str,
        event_key: str,
        decision: HookDecision,
        duration_ms: int,
    ) -> None:
        try:
            self._record(event, event_id, event_key, decision, duration_ms)
        except (StorageError, OSError, ValueError):
            # Diagnostics are optional and must never turn hook recovery into failure.
            return

    def _record_validation(
        self, validation_id: str, recovery_id: str, decision: HookDecision
    ) -> None:
        event_key = hashlib.sha256(
            f"validate\0{recovery_id}\0{validation_id}".encode("utf-8")
        ).hexdigest()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "event_id": validation_id,
            "event_key": event_key,
            "host": "operator",
            "host_version": "local",
            "trigger": "validate",
            "repository_fingerprint": self.config.repository_fingerprint,
            "outcome": decision.status,
            "degraded_reason_codes": [item.value for item in decision.degraded_reasons],
            "measurement_source": "unmeasured",
        }
        self.store.append_event(payload, dedupe_key=event_key)


def _bounded_actions(actions: Iterable[ActionRecord]) -> tuple[ActionRecord, ...]:
    values = list(actions)
    unfinished = [item for item in values if item.status in _INCOMPLETE_ACTIONS]
    completed = [item for item in values if item.status is ActionStatus.COMPLETED]
    combined = unfinished[-64:] + completed[-20:]
    seen: set[str] = set()
    result: list[ActionRecord] = []
    for action in combined:
        if action.action_id in seen:
            continue
        seen.add(action.action_id)
        result.append(action)
    return tuple(result)


def _elapsed_ms(started_ns: int) -> int:
    return max(0, (time.perf_counter_ns() - started_ns + 999_999) // 1_000_000)


def _model_class(model: str | None) -> str:
    if model is None:
        return "unmeasured"
    normalized = model.casefold()
    if "claude" in normalized:
        return "anthropic"
    if any(marker in normalized for marker in ("gpt", "codex", "o1", "o3", "o4")):
        return "openai"
    return "other"


def _unique_file_pointers(
    pointers: Iterable[StatePointer],
) -> tuple[StatePointer, ...]:
    result: list[StatePointer] = []
    seen: set[str] = set()
    for pointer in pointers:
        if pointer.relative_path not in seen:
            seen.add(pointer.relative_path)
            result.append(pointer)
    return tuple(result)


def _dedupe_reasons(values: Iterable[DegradedReason]) -> list[DegradedReason]:
    result: list[DegradedReason] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
