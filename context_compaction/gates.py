"""Content-free deterministic gate report for the compaction pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from .benchmark import (
    CONTINUATION_TURNS,
    MAX_BENCHMARK_ARTIFACT_BYTES,
    FaultCase,
    HostModelConfig,
    ScenarioMode,
    assess_thrashing,
    build_scenario_matrix,
    load_manifest,
    measure_representative_states,
    measure_savings,
    validate_manifest_source,
)
from .budget import BudgetCategory, allocate_categories
from .contracts import validate_contract_assets
from .models import Host


def deterministic_gate_report(
    *,
    source_root: str | Path,
    manifest_path: str | Path,
    educode_repository: str | Path,
) -> dict[str, object]:
    assets = validate_contract_assets(source_root)
    manifest = load_manifest(manifest_path)
    source_validation = validate_manifest_source(manifest, educode_repository)
    configurations = (
        HostModelConfig(Host.CODEX, "0.145.0", "openai"),
        HostModelConfig(Host.CLAUDE, "2.1.220", "anthropic"),
    )
    matrix = build_scenario_matrix(configurations)
    assemblers: dict[str, Callable[[], object]] = {
        fault.value: _assembly_callback(fault) for fault in FaultCase
    }
    latency = measure_representative_states(assemblers)
    thrashing = {
        mode.value: assess_thrashing(
            (), continuation_turns=CONTINUATION_TURNS
        ).to_dict()
        for mode in (
            ScenarioMode.MANUAL_COMPACT,
            ScenarioMode.AUTOMATIC_COMPACT,
            ScenarioMode.MIDTURN,
        )
    }
    savings = measure_savings(
        pre_body_chars=80_000,
        post_body_chars=20_000,
        fixed_prefix_chars=12_000,
        reentry_chars=4_000,
    )
    report: dict[str, object] = {
        "schema_version": 1,
        "qualification": "focused_local",
        "source_validation": source_validation.to_dict(),
        "contract": {
            "prompt_sha256": assets.prompt_sha256,
            "prompt_chars": assets.prompt_chars,
            "prompt_estimated_tokens": assets.prompt_estimated_tokens,
            "reentry_character_limit": 8_000,
            "reentry_estimated_token_limit": 2_000,
            "memory_text_character_limit": 4_000,
            "memory_envelope_character_limit": 8_000,
            "event_retention_limit": 200,
        },
        "matrix": {
            "case_count": len(matrix),
            "host_count": len({item.host for item in matrix}),
            "mode_count": len({item.mode for item in matrix}),
            "fault_count": len({item.fault for item in matrix}),
        },
        "assembly": {
            state: {
                **measurement.to_dict(),
                "p95_gate_ms": 2_000,
                "passed": measurement.p95_ms <= 2_000,
            }
            for state, measurement in latency.items()
        },
        "thrashing": thrashing,
        "savings_proxy": savings.to_dict(),
        "real_host_measurement": "unmeasured",
        "owner_acceptance": "unmeasured",
    }
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_BENCHMARK_ARTIFACT_BYTES:
        raise RuntimeError("deterministic gate report exceeds its content-free bound")
    if not all(item["passed"] for item in report["assembly"].values()):
        raise RuntimeError("local assembly p95 gate failed")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="context-pilot-gates")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--educode-repo", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    report = deterministic_gate_report(
        source_root=arguments.source_root,
        manifest_path=arguments.manifest,
        educode_repository=arguments.educode_repo,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


def _assembly_callback(fault: FaultCase) -> Callable[[], object]:
    degraded = [] if fault is FaultCase.VALID else [fault.value]
    status = json.dumps(
        {
            "gate": "validation_required" if not degraded else "degraded",
            "degraded": degraded,
            "authority": "reopen current source",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    task = json.dumps(
        {
            "task": "agentic-development-workbench",
            "phase": 5,
            "approval": "pending" if fault is FaultCase.ACTION_AMBIGUOUS else "granted",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    actions = json.dumps(
        [
            {
                "id": f"action-{index}",
                "class": "external_side_effect",
                "status": "ambiguous" if fault is FaultCase.ACTION_AMBIGUOUS else "completed",
            }
            for index in range(20)
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    repository = json.dumps(
        {
            "fingerprint": "a" * 64,
            "head": "b" * 40,
            "dirty_count": 2,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    pointers = json.dumps(
        [
            {
                "kind": "source",
                "id": f"pointer-{index}",
                "hash": "c" * 64,
            }
            for index in range(64)
        ],
        sort_keys=True,
        separators=(",", ":"),
    )

    def assemble():
        result = allocate_categories(
            (
                BudgetCategory("lifecycle_status", status, 0, required=True),
                BudgetCategory("task_identity", task, 1, required=True),
                BudgetCategory("pending_actions", actions, 2, required=True),
                BudgetCategory("repository_state", repository, 3, required=True),
                BudgetCategory("artifact_pointers", pointers, 4),
                BudgetCategory("memory_pointers", "[]", 5),
            ),
            max_chars=8_000,
            max_tokens=2_000,
        )
        if result.used_chars > 8_000 or result.estimated_tokens > 2_000:
            raise RuntimeError("assembly escaped its budget")
        return result

    return assemble


if __name__ == "__main__":
    raise SystemExit(main())
