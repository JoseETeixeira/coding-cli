"""Source-validated preservation, savings, and anti-thrashing benchmark contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from context_compaction.benchmark import (
    CONTINUATION_TURNS,
    FROZEN_EDUCODE_COMMIT,
    MIN_ASSEMBLY_SAMPLES,
    BenchmarkScenarioDriver,
    FaultCase,
    HostModelConfig,
    ProbeDriftError,
    ScenarioMode,
    ScenarioObservation,
    assess_thrashing,
    build_scenario_matrix,
    isolated_worktree,
    load_manifest,
    measure_assembly,
    measure_representative_states,
    measure_savings,
    prepare_p14_dirty_state,
    score_answers,
    validate_manifest_source,
)
from context_compaction.models import Host

ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "benchmarks" / "context_compaction" / "educode-probes.v1.json"
CRITICAL = {"P01", "P02", "P03", "P04", "P06", "P07", "P08", "P09", "P12", "P14"}


def _educode() -> Path:
    configured = os.environ.get("EDUCODE_BENCHMARK_REPO")
    candidate = Path(configured) if configured else Path.home() / "source" / "educode"
    if not (candidate / ".git").exists():
        pytest.skip("frozen educode checkout is unavailable")
    return candidate.resolve()


def test_manifest_machine_encodes_all_frozen_source_backed_probes():
    manifest = load_manifest(MANIFEST)

    assert manifest.schema_version == 1
    assert manifest.frozen_commit == FROZEN_EDUCODE_COMMIT
    assert [probe.probe_id for probe in manifest.probes] == [
        f"P{index:02d}" for index in range(1, 15)
    ]
    assert {probe.probe_id for probe in manifest.probes if probe.critical} == CRITICAL
    assert all(probe.question and probe.expected_answer for probe in manifest.probes)
    assert all(probe.authorities or probe.negative_assertion for probe in manifest.probes)


def test_frozen_manifest_validates_exact_git_objects_and_spans():
    report = validate_manifest_source(load_manifest(MANIFEST), _educode())

    assert report.commit == FROZEN_EDUCODE_COMMIT
    assert report.validated_probe_ids == tuple(f"P{index:02d}" for index in range(1, 15))
    assert report.negative_match_count == 0
    assert report.source_object_count >= 12


def test_isolated_worktree_contains_p14_dirtiness_only_and_active_stays_clean():
    source = _educode()
    before_head = _git(source, "rev-parse", "HEAD")
    before_status = _git(source, "status", "--porcelain=v1", "-z")

    with isolated_worktree(source, FROZEN_EDUCODE_COMMIT) as isolated:
        validate_manifest_source(load_manifest(MANIFEST), isolated)
        dirty = prepare_p14_dirty_state(isolated)
        assert {(item.path, item.status) for item in dirty} == {
            ("CONTEXT.md", ".M"),
            ("context-pilot-dirty/queued-change.ts", "??"),
        }
        assert isolated != source

    assert _git(source, "rev-parse", "HEAD") == before_head
    assert _git(source, "status", "--porcelain=v1", "-z") == before_status == ""


def test_source_drift_is_refused_inside_disposable_worktree():
    source = _educode()
    with isolated_worktree(source, FROZEN_EDUCODE_COMMIT) as isolated:
        target = isolated / "src" / "vs" / "platform" / "agenticRuntime" / "common" / "executionTarget.ts"
        target.write_text(target.read_text(encoding="utf-8") + "\n// benchmark drift\n", encoding="utf-8")
        with pytest.raises(ProbeDriftError, match="source object drift"):
            validate_manifest_source(load_manifest(MANIFEST), isolated)


def test_source_validated_scoring_is_content_free_and_detects_false_exact_claims():
    manifest = load_manifest(MANIFEST)
    validation = validate_manifest_source(manifest, _educode())
    answers = {probe.probe_id: probe.expected_answer for probe in manifest.probes}

    green = score_answers(manifest, answers, validation)
    assert green.critical_accuracy == 1.0
    assert green.overall_accuracy == 1.0
    assert green.false_exact_code_claims == 0
    assert green.stale_contradictions == 0
    assert green.dirty_path_fidelity is True
    assert green.approval_retained is True
    assert green.action_replay_safe is True
    serialized = json.dumps(green.to_dict(), sort_keys=True)
    assert "expected_answer" not in serialized
    assert "src/vs/" not in serialized

    answers["P08"] = answers["P08"] + " Invented exact code RUNTIME_COMMAND_RETRY_OK."
    red = score_answers(manifest, answers, validation)
    assert red.false_exact_code_claims == 1
    assert "P08" in red.failed_probe_ids


def test_savings_uses_observed_host_tokens_or_named_qualified_proxy():
    observed = measure_savings(
        pre_total_tokens=100_000,
        post_total_tokens=35_000,
        fixed_prefix_tokens=20_000,
        reentry_tokens=2_000,
        measurement_source="host_hook",
    )
    assert observed.qualification == "confirmed"
    assert observed.measurement_source == "host_hook"
    assert observed.fixed_prefix_tokens == 20_000
    assert observed.eligible_after_tokens == 15_000
    assert observed.reentry_tokens == 2_000
    assert observed.eligible_body_reduction_percent >= 50

    proxy = measure_savings(
        pre_body_chars=80_000,
        post_body_chars=20_000,
        reentry_chars=4_000,
        fixed_prefix_chars=12_000,
    )
    assert proxy.qualification == "qualified"
    assert proxy.measurement_source == "qualified_local_character_proxy"

    unmeasured = measure_savings()
    assert unmeasured.qualification == "unmeasured"
    assert unmeasured.eligible_body_reduction_percent is None


def test_latency_sampling_and_ten_turn_thrash_gate_are_explicit():
    measurement = measure_assembly(lambda: "bounded re-entry", samples=MIN_ASSEMBLY_SAMPLES)
    assert measurement.sample_count == 30
    assert measurement.p50_ms <= measurement.p95_ms <= measurement.max_ms
    assert measurement.p95_ms <= 2_000
    representative = measure_representative_states(
        {
            fault.value: (lambda value=fault.value: f"bounded:{value}")
            for fault in FaultCase
        }
    )
    assert set(representative) == {fault.value for fault in FaultCase}
    assert all(item.sample_count == 30 for item in representative.values())

    stable = assess_thrashing((), continuation_turns=CONTINUATION_TURNS)
    assert stable.passed is True
    assert stable.unexplained_compaction_count == 0
    red = assess_thrashing((4,), continuation_turns=CONTINUATION_TURNS)
    assert red.passed is False
    explained = assess_thrashing(
        (4,), continuation_turns=CONTINUATION_TURNS, declared_oversized_turns=(4,)
    )
    assert explained.passed is True


def test_scenario_matrix_and_driver_cover_both_hosts_modes_and_faults():
    configurations = (
        HostModelConfig(Host.CODEX, "0.145.0", "openai"),
        HostModelConfig(Host.CLAUDE, "2.1.220", "anthropic"),
    )
    matrix = build_scenario_matrix(configurations)

    assert {case.mode for case in matrix} == set(ScenarioMode)
    assert {case.fault for case in matrix} == set(FaultCase)
    assert {case.host for case in matrix} == {Host.CODEX, Host.CLAUDE}
    assert all(case.continuation_turns == CONTINUATION_TURNS for case in matrix)

    manifest = load_manifest(MANIFEST)
    validation = validate_manifest_source(manifest, _educode())
    answers = {probe.probe_id: probe.expected_answer for probe in manifest.probes}
    case = next(
        item
        for item in matrix
        if item.host is Host.CODEX
        and item.mode is ScenarioMode.MANUAL_COMPACT
        and item.fault is FaultCase.VALID
    )
    driver = BenchmarkScenarioDriver(manifest, validation)
    result = driver.run(
        case,
        lambda selected: ScenarioObservation(
            case_id=selected.case_id,
            answers=answers,
            compaction_turns=(),
            continuation_turns=CONTINUATION_TURNS,
            pre_body_chars=80_000,
            post_body_chars=20_000,
            reentry_chars=4_000,
            fixed_prefix_chars=12_000,
        ),
    )

    assert result.preservation.overall_accuracy == 1.0
    assert result.savings.qualification == "qualified"
    assert result.thrashing.passed is True
    artifact = json.dumps(result.to_dict(), sort_keys=True)
    assert len(artifact) <= 32_768
    assert "expected_answer" not in artifact
    assert str(_educode()) not in artifact


def _git(repository: Path, *arguments: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
