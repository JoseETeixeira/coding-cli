"""Deterministic aggregate gate report."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from context_compaction.gates import deterministic_gate_report

ROOT = Path(__file__).parents[2]


def test_gate_report_is_bounded_source_validated_and_explicitly_qualified():
    configured = os.environ.get("EDUCODE_BENCHMARK_REPO")
    educode = Path(configured) if configured else Path.home() / "source" / "educode"
    if not (educode / ".git").exists():
        pytest.skip("frozen educode checkout is unavailable")

    report = deterministic_gate_report(
        source_root=ROOT,
        manifest_path=ROOT
        / "benchmarks"
        / "context_compaction"
        / "educode-probes.v1.json",
        educode_repository=educode,
    )

    assert report["qualification"] == "focused_local"
    assert report["matrix"] == {
        "case_count": 64,
        "host_count": 2,
        "mode_count": 4,
        "fault_count": 8,
    }
    assert all(item["sample_count"] == 30 for item in report["assembly"].values())
    assert all(item["passed"] for item in report["assembly"].values())
    assert all(item["continuation_turns"] == 10 for item in report["thrashing"].values())
    assert report["savings_proxy"]["qualification"] == "qualified"
    assert report["real_host_measurement"] == "unmeasured"
    assert report["owner_acceptance"] == "unmeasured"
    encoded = json.dumps(report, sort_keys=True)
    assert len(encoded) <= 32_768
    assert str(educode.resolve()) not in encoded
