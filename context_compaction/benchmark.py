"""Frozen-source preservation and token-savings benchmark harness."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Mapping, Sequence

from .models import DirtyPath, Host
from .repository import RepositoryResolver, canonical_repository_root, repository_fingerprint

FROZEN_EDUCODE_COMMIT = "0db30624dd32d814b937aa88b5ec84e18d4b130d"
MIN_ASSEMBLY_SAMPLES = 30
CONTINUATION_TURNS = 10
MAX_BENCHMARK_ARTIFACT_BYTES = 32_768
_MAX_MANIFEST_BYTES = 512 * 1024
_MAX_SOURCE_BYTES = 32 * 1024 * 1024
_EXPECTED_PROBE_IDS = tuple(f"P{index:02d}" for index in range(1, 15))
_EXPECTED_CRITICAL = {
    "P01",
    "P02",
    "P03",
    "P04",
    "P06",
    "P07",
    "P08",
    "P09",
    "P12",
    "P14",
}
_EXACT_CODE = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b")
_ABSOLUTE_PATH = re.compile(r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\]|(?<!:)//[^/])")
_SAFE_MODEL_CLASS = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")


class BenchmarkError(RuntimeError):
    pass


class ProbeDriftError(BenchmarkError):
    pass


class IsolationError(BenchmarkError):
    pass


@dataclass(frozen=True)
class AuthoritySpan:
    path: str
    blob_oid: str
    start_line: int
    end_line: int
    anchors: tuple[str, ...]


@dataclass(frozen=True)
class NegativeAssertion:
    pattern: str
    paths: tuple[str, ...]
    expected_match_count: int


@dataclass(frozen=True)
class Probe:
    probe_id: str
    critical: bool
    question: str
    expected_answer: str
    required_concepts: tuple[tuple[str, ...], ...]
    allowed_exact_codes: tuple[str, ...]
    contradiction_terms: tuple[str, ...]
    authorities: tuple[AuthoritySpan, ...]
    negative_assertion: NegativeAssertion | None


@dataclass(frozen=True)
class BenchmarkManifest:
    schema_version: int
    workload_name: str
    frozen_commit: str
    probes: tuple[Probe, ...]
    manifest_sha256: str


@dataclass(frozen=True)
class SourceValidation:
    commit: str
    manifest_sha256: str
    validated_probe_ids: tuple[str, ...]
    source_object_count: int
    authority_span_count: int
    negative_match_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "commit": self.commit,
            "manifest_sha256": self.manifest_sha256,
            "validated_probe_ids": list(self.validated_probe_ids),
            "source_object_count": self.source_object_count,
            "authority_span_count": self.authority_span_count,
            "negative_match_count": self.negative_match_count,
        }


@dataclass(frozen=True)
class PreservationScore:
    critical_accuracy: float
    overall_accuracy: float
    false_exact_code_claims: int
    stale_contradictions: int
    dirty_path_fidelity: bool
    approval_retained: bool
    action_replay_safe: bool
    passed_probe_ids: tuple[str, ...]
    failed_probe_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "critical_accuracy": self.critical_accuracy,
            "overall_accuracy": self.overall_accuracy,
            "false_exact_code_claims": self.false_exact_code_claims,
            "stale_contradictions": self.stale_contradictions,
            "dirty_path_fidelity": self.dirty_path_fidelity,
            "approval_retained": self.approval_retained,
            "action_replay_safe": self.action_replay_safe,
            "passed_probe_ids": list(self.passed_probe_ids),
            "failed_probe_ids": list(self.failed_probe_ids),
        }


@dataclass(frozen=True)
class SavingsMeasurement:
    qualification: str
    measurement_source: str
    fixed_prefix_tokens: int | None
    eligible_before_tokens: int | None
    eligible_after_tokens: int | None
    reentry_tokens: int | None
    eligible_body_reduction_percent: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "qualification": self.qualification,
            "measurement_source": self.measurement_source,
            "fixed_prefix_tokens": self.fixed_prefix_tokens,
            "eligible_before_tokens": self.eligible_before_tokens,
            "eligible_after_tokens": self.eligible_after_tokens,
            "reentry_tokens": self.reentry_tokens,
            "eligible_body_reduction_percent": self.eligible_body_reduction_percent,
        }


@dataclass(frozen=True)
class AssemblyMeasurement:
    sample_count: int
    p50_ms: float
    p95_ms: float
    max_ms: float

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "max_ms": self.max_ms,
        }


@dataclass(frozen=True)
class ThrashAssessment:
    continuation_turns: int
    observed_compaction_count: int
    explained_compaction_count: int
    unexplained_compaction_count: int
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "continuation_turns": self.continuation_turns,
            "observed_compaction_count": self.observed_compaction_count,
            "explained_compaction_count": self.explained_compaction_count,
            "unexplained_compaction_count": self.unexplained_compaction_count,
            "passed": self.passed,
        }


class ScenarioMode(str, Enum):
    UNCOMPACTED = "uncompacted"
    MANUAL_COMPACT = "manual_compact"
    AUTOMATIC_COMPACT = "automatic_compact"
    MIDTURN = "midturn"


class FaultCase(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    STALE = "stale"
    MALFORMED = "malformed"
    OVERSIZED = "oversized"
    MEMORY_OFFLINE = "memory_offline"
    ACTION_AMBIGUOUS = "action_ambiguous"
    ROLLBACK = "rollback"


REPRESENTATIVE_STATES = tuple(item.value for item in FaultCase)


@dataclass(frozen=True)
class HostModelConfig:
    host: Host
    host_version: str
    model_class: str

    def __post_init__(self) -> None:
        if not isinstance(self.host, Host):
            raise ValueError("invalid benchmark host")
        if not self.host_version or len(self.host_version) > 64:
            raise ValueError("invalid host version")
        if not _SAFE_MODEL_CLASS.fullmatch(self.model_class):
            raise ValueError("invalid model class")


@dataclass(frozen=True)
class ScenarioCase:
    case_id: str
    host: Host
    host_version: str
    model_class: str
    mode: ScenarioMode
    fault: FaultCase
    continuation_turns: int = CONTINUATION_TURNS


@dataclass(frozen=True)
class ScenarioObservation:
    case_id: str
    answers: Mapping[str, str]
    compaction_turns: tuple[int, ...]
    continuation_turns: int
    declared_oversized_turns: tuple[int, ...] = ()
    pre_total_tokens: int | None = None
    post_total_tokens: int | None = None
    fixed_prefix_tokens: int | None = None
    reentry_tokens: int | None = None
    measurement_source: str | None = None
    pre_body_chars: int | None = None
    post_body_chars: int | None = None
    fixed_prefix_chars: int | None = None
    reentry_chars: int | None = None


@dataclass(frozen=True)
class ScenarioResult:
    case: ScenarioCase
    preservation: PreservationScore
    savings: SavingsMeasurement
    thrashing: ThrashAssessment

    def to_dict(self) -> dict[str, object]:
        value = {
            "case": {
                "case_id": self.case.case_id,
                "host": self.case.host.value,
                "host_version": self.case.host_version,
                "model_class": self.case.model_class,
                "mode": self.case.mode.value,
                "fault": self.case.fault.value,
                "continuation_turns": self.case.continuation_turns,
            },
            "preservation": self.preservation.to_dict(),
            "savings": self.savings.to_dict(),
            "thrashing": self.thrashing.to_dict(),
        }
        _validate_content_free_artifact(value)
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(encoded) > MAX_BENCHMARK_ARTIFACT_BYTES:
            raise BenchmarkError("benchmark artifact exceeds its bound")
        return value


class BenchmarkScenarioDriver:
    """Run one reproducible case while retaining only aggregate evidence."""

    def __init__(
        self, manifest: BenchmarkManifest, validation: SourceValidation
    ) -> None:
        self.manifest = manifest
        self.validation = validation

    def run(
        self,
        case: ScenarioCase,
        executor: Callable[[ScenarioCase], ScenarioObservation],
    ) -> ScenarioResult:
        observation = executor(case)
        if observation.case_id != case.case_id:
            raise BenchmarkError("scenario observation identity mismatch")
        if observation.continuation_turns != case.continuation_turns:
            raise BenchmarkError("scenario continuation-turn count mismatch")
        preservation = score_answers(
            self.manifest, observation.answers, self.validation
        )
        savings = measure_savings(
            pre_total_tokens=observation.pre_total_tokens,
            post_total_tokens=observation.post_total_tokens,
            fixed_prefix_tokens=observation.fixed_prefix_tokens,
            reentry_tokens=observation.reentry_tokens,
            measurement_source=observation.measurement_source,
            pre_body_chars=observation.pre_body_chars,
            post_body_chars=observation.post_body_chars,
            fixed_prefix_chars=observation.fixed_prefix_chars,
            reentry_chars=observation.reentry_chars,
        )
        thrashing = assess_thrashing(
            observation.compaction_turns,
            continuation_turns=observation.continuation_turns,
            declared_oversized_turns=observation.declared_oversized_turns,
        )
        result = ScenarioResult(case, preservation, savings, thrashing)
        result.to_dict()
        return result


def load_manifest(path: str | Path) -> BenchmarkManifest:
    target = Path(path).resolve(strict=True)
    if not target.is_file() or target.stat().st_size > _MAX_MANIFEST_BYTES:
        raise BenchmarkError("benchmark manifest is missing or oversized")
    try:
        raw = target.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError("benchmark manifest cannot be decoded") from exc
    _require_keys(value, {"schema_version", "workload", "probes"}, "manifest")
    if value["schema_version"] != 1:
        raise BenchmarkError("unsupported benchmark manifest schema")
    workload = value["workload"]
    _require_keys(workload, {"name", "frozen_commit"}, "workload")
    if workload["frozen_commit"] != FROZEN_EDUCODE_COMMIT:
        raise BenchmarkError("benchmark commit is not the approved frozen commit")
    probes_value = value["probes"]
    if not isinstance(probes_value, list):
        raise BenchmarkError("benchmark probes must be a list")
    probes = tuple(_parse_probe(item) for item in probes_value)
    identifiers = tuple(item.probe_id for item in probes)
    if identifiers != _EXPECTED_PROBE_IDS:
        raise BenchmarkError("benchmark probe identities or order drifted")
    critical = {item.probe_id for item in probes if item.critical}
    if critical != _EXPECTED_CRITICAL:
        raise BenchmarkError("benchmark critical-probe set drifted")
    name = _bounded_text(workload["name"], "workload name", 256)
    return BenchmarkManifest(
        schema_version=1,
        workload_name=name,
        frozen_commit=FROZEN_EDUCODE_COMMIT,
        probes=probes,
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
    )


def validate_manifest_source(
    manifest: BenchmarkManifest, repository: str | Path
) -> SourceValidation:
    root = canonical_repository_root(repository)
    commit = _git(root, "rev-parse", "HEAD").strip()
    if commit != manifest.frozen_commit:
        raise ProbeDriftError("benchmark checkout is not at the frozen commit")
    objects: dict[str, str] = {}
    validated: list[str] = []
    span_count = 0
    negative_matches = 0
    for probe in manifest.probes:
        for authority in probe.authorities:
            target = _safe_relative(root, authority.path)
            if not target.is_file() or target.stat().st_size > _MAX_SOURCE_BYTES:
                raise ProbeDriftError("benchmark authority is missing or oversized")
            oid = _git(root, "hash-object", "--", authority.path).strip()
            if oid != authority.blob_oid:
                raise ProbeDriftError(
                    f"source object drift for {probe.probe_id}"
                )
            previous = objects.setdefault(authority.path, oid)
            if previous != oid:
                raise ProbeDriftError("inconsistent authority object identity")
            try:
                lines = target.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as exc:
                raise ProbeDriftError("benchmark authority cannot be decoded") from exc
            if authority.end_line > len(lines):
                raise ProbeDriftError("authority span exceeds source")
            span = "\n".join(lines[authority.start_line - 1 : authority.end_line])
            if any(anchor not in span for anchor in authority.anchors):
                raise ProbeDriftError(f"authority anchor drift for {probe.probe_id}")
            span_count += 1
        if probe.negative_assertion is not None:
            assertion = probe.negative_assertion
            result = _git_result(
                root,
                "grep",
                "-n",
                "-E",
                "--",
                assertion.pattern,
                "--",
                *assertion.paths,
            )
            if result.returncode not in {0, 1}:
                raise ProbeDriftError("negative authority query failed")
            matches = len([line for line in result.stdout.splitlines() if line])
            negative_matches += matches
            if matches != assertion.expected_match_count:
                raise ProbeDriftError(f"negative authority drift for {probe.probe_id}")
        validated.append(probe.probe_id)
    return SourceValidation(
        commit=commit,
        manifest_sha256=manifest.manifest_sha256,
        validated_probe_ids=tuple(validated),
        source_object_count=len(objects),
        authority_span_count=span_count,
        negative_match_count=negative_matches,
    )


@contextmanager
def isolated_worktree(
    source_repository: str | Path,
    commit: str = FROZEN_EDUCODE_COMMIT,
) -> Iterator[Path]:
    source = canonical_repository_root(source_repository)
    before_head = _git(source, "rev-parse", "HEAD").strip()
    before_status = _git(source, "status", "--porcelain=v1", "-z")
    if before_head != commit:
        raise IsolationError("active benchmark checkout is not at the frozen commit")
    if before_status:
        raise IsolationError("active benchmark checkout is not clean")
    # Keep the disposable sibling path short on Windows: this repository has
    # tracked paths near MAX_PATH, while the normal user temp root is long.
    temp_root = source.parent.resolve(strict=True)
    parent = Path(tempfile.mkdtemp(prefix=".cpb-", dir=temp_root)).resolve(strict=True)
    if not parent.is_relative_to(temp_root) or parent == temp_root:
        raise IsolationError("temporary benchmark root is unsafe")
    target = parent / "w"
    added = False
    cleanup_error: str | None = None
    try:
        result = _git_result(source, "worktree", "add", "--detach", str(target), commit)
        if result.returncode != 0:
            raise IsolationError("isolated benchmark worktree creation failed")
        added = True
        yield target.resolve(strict=True)
    finally:
        if added:
            result = _git_result(source, "worktree", "remove", "--force", str(target))
            if result.returncode != 0:
                cleanup_error = "isolated benchmark worktree cleanup failed"
        if parent.exists():
            resolved_parent = parent.resolve(strict=True)
            if resolved_parent.is_relative_to(temp_root) and resolved_parent != temp_root:
                shutil.rmtree(resolved_parent)
            else:
                cleanup_error = cleanup_error or "temporary benchmark cleanup refused"
        after_head = _git(source, "rev-parse", "HEAD").strip()
        after_status = _git(source, "status", "--porcelain=v1", "-z")
        if (after_head, after_status) != (before_head, before_status):
            raise IsolationError("active benchmark checkout changed")
        if cleanup_error is not None:
            raise IsolationError(cleanup_error)


def prepare_p14_dirty_state(repository: str | Path) -> tuple[DirtyPath, ...]:
    root = canonical_repository_root(repository)
    tracked = _git_result(root, "ls-files", "--error-unmatch", "--", "CONTEXT.md")
    if tracked.returncode != 0:
        raise IsolationError("P14 tracked marker target is unavailable")
    context = _safe_relative(root, "CONTEXT.md")
    with context.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("\n<!-- context-pilot-p14-marker -->\n")
    untracked = _safe_relative(root, "context-pilot-dirty/queued-change.ts")
    untracked.parent.mkdir(parents=True, exist_ok=False)
    untracked.write_text("export const queuedChange = true;\n", encoding="utf-8")
    snapshot = RepositoryResolver(
        root,
        allowed_fingerprint=repository_fingerprint(root),
        explicit_task_slug="agentic-development-workbench",
    ).resolve().repository
    expected = {
        ("CONTEXT.md", ".M"),
        ("context-pilot-dirty/queued-change.ts", "??"),
    }
    observed = {(item.path, item.status) for item in snapshot.dirty_paths}
    if observed != expected:
        raise IsolationError("P14 dirty-state fixture drifted")
    return snapshot.dirty_paths


def score_answers(
    manifest: BenchmarkManifest,
    answers: Mapping[str, str],
    validation: SourceValidation,
) -> PreservationScore:
    if validation.manifest_sha256 != manifest.manifest_sha256:
        raise BenchmarkError("source validation belongs to another manifest")
    if validation.commit != manifest.frozen_commit:
        raise BenchmarkError("source validation belongs to another commit")
    if validation.validated_probe_ids != tuple(item.probe_id for item in manifest.probes):
        raise BenchmarkError("not every probe is source validated")
    if set(answers) != set(_EXPECTED_PROBE_IDS):
        raise BenchmarkError("answers must cover exactly P01-P14")
    passed: list[str] = []
    failed: list[str] = []
    false_codes = 0
    contradictions = 0
    dirty_fidelity = False
    for probe in manifest.probes:
        answer = answers[probe.probe_id]
        if not isinstance(answer, str) or len(answer) > 64_000 or "\x00" in answer:
            raise BenchmarkError("invalid benchmark answer")
        normalized = _normalize(answer)
        concepts_pass = all(
            any(_normalize(term) in normalized for term in alternatives)
            for alternatives in probe.required_concepts
        )
        probe_contradictions = sum(
            _normalize(term) in normalized for term in probe.contradiction_terms
        )
        claimed_codes = set(_EXACT_CODE.findall(answer))
        probe_false_codes = claimed_codes - set(probe.allowed_exact_codes)
        false_codes += len(probe_false_codes)
        contradictions += probe_contradictions
        fidelity = True
        if probe.probe_id == "P14":
            fidelity = _dirty_path_fidelity(answer)
            dirty_fidelity = fidelity
        if concepts_pass and not probe_contradictions and not probe_false_codes and fidelity:
            passed.append(probe.probe_id)
        else:
            failed.append(probe.probe_id)
    critical_passed = sum(item in passed for item in _EXPECTED_CRITICAL)
    return PreservationScore(
        critical_accuracy=round(critical_passed / len(_EXPECTED_CRITICAL), 6),
        overall_accuracy=round(len(passed) / len(manifest.probes), 6),
        false_exact_code_claims=false_codes,
        stale_contradictions=contradictions,
        dirty_path_fidelity=dirty_fidelity,
        approval_retained="P02" in passed,
        action_replay_safe=all(item in passed for item in ("P07", "P08", "P12")),
        passed_probe_ids=tuple(passed),
        failed_probe_ids=tuple(failed),
    )


def measure_savings(
    *,
    pre_total_tokens: int | None = None,
    post_total_tokens: int | None = None,
    fixed_prefix_tokens: int | None = None,
    reentry_tokens: int | None = None,
    measurement_source: str | None = None,
    pre_body_chars: int | None = None,
    post_body_chars: int | None = None,
    fixed_prefix_chars: int | None = None,
    reentry_chars: int | None = None,
) -> SavingsMeasurement:
    token_values = (
        pre_total_tokens,
        post_total_tokens,
        fixed_prefix_tokens,
        reentry_tokens,
    )
    if all(value is not None for value in token_values) and measurement_source:
        pre, post, prefix, reentry = (_metric(item, "token metric") for item in token_values)
        if not measurement_source.startswith("host_"):
            raise BenchmarkError("token evidence source is not a credible host surface")
        before = max(0, pre - prefix)
        # Host post-total evidence already includes the re-entry payload. Keep
        # re-entry visible as a diagnostic; never count it twice.
        after = max(0, post - prefix)
        return _savings("confirmed", measurement_source, prefix, before, after, reentry)
    char_values = (pre_body_chars, post_body_chars, fixed_prefix_chars, reentry_chars)
    if all(value is not None for value in char_values):
        pre_chars, post_chars, prefix_chars, reentry_chars_value = (
            _metric(item, "character metric") for item in char_values
        )
        before = math.ceil(pre_chars / 4)
        reentry = math.ceil(reentry_chars_value / 4)
        after = math.ceil(post_chars / 4) + reentry
        prefix = math.ceil(prefix_chars / 4)
        return _savings(
            "qualified",
            "qualified_local_character_proxy",
            prefix,
            before,
            after,
            reentry,
        )
    return SavingsMeasurement(
        "unmeasured", "unmeasured", None, None, None, None, None
    )


def measure_assembly(
    assembler: Callable[[], object], *, samples: int = MIN_ASSEMBLY_SAMPLES
) -> AssemblyMeasurement:
    if samples < MIN_ASSEMBLY_SAMPLES or samples > 10_000:
        raise BenchmarkError("assembly sample count is outside the benchmark contract")
    for _ in range(3):
        assembler()
    durations: list[float] = []
    for _ in range(samples):
        started = time.perf_counter_ns()
        assembler()
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
    ordered = sorted(durations)
    return AssemblyMeasurement(
        sample_count=samples,
        p50_ms=round(_nearest_rank(ordered, 0.50), 6),
        p95_ms=round(_nearest_rank(ordered, 0.95), 6),
        max_ms=round(ordered[-1], 6),
    )


def measure_representative_states(
    assemblers: Mapping[str, Callable[[], object]],
    *,
    samples: int = MIN_ASSEMBLY_SAMPLES,
) -> dict[str, AssemblyMeasurement]:
    if set(assemblers) != set(REPRESENTATIVE_STATES):
        raise BenchmarkError("representative-state assembly set is incomplete")
    return {
        state: measure_assembly(assemblers[state], samples=samples)
        for state in REPRESENTATIVE_STATES
    }


def assess_thrashing(
    compaction_turns: Sequence[int],
    *,
    continuation_turns: int = CONTINUATION_TURNS,
    declared_oversized_turns: Sequence[int] = (),
) -> ThrashAssessment:
    if continuation_turns != CONTINUATION_TURNS:
        raise BenchmarkError("thrash gate requires exactly ten continuation turns")
    observed = tuple(compaction_turns)
    declared = set(declared_oversized_turns)
    if any(
        not isinstance(turn, int) or isinstance(turn, bool) or not 1 <= turn <= continuation_turns
        for turn in (*observed, *declared)
    ):
        raise BenchmarkError("invalid compaction turn")
    explained = sum(turn in declared for turn in observed)
    unexplained = len(observed) - explained
    return ThrashAssessment(
        continuation_turns,
        len(observed),
        explained,
        unexplained,
        unexplained == 0,
    )


def build_scenario_matrix(
    configurations: Sequence[HostModelConfig],
) -> tuple[ScenarioCase, ...]:
    if not configurations:
        raise BenchmarkError("at least one host/model configuration is required")
    cases: list[ScenarioCase] = []
    for configuration in configurations:
        for mode in ScenarioMode:
            for fault in FaultCase:
                case_id = ":".join(
                    (
                        configuration.host.value,
                        configuration.host_version,
                        configuration.model_class,
                        mode.value,
                        fault.value,
                    )
                )
                cases.append(
                    ScenarioCase(
                        case_id,
                        configuration.host,
                        configuration.host_version,
                        configuration.model_class,
                        mode,
                        fault,
                    )
                )
    return tuple(cases)


def _parse_probe(value: object) -> Probe:
    keys = {
        "id",
        "critical",
        "question",
        "expected_answer",
        "required_concepts",
        "allowed_exact_codes",
        "contradiction_terms",
        "authorities",
        "negative_assertion",
    }
    _require_keys(value, keys, "probe")
    probe_id = _bounded_text(value["id"], "probe id", 8)
    if not isinstance(value["critical"], bool):
        raise BenchmarkError("probe critical flag must be boolean")
    concepts_value = value["required_concepts"]
    if not isinstance(concepts_value, list) or not concepts_value:
        raise BenchmarkError("probe concepts must be a non-empty list")
    concepts: list[tuple[str, ...]] = []
    for alternatives in concepts_value:
        if not isinstance(alternatives, list) or not alternatives:
            raise BenchmarkError("probe concept alternatives must be non-empty")
        concepts.append(
            tuple(_bounded_text(item, "probe concept", 512) for item in alternatives)
        )
    authorities_value = value["authorities"]
    if not isinstance(authorities_value, list):
        raise BenchmarkError("probe authorities must be a list")
    authorities = tuple(_parse_authority(item) for item in authorities_value)
    negative = (
        _parse_negative(value["negative_assertion"])
        if value["negative_assertion"] is not None
        else None
    )
    if not authorities and negative is None:
        raise BenchmarkError("probe has no source authority")
    return Probe(
        probe_id=probe_id,
        critical=value["critical"],
        question=_bounded_text(value["question"], "probe question", 4_000),
        expected_answer=_bounded_text(
            value["expected_answer"], "expected answer", 8_000
        ),
        required_concepts=tuple(concepts),
        allowed_exact_codes=_text_tuple(
            value["allowed_exact_codes"], "allowed exact code", 256
        ),
        contradiction_terms=_text_tuple(
            value["contradiction_terms"], "contradiction term", 512
        ),
        authorities=authorities,
        negative_assertion=negative,
    )


def _parse_authority(value: object) -> AuthoritySpan:
    _require_keys(
        value,
        {"path", "blob_oid", "start_line", "end_line", "anchors"},
        "authority",
    )
    path = _relative_path(value["path"])
    oid = _bounded_text(value["blob_oid"], "blob oid", 64)
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid):
        raise BenchmarkError("invalid authority blob oid")
    start = value["start_line"]
    end = value["end_line"]
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start <= 0
        or end < start
        or end - start > 2_000
    ):
        raise BenchmarkError("invalid authority span")
    anchors = _text_tuple(value["anchors"], "authority anchor", 2_000)
    if not anchors:
        raise BenchmarkError("authority span has no anchor")
    return AuthoritySpan(path, oid, start, end, anchors)


def _parse_negative(value: object) -> NegativeAssertion:
    _require_keys(value, {"pattern", "paths", "expected_match_count"}, "negative assertion")
    pattern = _bounded_text(value["pattern"], "negative pattern", 1_000)
    try:
        re.compile(pattern)
    except re.error as exc:
        raise BenchmarkError("invalid negative assertion regex") from exc
    paths_value = value["paths"]
    if not isinstance(paths_value, list) or not paths_value:
        raise BenchmarkError("negative assertion paths are missing")
    paths = tuple(_relative_path(item) for item in paths_value)
    count = value["expected_match_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise BenchmarkError("invalid negative assertion count")
    return NegativeAssertion(pattern, paths, count)


def _savings(
    qualification: str,
    source: str,
    prefix: int,
    before: int,
    after: int,
    reentry: int,
) -> SavingsMeasurement:
    reduction = None if before == 0 else round((before - after) * 100 / before, 3)
    return SavingsMeasurement(
        qualification, source, prefix, before, after, reentry, reduction
    )


def _nearest_rank(values: Sequence[float], percentile: float) -> float:
    return values[max(0, math.ceil(percentile * len(values)) - 1)]


def _dirty_path_fidelity(answer: str) -> bool:
    normalized = _normalize(answer)
    required = (
        "context.md",
        "modified",
        "context-pilot-dirty/queued-change.ts",
        "untracked",
    )
    return (
        all(item in normalized for item in required)
        and not _ABSOLUTE_PATH.search(answer)
        and "diff --git" not in normalized
        and "@@" not in answer
    )


def _validate_content_free_artifact(value: object) -> None:
    forbidden = {
        "answer",
        "answers",
        "expected_answer",
        "question",
        "source_body",
        "summary",
        "tool_output",
        "diff",
        "path",
        "repository_root",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in forbidden:
                raise BenchmarkError("sensitive benchmark artifact category")
            _validate_content_free_artifact(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_content_free_artifact(item)
    elif isinstance(value, str):
        if "\x00" in value or _ABSOLUTE_PATH.search(value):
            raise BenchmarkError("unsafe benchmark artifact text")


def _safe_relative(root: Path, relative: str) -> Path:
    path = (root / Path(*relative.split("/"))).resolve(strict=False)
    if not path.is_relative_to(root):
        raise BenchmarkError("benchmark path escapes repository")
    return path


def _relative_path(value: object) -> str:
    text = _bounded_text(value, "relative path", 32_768).replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BenchmarkError("unsafe benchmark relative path")
    return path.as_posix()


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _text_tuple(value: object, name: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise BenchmarkError(f"{name} values must be a list")
    return tuple(_bounded_text(item, name, maximum) for item in value)


def _bounded_text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise BenchmarkError(f"invalid {name}")
    return value


def _require_keys(value: object, keys: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise BenchmarkError(f"invalid {name} fields")


def _metric(value: int | None, name: str) -> int:
    if (
        value is None
        or not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value > 10**12
    ):
        raise BenchmarkError(f"invalid {name}")
    return value


def _git(root: Path, *arguments: str) -> str:
    result = _git_result(root, *arguments)
    if result.returncode != 0:
        raise BenchmarkError("Git benchmark operation failed")
    return result.stdout


def _git_result(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        check=False,
        timeout=60,
    )
