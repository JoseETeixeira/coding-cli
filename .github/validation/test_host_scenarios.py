from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from validate_source_assets import (
    authorize_specialist_tool,
    evaluate_auto_improvement_trace,
    evaluate_entry_trace,
    evaluate_mutation_trace,
    evaluate_specialist_trace,
    finding_identity,
    frontmatter,
    requires_mutation_review,
    resolve_effective_tools,
    role_contract_failure_code,
)

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = json.loads((ROOT / ".github/validation/host-scenarios.json").read_text())
HOSTS = json.loads((ROOT / ".github/validation/host-fixtures.json").read_text())
NEGATIVES = json.loads((ROOT / ".github/validation/negative-fixtures.json").read_text())
ROLE_CONTRACT = json.loads((ROOT / "agents/role-contracts.json").read_text())


def _host_trace(host: str) -> dict:
    trace = deepcopy(SCENARIOS["mutation_review"]["positive_trace"])
    trace["host"] = host
    return trace


def _prior_revision(trace: dict, revision: int, blocker_identity: str) -> dict:
    return {
        "revision": revision,
        "batchId": trace["batchId"],
        "manifestHash": trace["manifestHash"],
        "reviewerId": trace["reviewerId"],
        "writerId": trace["writerIds"][0],
        "blockerIdentities": [blocker_identity],
        "terminalStatus": "CHANGES_REQUIRED",
    }


class HostScenarioTests(unittest.TestCase):
    def test_every_host_and_task_requires_entry_and_repowise_before_work(self) -> None:
        prefix = SCENARIOS["required_prefix"]
        for host in SCENARIOS["supported_hosts"]:
            for task_class in SCENARIOS["task_classes"]:
                trace = [*prefix, "repository_work"]
                self.assertEqual(evaluate_entry_trace(trace, "current"), "PASS", host)
                self.assertLess(
                    trace.index("get_index_status"), trace.index("repository_work")
                )
                self.assertLess(
                    trace.index("scoped_repowise_query"), trace.index("repository_work")
                )
                self.assertIn(task_class, SCENARIOS["task_classes"])
        for fixture in NEGATIVES["entry_trace_cases"]:
            self.assertEqual(
                evaluate_entry_trace(
                    fixture["events"],
                    fixture["freshness"],
                    fixture.get("retryFreshness"),
                ),
                fixture["expected"],
                fixture["id"],
            )

    def test_specialists_repeat_freshness_and_query(self) -> None:
        prefix = SCENARIOS["specialist_prefix"]
        for specialist in SCENARIOS["specialists"]:
            trace = [*prefix, "specialist_work"]
            self.assertEqual(
                evaluate_specialist_trace(trace, "current"), "PASS", specialist
            )
        for fixture in NEGATIVES["specialist_trace_cases"]:
            for host in SCENARIOS["supported_hosts"]:
                self.assertEqual(
                    evaluate_specialist_trace(
                        fixture["events"],
                        fixture["freshness"],
                        fixture.get("retryFreshness"),
                    ),
                    fixture["expected"],
                    f"{host}/{fixture['id']}",
                )

    def test_bad_freshness_never_reaches_repository_work(self) -> None:
        for state in SCENARIOS["blocking_freshness"]:
            blocked = [
                *SCENARIOS["required_prefix"][:-1],
                "bounded_retry",
                "get_index_status_retry",
                "blocked",
            ]
            self.assertEqual(evaluate_entry_trace(blocked, state, state), "PASS")
            self.assertEqual(
                evaluate_entry_trace(
                    [*SCENARIOS["required_prefix"], "repository_work"], state, state
                ),
                "REPOWISE_BLOCKING_STATE_BYPASSED",
            )

    def test_role_skill_contract_rejects_every_negative_fixture(self) -> None:
        for fixture in NEGATIVES["skill_contract_mutations"]:
            contract = deepcopy(ROLE_CONTRACT)
            values = contract["roles"][fixture["role"]][fixture["field"]]
            operation = fixture["operation"]
            if operation == "remove":
                values.remove(fixture["old"])
            elif operation == "append":
                values.append(fixture["value"])
            elif operation == "replace":
                values[values.index(fixture["old"])] = fixture["value"]
            else:  # pragma: no cover - fixture schema is source-validated
                self.fail(f"unknown fixture operation: {operation}")
            self.assertEqual(
                role_contract_failure_code(contract), fixture["expected"], fixture["id"]
            )

    def test_fixed_role_tools_cannot_be_broadened_by_skills(self) -> None:
        for role_name, role in ROLE_CONTRACT["roles"].items():
            metadata = frontmatter(ROOT / role["agent"])
            declared = [item.strip() for item in metadata["tools"][1:-1].split(",")]
            self.assertEqual(set(declared), set(role["tools"]), role_name)
            self.assertEqual(
                resolve_effective_tools(role["tools"], role["tools"]),
                role["tools"],
                role_name,
            )
        self.assertEqual(
            ROLE_CONTRACT["roles"]["implementation-specialist"]["taskSpecificSkills"],
            "approved-scope-only",
        )
        for fixture in NEGATIVES["advisory_tool_cases"]:
            if "expected_error" in fixture:
                with self.assertRaisesRegex(ValueError, fixture["expected_error"]):
                    resolve_effective_tools(fixture["fixed"], fixture["advisory"])
            else:
                self.assertEqual(
                    resolve_effective_tools(fixture["fixed"], fixture["advisory"]),
                    fixture["expected"],
                    fixture["id"],
                )
        for fixture in NEGATIVES["specialist_tool_cases"]:
            self.assertEqual(
                authorize_specialist_tool(fixture["fixed"], fixture["requested"]),
                fixture["expected"],
                fixture["id"],
            )

    def test_supported_hosts_accept_complete_mutation_trace(self) -> None:
        for host, profile in HOSTS["supported"].items():
            self.assertEqual(
                evaluate_mutation_trace(_host_trace(host), profile), "PASS", host
            )

    def test_mutation_trace_negative_cases_return_exact_codes(self) -> None:
        for fixture in NEGATIVES["mutation_trace_mutations"]:
            trace = _host_trace("claude")
            trace.update(deepcopy(fixture.get("overrides", {})))
            for key in fixture.get("removeKeys", []):
                trace.pop(key, None)
            profile_host = fixture.get("profileHost", trace.get("host"))
            profile = HOSTS["supported"].get(profile_host)
            self.assertEqual(
                evaluate_mutation_trace(trace, profile),
                fixture["expected"],
                fixture["id"],
            )

    def test_supported_host_without_reviewer_continuity_fails_closed(self) -> None:
        for fixture in HOSTS["ineligible_profiles"].values():
            profile = deepcopy(HOSTS["supported"][fixture["base_host"]])
            profile["capabilities"].update(fixture["capability_overrides"])
            self.assertEqual(
                evaluate_mutation_trace(_host_trace(fixture["base_host"]), profile),
                fixture["expected"],
            )

    def test_review_recursion_exempts_only_generated_nondurable_outputs(self) -> None:
        for kind in SCENARIOS["mutation_review"]["ignored_artifact_kinds"]:
            self.assertFalse(requires_mutation_review(kind), kind)
        for kind in SCENARIOS["mutation_review"]["durable_artifact_kinds"]:
            self.assertTrue(requires_mutation_review(kind), kind)
        with self.assertRaisesRegex(
            ValueError, "MUTATION_REVIEW_ARTIFACT_KIND_UNKNOWN"
        ):
            requires_mutation_review("generated-source")

    def test_blocked_threshold_uses_consecutive_condition_identity(self) -> None:
        profile = HOSTS["supported"]["claude"]
        identity = finding_identity(
            {"severity": "high", "path": "source.py", "message": "same"}
        )
        for count in (1, 2, 3):
            trace = _host_trace("claude")
            trace["revision"] = count
            trace["reviewerObservations"] = [
                {"phase": phase, "reviewerId": "reviewer-a", "revision": count}
                for phase in ("prewrite", "postwrite")
            ]
            trace["priorRevisions"] = [
                _prior_revision(trace, revision, identity)
                for revision in range(1, count)
            ]
            trace["findings"] = [
                {"severity": "high", "path": "source.py", "message": "same"}
            ]
            trace["status"] = "BLOCKED" if count == 3 else "CHANGES_REQUIRED"
            trace["blockedReason"] = "repeated-blocker" if count == 3 else "none"
            self.assertEqual(evaluate_mutation_trace(trace, profile), "PASS", count)
        reset = _host_trace("claude")
        reset["revision"] = 3
        reset["reviewerObservations"] = [
            {"phase": phase, "reviewerId": "reviewer-a", "revision": 3}
            for phase in ("prewrite", "postwrite")
        ]
        reset["priorRevisions"] = [
            _prior_revision(reset, revision, identity) for revision in (1, 2)
        ]
        reset["findings"] = [
            {"severity": "high", "path": "source.py", "message": "different"}
        ]
        reset["status"] = "CHANGES_REQUIRED"
        self.assertEqual(evaluate_mutation_trace(reset, profile), "PASS")

    def test_auto_improvement_paths_and_review_composition(self) -> None:
        for host, profile in HOSTS["supported"].items():
            for name, fixture in SCENARIOS["auto_improvement"].items():
                trace = deepcopy(fixture)
                if isinstance(trace.get("mutation_trace"), dict):
                    trace["mutation_trace"]["host"] = host
                self.assertEqual(
                    evaluate_auto_improvement_trace(trace, profile),
                    "PASS",
                    f"{host}/{name}",
                )
        for fixture in NEGATIVES["auto_improvement_mutations"]:
            trace = deepcopy(SCENARIOS["auto_improvement"][fixture["base"]])
            trace.update(deepcopy(fixture.get("overrides", {})))
            if isinstance(trace.get("mutation_trace"), dict):
                trace["mutation_trace"]["host"] = "claude"
                trace["mutation_trace"].update(
                    deepcopy(fixture.get("mutationTraceOverrides", {}))
                )
            trace["events"] = [
                item
                for item in trace["events"]
                if item not in fixture.get("removeEvents", [])
            ]
            trace["events"].extend(fixture.get("appendEvents", []))
            if fixture.get("removeMutationTrace"):
                trace.pop("mutation_trace", None)
            self.assertEqual(
                evaluate_auto_improvement_trace(trace, HOSTS["supported"]["claude"]),
                fixture["expected"],
                fixture["id"],
            )

    def test_static_boundaries_deny_undeclared_mutation_and_network(self) -> None:
        specialists = SCENARIOS["specialists"]
        self.assertFalse(specialists["repository-researcher"]["writes"])
        self.assertFalse(specialists["verification-reviewer"]["writes"])
        self.assertTrue(
            all(not boundary["network"] for boundary in specialists.values())
        )
        self.assertEqual(
            specialists["implementation-specialist"]["writes"], "approved-scope"
        )
        self.assertEqual(
            authorize_specialist_tool(
                ROLE_CONTRACT["roles"]["verification-reviewer"]["tools"],
                NEGATIVES["undeclared_specialist_tool"],
            ),
            "SPECIALIST_TOOL_UNDECLARED",
        )


if __name__ == "__main__":
    unittest.main()
