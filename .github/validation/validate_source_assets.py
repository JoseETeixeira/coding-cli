#!/usr/bin/env python3
"""Dependency-light validation for canonical source-only agent assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
ACTIVE_ROOTS = (
    ROOT / "agents",
    ROOT / "skills",
    ROOT / "prompts",
    ROOT / "instructions",
    ROOT / "hooks",
    ROOT / ".claude/hooks",
)
REQUIRED_AGENTS = {
    "batman",
    "repository-researcher",
    "planning-specialist",
    "implementation-specialist",
    "verification-reviewer",
    "documentation-specialist",
}
ROLE_KEYS = {
    "agent",
    "requiredSkills",
    "conditionalSkills",
    "requiredProcedures",
    "tools",
    "writes",
    "delegates",
    "network",
    "memoryActions",
    "taskSpecificSkills",
}
EVENT_KEYS = {
    "requiredSkills",
    "conditionalSkills",
    "requiredProcedures",
    "sequence",
}
EXPECTED_ROLE_CONTRACTS = {
    "batman": {
        "requiredSkills": ["freighthero-entry", "auto-improvement", "repowise-memory"],
        "conditionalSkills": ["mutation-review"],
        "requiredProcedures": [
            "skills/freighthero-entry/references/workflow.md",
            "skills/freighthero-entry/references/host-boundaries.md",
        ],
        "tools": {"read", "search", "execute", "edit", "agent", "repowise"},
        "writes": "approved-scope",
        "delegates": True,
        "network": False,
        "memoryActions": ["read"],
        "taskSpecificSkills": "smallest-sufficient-set",
    },
    "repository-researcher": {
        "requiredSkills": ["freighthero-entry", "repowise-memory"],
        "conditionalSkills": [],
        "requiredProcedures": ["skills/freighthero-entry/references/repowise.md"],
        "tools": {"read", "search", "execute", "repowise"},
        "writes": False,
        "delegates": False,
        "network": False,
        "memoryActions": ["read"],
        "taskSpecificSkills": "none",
    },
    "planning-specialist": {
        "requiredSkills": ["freighthero-entry", "grill-me", "repowise-memory"],
        "conditionalSkills": ["visual-explainer"],
        "requiredProcedures": [
            "skills/freighthero-entry/references/workflow.md",
            "skills/freighthero-entry/references/governance.md",
        ],
        "tools": {"read", "search", "execute", "edit", "repowise"},
        "writes": "planning-only",
        "delegates": False,
        "network": False,
        "memoryActions": ["read"],
        "taskSpecificSkills": "none",
    },
    "implementation-specialist": {
        "requiredSkills": ["freighthero-entry", "repowise-memory"],
        "conditionalSkills": [],
        "requiredProcedures": [
            "skills/freighthero-entry/references/repowise.md",
            "skills/freighthero-entry/references/host-boundaries.md",
        ],
        "tools": {"read", "search", "execute", "edit", "repowise"},
        "writes": "approved-scope",
        "delegates": False,
        "network": False,
        "memoryActions": ["read"],
        "taskSpecificSkills": "approved-scope-only",
    },
    "verification-reviewer": {
        "requiredSkills": ["freighthero-entry", "mutation-review", "repowise-memory"],
        "conditionalSkills": ["visual-explainer"],
        "requiredProcedures": ["instructions/code-review.instructions.md"],
        "tools": {"read", "search", "execute", "repowise"},
        "writes": False,
        "delegates": False,
        "network": False,
        "memoryActions": ["read"],
        "taskSpecificSkills": "none",
    },
    "documentation-specialist": {
        "requiredSkills": ["freighthero-entry", "repowise-memory"],
        "conditionalSkills": ["visual-explainer"],
        "requiredProcedures": ["skills/freighthero-entry/references/governance.md"],
        "tools": {"read", "search", "execute", "edit", "repowise"},
        "writes": "docs-only",
        "delegates": False,
        "network": False,
        "memoryActions": ["read"],
        "taskSpecificSkills": "none",
    },
}
EXPECTED_PHASE_EVENTS = {
    "entry": (
        ["freighthero-entry", "auto-improvement", "repowise-memory"],
        ["mutation-review"],
        [],
        [
            "evaluate-auto-improvement",
            "classify",
            "load-selected-skills",
            "repowise-status",
            "shared-memory-status",
            "task-context",
            "repowise-query",
        ],
    ),
    "repository-research": (
        ["freighthero-entry", "repowise-memory"],
        [],
        ["skills/freighthero-entry/references/repowise.md"],
        ["repowise-status", "shared-memory-status", "task-context", "repowise-query", "read-cited-source", "report"],
    ),
    "understanding": (
        ["batman-understanding", "visual-explainer", "grill-me", "repowise-memory"],
        [],
        [],
        ["shared-memory-status", "task-context", "repowise-discovery", "draft", "grill-me", "approval"],
    ),
    "requirements": (
        ["grill-me", "repowise-memory"],
        ["visual-explainer"],
        ["prompts/requirements.prompt.md"],
        ["shared-memory-status", "task-context", "repowise-discovery", "draft", "grill-me", "approval"],
    ),
    "design": (
        ["grill-me", "repowise-memory"],
        ["visual-explainer"],
        ["prompts/design.prompt.md"],
        ["shared-memory-status", "task-context", "repowise-discovery", "draft", "grill-me", "approval"],
    ),
    "task-planning": (
        ["grill-me", "repowise-memory"],
        ["visual-explainer"],
        ["prompts/create-tasks.prompt.md"],
        ["shared-memory-status", "task-context", "repowise-discovery", "draft", "grill-me", "approval"],
    ),
    "implementation": (
        ["freighthero-entry", "mutation-review", "repowise-memory"],
        [],
        ["prompts/execute-task.prompt.md"],
        ["shared-memory-status", "task-context", "prewrite-review", "write", "targeted-checks", "postwrite-review"],
    ),
    "tests": (
        ["freighthero-entry", "repowise-memory"],
        [],
        [],
        ["shared-memory-status", "task-context", "targeted-tests", "regression-tests", "record-evidence"],
    ),
    "code-review": (
        ["freighthero-entry", "mutation-review", "repowise-memory"],
        ["visual-explainer"],
        ["instructions/code-review.instructions.md"],
        ["shared-memory-status", "task-context", "review-full-diff", "fix-findings", "rerun-checks", "pass"],
    ),
    "documentation-updates": (
        ["freighthero-entry", "repowise-memory"],
        ["visual-explainer"],
        ["skills/freighthero-entry/references/governance.md"],
        ["shared-memory-status", "task-context", "append-governance-outcomes", "update-covered-docs", "verify-citations"],
    ),
}
RETIRED = re.compile(
    r"freighthero-codebase|freighthero-mcp|cocoindex|openwiki|refresh-repowise|patch-repowise",
    re.IGNORECASE,
)
HARD_HOME = re.compile(r"/(Users|home)/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+")
SECRET = re.compile(
    r"(?<![A-Za-z0-9_-])(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|lsv2_[A-Za-z0-9_]+)"
)
KNOWN_TOOLS = frozenset({"read", "search", "execute", "edit", "agent", "repowise"})
REVIEW_REQUIRED_KINDS = frozenset(
    {
        "source",
        "configuration",
        "test",
        "documentation",
        "migration",
        "lockfile",
        "adr",
        "prd",
        "prompt",
        "agent",
        "instruction",
        "skill",
    }
)
REVIEW_EXEMPT_KINDS = frozenset(
    {
        "ignored-database",
        "cache",
        "coverage",
        "temporary-test-output",
        "reviewer-trace",
    }
)
MUTATION_EVENTS = (
    "record-manifest",
    "spawn-reviewer",
    "prewrite-pass",
    "write",
    "checks-pass",
    "postwrite-review",
)
REVIEWER_DENIED_ACTIONS = frozenset({"write", "delegate", "auto-improvement"})
ENTRY_PREFIX = (
    "evaluate_auto_improvement",
    "classify",
    "select_skill_metadata",
    "read_selected_skill",
    "get_index_status",
    "scoped_repowise_query",
)
SPECIALIST_PREFIX = (
    "delegate_static_specialist",
    "specialist_get_index_status",
    "specialist_scoped_repowise_query",
)
BLOCKING_FRESHNESS = frozenset(
    {
        "stale",
        "empty",
        "unauthorized",
        "malformed",
        "partial",
        "inconsistent",
        "unavailable",
    }
)
TRACE_KEYS = {
    "host",
    "batchId",
    "manifest",
    "manifestHash",
    "events",
    "terminalStage",
    "reviewerId",
    "revision",
    "reviewerObservations",
    "priorRevisions",
    "writerIds",
    "coveredFiles",
    "checks",
    "checksPassed",
    "writtenFingerprint",
    "worktreeFingerprint",
    "findings",
    "status",
    "blockedReason",
    "blockedEvidence",
    "reviewerActions",
}
IMMEDIATE_BLOCK_REASONS = frozenset(
    {"new-authority", "external-state-unavailable", "architecture-expansion"}
)
HOST_ACTIVATIONS = {
    "claude": "--plugin-dir",
    "codex": "AGENTS.md",
    "local-copilot": "workspace-discovery-paths",
}
TASK_CLASSES = ("research", "planning", "implementation", "review", "documentation")
SPECIALIST_BOUNDARIES = {
    "repository-researcher": {"writes": False, "network": False},
    "planning-specialist": {"writes": "planning-only", "network": False},
    "implementation-specialist": {"writes": "approved-scope", "network": False},
    "verification-reviewer": {"writes": False, "network": False},
    "documentation-specialist": {"writes": "docs-only", "network": False},
}
REQUIRED_NEGATIVE_IDS = {
    "skill_contract_mutations": {
        "missing-required",
        "extra-required",
        "unknown-skill",
        "duplicate-skill",
        "escaping-skill",
    },
    "entry_trace_cases": {
        "entry-reordered",
        "stale-bypass",
        "stale-blocked",
        "stale-recovered",
        "stale-recovery-bypass",
        "entry-malformed-freshness",
    },
    "specialist_trace_cases": {
        "specialist-query-late",
        "specialist-stale-bypass",
        "specialist-stale-blocked",
        "specialist-stale-recovered",
        "specialist-malformed-retry",
    },
    "specialist_tool_cases": {"declared-tool", "undeclared-tool"},
    "mutation_trace_mutations": {
        "prewrite-order",
        "duplicate-lifecycle-event",
        "post-review-write",
        "single-reviewer-observation",
        "reviewer-swap",
        "multiple-writers",
        "missing-batch-id",
        "bad-manifest-hash",
        "zero-revision",
        "empty-checks",
        "empty-manifest-path",
        "escaping-manifest-path",
        "control-character-path",
        "incomplete-manifest",
        "extra-manifest",
        "failed-checks",
        "bad-fingerprint-format",
        "fingerprint-drift",
        "medium-finding-pass",
        "reviewer-write",
        "reviewer-delegate",
        "reviewer-auto-improvement",
        "unsupported-host",
        "host-profile-mismatch",
        "blocker-identity-mismatch",
        "finding-identity-collision",
        "revision-one-third-blocker",
        "cross-revision-reviewer-swap",
        "cross-revision-writer-swap",
        "cross-revision-batch-swap",
        "cross-revision-manifest-swap",
        "premature-blocked",
        "third-same-not-blocked",
        "revision-after-blocked-threshold",
        "different-blocker-resets",
        "new-authority-block",
        "external-state-block",
        "architecture-expansion-block",
        "postwrite-immediate-block",
        "bool-observation-revision",
        "list-blocked-reason",
    },
    "auto_improvement_mutations": {
        "write-without-review",
        "duplicate-parent-write",
        "nested-changes-required",
        "nested-blocked",
        "no-candidate-write",
        "protected-write",
        "protected-reordered",
        "conflict-write",
        "conflict-reordered",
        "malformed-auto-events",
    },
    "advisory_tool_cases": {
        "narrow-tools",
        "known-outside-role-removed",
        "unknown-tool",
    },
}


def fail(message: str) -> None:
    raise ValueError(message)


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"missing frontmatter: {path.relative_to(ROOT)}")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"unterminated frontmatter: {path.relative_to(ROOT)}")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def validate_skills() -> None:
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        metadata = frontmatter(path)
        expected = path.parent.name
        if metadata.get("name") != expected or not re.fullmatch(
            r"[a-z0-9-]+", expected
        ):
            fail(f"skill identity mismatch: {path.relative_to(ROOT)}")
        if not metadata.get("description"):
            fail(f"skill description missing: {path.relative_to(ROOT)}")
        if "tools" in metadata:
            fail(f"skill cannot declare authoritative tools: {path.relative_to(ROOT)}")
        if "allowed-tools" in metadata:
            raw_allowed = metadata["allowed-tools"]
            if not raw_allowed.startswith("[") or not raw_allowed.endswith("]"):
                fail(
                    f"skill allowed-tools must be an inline list: {path.relative_to(ROOT)}"
                )
            tokens = raw_allowed[1:-1].split(",")
            if not tokens or any(not item.strip() for item in tokens):
                fail(
                    f"skill allowed-tools contain an empty token: {path.relative_to(ROOT)}"
                )
            resolve_effective_tools(
                sorted(KNOWN_TOOLS), [item.strip() for item in tokens]
            )
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            clean = target.split("#", 1)[0]
            if not clean or "://" in clean:
                continue
            target_path = Path(clean)
            if ".." in target_path.parts:
                fail(f"escaping skill reference: {path.relative_to(ROOT)} -> {target}")
            resolved = (path.parent / clean).resolve()
            managed_reference = target_path.parts[0] in {
                "assets",
                "references",
                "scripts",
            }
            if not managed_reference and not resolved.exists():
                # Some skills cite paths that are resolved in the target repository at task time.
                continue
            if path.parent.resolve() not in resolved.parents or not resolved.is_file():
                fail(
                    f"broken or escaping skill reference: {path.relative_to(ROOT)} -> {target}"
                )
            if resolved.parent.name == "references":
                nested = re.findall(
                    r"\[[^]]+\]\(([^)]+)\)", resolved.read_text(encoding="utf-8")
                )
                if any(item and "://" not in item for item in nested):
                    fail(f"nested skill reference: {resolved.relative_to(ROOT)}")


def _canonical_list(value: object, *, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        fail(f"{label} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        fail(f"duplicate values in {label}")
    return value


def resolve_effective_tools(
    fixed_role_tools: object, advisory_allowed_tools: object
) -> list[str]:
    """Narrow fixed native tools with advisory skill metadata; never broaden."""
    fixed = _canonical_list(fixed_role_tools, label="fixed_role_tools")
    advisory = _canonical_list(advisory_allowed_tools, label="advisory_allowed_tools")
    if any(tool not in KNOWN_TOOLS for tool in [*fixed, *advisory]):
        fail("SKILL_ADVISORY_TOOL_UNKNOWN")
    allowed = set(advisory)
    return [tool for tool in fixed if tool in allowed]


def requires_mutation_review(artifact_kind: str) -> bool:
    if artifact_kind in REVIEW_REQUIRED_KINDS:
        return True
    if artifact_kind in REVIEW_EXEMPT_KINDS:
        return False
    fail(f"MUTATION_REVIEW_ARTIFACT_KIND_UNKNOWN: {artifact_kind}")


def _consecutive_tail(values: list[list[str]]) -> int:
    if not values:
        return 0
    last = values[-1]
    count = 0
    for value in reversed(values):
        if value != last:
            break
        count += 1
    return count


def mutation_host_eligibility(host_profile: object | None) -> str:
    if host_profile is None:
        return "MUTATION_REVIEW_HOST_UNSUPPORTED"
    if not isinstance(host_profile, dict):
        return "MUTATION_REVIEW_TRACE_MALFORMED"
    if (
        not isinstance(host_profile.get("host"), str)
        or not host_profile["host"]
        or host_profile.get("conformance_mode") != "instruction-evaluation"
        or host_profile.get("hard_enforcement_claim") is not False
    ):
        return "MUTATION_REVIEW_HOST_CAPABILITY_UNAVAILABLE"
    capabilities = host_profile.get("capabilities")
    required = {
        "same_reviewer",
        "reviewer_read_only",
        "reviewer_no_delegation",
        "single_writer",
    }
    if not isinstance(capabilities, dict) or set(capabilities) != required:
        return "MUTATION_REVIEW_HOST_CAPABILITY_UNAVAILABLE"
    if any(capabilities[item] is not True for item in required):
        return "MUTATION_REVIEW_HOST_CAPABILITY_UNAVAILABLE"
    return "PASS"


def evaluate_entry_trace(
    events: object, freshness: str, retry_freshness: str | None = None
) -> str:
    if not isinstance(events, list) or not all(
        isinstance(item, str) for item in events
    ):
        return "ENTRY_TRACE_MALFORMED"
    if not isinstance(freshness, str) or (
        retry_freshness is not None and not isinstance(retry_freshness, str)
    ):
        return "ENTRY_TRACE_MALFORMED"
    if freshness in BLOCKING_FRESHNESS:
        blocked = [
            *ENTRY_PREFIX[:-1],
            "bounded_retry",
            "get_index_status_retry",
            "blocked",
        ]
        recovered = [
            *ENTRY_PREFIX[:-1],
            "bounded_retry",
            "get_index_status_retry",
            "scoped_repowise_query",
            "repository_work",
        ]
        if retry_freshness in BLOCKING_FRESHNESS:
            return "PASS" if events == blocked else "REPOWISE_BLOCKING_STATE_BYPASSED"
        if retry_freshness == "current":
            return "PASS" if events == recovered else "ENTRY_ORDER_INVALID"
        return "REPOWISE_RETRY_STATE_MISSING"
    if freshness != "current":
        return "REPOWISE_FRESHNESS_UNKNOWN"
    if retry_freshness is not None:
        return "REPOWISE_RETRY_STATE_UNEXPECTED"
    return (
        "PASS"
        if events == [*ENTRY_PREFIX, "repository_work"]
        else "ENTRY_ORDER_INVALID"
    )


def evaluate_specialist_trace(
    events: object, freshness: str, retry_freshness: str | None = None
) -> str:
    if not isinstance(events, list) or not all(
        isinstance(item, str) for item in events
    ):
        return "SPECIALIST_TRACE_MALFORMED"
    if not isinstance(freshness, str) or (
        retry_freshness is not None and not isinstance(retry_freshness, str)
    ):
        return "SPECIALIST_TRACE_MALFORMED"
    if freshness in BLOCKING_FRESHNESS:
        blocked = [
            *SPECIALIST_PREFIX[:2],
            "specialist_bounded_retry",
            "specialist_get_index_status_retry",
            "specialist_blocked",
        ]
        recovered = [
            *SPECIALIST_PREFIX[:2],
            "specialist_bounded_retry",
            "specialist_get_index_status_retry",
            "specialist_scoped_repowise_query",
            "specialist_work",
        ]
        if retry_freshness in BLOCKING_FRESHNESS:
            return "PASS" if events == blocked else "SPECIALIST_FRESHNESS_BYPASSED"
        if retry_freshness == "current":
            return "PASS" if events == recovered else "SPECIALIST_ORDER_INVALID"
        return "SPECIALIST_RETRY_STATE_MISSING"
    if freshness != "current" or retry_freshness is not None:
        return "SPECIALIST_FRESHNESS_UNKNOWN"
    return (
        "PASS"
        if events == [*SPECIALIST_PREFIX, "specialist_work"]
        else "SPECIALIST_ORDER_INVALID"
    )


def authorize_specialist_tool(fixed_role_tools: object, requested_tool: object) -> str:
    if not isinstance(requested_tool, str) or not requested_tool:
        return "SPECIALIST_TOOL_MALFORMED"
    try:
        fixed = _canonical_list(fixed_role_tools, label="fixed_role_tools")
    except ValueError:
        return "SPECIALIST_TOOL_MALFORMED"
    return "PASS" if requested_tool in fixed else "SPECIALIST_TOOL_UNDECLARED"


def _valid_relative_path(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return False
    path = PurePosixPath(value)
    return (
        bool(path.parts)
        and value != "."
        and not path.is_absolute()
        and value == path.as_posix()
        and ".." not in path.parts
    )


def _manifest_hash(paths: list[str]) -> str:
    canonical = json.dumps(paths, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def finding_identity(finding: dict[str, str]) -> str:
    fields = [finding["severity"], finding["path"], finding["message"]]
    canonical = json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def evaluate_mutation_trace(trace: object, host_profile: object | None) -> str:
    """Evaluate a concrete host trace against code-owned review invariants."""
    eligibility = mutation_host_eligibility(host_profile)
    if eligibility != "PASS":
        return eligibility
    if not isinstance(trace, dict) or set(trace) != TRACE_KEYS:
        return "MUTATION_REVIEW_TRACE_MALFORMED"

    if trace.get("host") != host_profile.get("host"):
        return "MUTATION_REVIEW_HOST_MISMATCH"
    batch_id = trace.get("batchId")
    if (
        not isinstance(batch_id, str)
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]*", batch_id) is None
    ):
        return "MUTATION_REVIEW_BATCH_ID_INVALID"
    trace_revision = trace.get("revision")
    if type(trace_revision) is not int or trace_revision < 1:
        return "MUTATION_REVIEW_REVISION_INVALID"
    top_reviewer = trace.get("reviewerId")
    if not isinstance(top_reviewer, str) or not top_reviewer:
        return "MUTATION_REVIEW_REVIEWER_CHANGED"
    stage = trace.get("terminalStage")
    events = trace.get("events")
    writer_ids = trace.get("writerIds")
    written = trace.get("writtenFingerprint")
    reviewed = trace.get("worktreeFingerprint")
    if not isinstance(reviewed, str) or re.fullmatch(r"[a-f0-9]{64}", reviewed) is None:
        return "MUTATION_REVIEW_FINGERPRINT_DRIFT"
    if stage == "postwrite":
        if events != list(MUTATION_EVENTS):
            return "MUTATION_REVIEW_ORDER"
        expected_phases = ("prewrite", "postwrite")
        if (
            not isinstance(writer_ids, list)
            or len(writer_ids) != 1
            or not isinstance(writer_ids[0], str)
            or not writer_ids[0]
        ):
            return "MUTATION_REVIEW_MULTIPLE_WRITERS"
        if written != reviewed:
            return "MUTATION_REVIEW_FINGERPRINT_DRIFT"
    elif stage == "prewrite":
        if events != ["record-manifest", "spawn-reviewer", "prewrite-blocked"]:
            return "MUTATION_REVIEW_ORDER"
        expected_phases = ("prewrite",)
        if writer_ids != [] or written != "":
            return "MUTATION_REVIEW_PREWRITE_MUTATION"
    else:
        return "MUTATION_REVIEW_TERMINAL_STAGE_INVALID"
    observations = trace.get("reviewerObservations")
    if not isinstance(observations, list) or len(observations) != len(expected_phases):
        return "MUTATION_REVIEW_REVIEWER_OBSERVATION_INVALID"
    if len(observations) != len(expected_phases):
        return "BLOCKED"
    for observation, phase in zip(observations, expected_phases):
        if not isinstance(observation, dict) or set(observation) != {
            "phase",
            "reviewerId",
            "revision",
        }:
            return "MUTATION_REVIEW_REVIEWER_OBSERVATION_INVALID"
        if observation["phase"] != phase or observation["reviewerId"] != top_reviewer:
            return "MUTATION_REVIEW_REVIEWER_CHANGED"
        if (
            type(observation["revision"]) is not int
            or observation["revision"] != trace_revision
        ):
            return "MUTATION_REVIEW_REVISION_INVALID"

    manifest = trace.get("manifest")
    covered = trace.get("coveredFiles")
    if (
        not isinstance(manifest, list)
        or not manifest
        or not isinstance(covered, list)
        or not all(_valid_relative_path(item) for item in [*manifest, *covered])
        or len(manifest) != len(set(manifest))
        or len(covered) != len(set(covered))
        or set(manifest) != set(covered)
    ):
        return "MUTATION_REVIEW_MANIFEST_MISMATCH"
    manifest_hash = trace.get("manifestHash")
    if (
        not isinstance(manifest_hash, str)
        or re.fullmatch(r"[a-f0-9]{64}", manifest_hash) is None
        or manifest_hash != _manifest_hash(manifest)
    ):
        return "MUTATION_REVIEW_MANIFEST_HASH_INVALID"
    checks = trace.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or not all(isinstance(item, str) and item for item in checks)
        or len(checks) != len(set(checks))
    ):
        return "MUTATION_REVIEW_CHECKS_INVALID"
    if trace.get("checksPassed") is not True:
        return "MUTATION_REVIEW_CHECKS_FAILED"
    actions = trace.get("reviewerActions")
    if not isinstance(actions, list) or not all(
        isinstance(item, str) for item in actions
    ):
        return "MUTATION_REVIEW_TRACE_MALFORMED"
    if REVIEWER_DENIED_ACTIONS.intersection(actions):
        return "MUTATION_REVIEW_REVIEWER_ACTION_DENIED"

    prior_revisions = trace.get("priorRevisions")
    if (
        not isinstance(prior_revisions, list)
        or len(prior_revisions) != trace_revision - 1
    ):
        return "MUTATION_REVIEW_REVISION_STATE_INVALID"
    prior_blockers: list[list[str]] = []
    prior_writer: str | None = None
    prior_keys = {
        "revision",
        "batchId",
        "manifestHash",
        "reviewerId",
        "writerId",
        "blockerIdentities",
        "terminalStatus",
    }
    for expected_revision, prior in enumerate(prior_revisions, start=1):
        if not isinstance(prior, dict) or set(prior) != prior_keys:
            return "MUTATION_REVIEW_REVISION_STATE_INVALID"
        if (
            type(prior["revision"]) is not int
            or prior["revision"] != expected_revision
            or prior["terminalStatus"] != "CHANGES_REQUIRED"
        ):
            return "MUTATION_REVIEW_REVISION_STATE_INVALID"
        if prior["batchId"] != batch_id or prior["manifestHash"] != manifest_hash:
            return "MUTATION_REVIEW_REVISION_STATE_INVALID"
        if prior["reviewerId"] != top_reviewer:
            return "MUTATION_REVIEW_REVIEWER_CHANGED"
        writer = prior["writerId"]
        if not isinstance(writer, str) or not writer:
            return "MUTATION_REVIEW_WRITER_CHANGED"
        if prior_writer is None:
            prior_writer = writer
        elif prior_writer != writer:
            return "MUTATION_REVIEW_WRITER_CHANGED"
        identities = prior["blockerIdentities"]
        if (
            not isinstance(identities, list)
            or not identities
            or not all(
                isinstance(item, str) and re.fullmatch(r"[a-f0-9]{64}", item)
                for item in identities
            )
        ):
            return "MUTATION_REVIEW_REVISION_STATE_INVALID"
        if identities != sorted(set(identities)):
            return "MUTATION_REVIEW_REVISION_STATE_INVALID"
        prior_blockers.append(identities)
        if _consecutive_tail(prior_blockers) >= 3:
            return "MUTATION_REVIEW_REVISION_STATE_INVALID"
    if (
        stage == "postwrite"
        and prior_writer is not None
        and writer_ids[0] != prior_writer
    ):
        return "MUTATION_REVIEW_WRITER_CHANGED"

    findings = trace.get("findings")
    if not isinstance(findings, list):
        return "MUTATION_REVIEW_TRACE_MALFORMED"
    severities: list[str] = []
    current_blockers: list[str] = []
    for finding in findings:
        if (
            not isinstance(finding, dict)
            or set(finding) != {"severity", "path", "message"}
            or not isinstance(finding.get("severity"), str)
            or finding["severity"] not in {"blocker", "high", "medium", "low"}
            or not all(
                isinstance(finding.get(key), str) and finding[key]
                for key in ("path", "message")
            )
        ):
            return "MUTATION_REVIEW_TRACE_MALFORMED"
        severities.append(finding["severity"])
        if finding["severity"] in {"blocker", "high", "medium"}:
            current_blockers.append(finding_identity(finding))
    blocking = any(item in {"blocker", "high", "medium"} for item in severities)
    status = trace.get("status")
    blocked_reason = trace.get("blockedReason")
    blocked_evidence = trace.get("blockedEvidence")
    if (
        not isinstance(status, str)
        or status not in {"PASS", "CHANGES_REQUIRED", "BLOCKED"}
        or not isinstance(blocked_reason, str)
        or blocked_reason not in {"none", "repeated-blocker", *IMMEDIATE_BLOCK_REASONS}
        or not isinstance(blocked_evidence, str)
    ):
        return "MUTATION_REVIEW_TRACE_MALFORMED"
    if stage == "prewrite":
        if (
            status != "BLOCKED"
            or blocked_reason not in IMMEDIATE_BLOCK_REASONS
            or not blocked_evidence
            or findings
        ):
            return "MUTATION_REVIEW_BLOCKER_STATE_INVALID"
        return "PASS"
    if blocked_reason in IMMEDIATE_BLOCK_REASONS or blocked_evidence:
        return "MUTATION_REVIEW_BLOCKER_STATE_INVALID"
    if status == "PASS" and blocking:
        return "MUTATION_REVIEW_FINDINGS_UNRESOLVED"
    if blocking:
        current = sorted(current_blockers)
        history = [*prior_blockers, current]
        repeated = _consecutive_tail(history) >= 3
        expected = "BLOCKED" if repeated else "CHANGES_REQUIRED"
        expected_reason = "repeated-blocker" if repeated else "none"
        if status != expected or blocked_reason != expected_reason:
            return "MUTATION_REVIEW_BLOCKER_STATE_INVALID"
    elif status != "PASS" or blocked_reason != "none":
        return "MUTATION_REVIEW_BLOCKER_STATE_INVALID"
    return "PASS"


def evaluate_auto_improvement_trace(trace: object, host_profile: object | None) -> str:
    if not isinstance(trace, dict):
        return "AUTO_IMPROVEMENT_TRACE_MALFORMED"
    events = trace.get("events")
    if not isinstance(events, list) or not all(
        isinstance(item, str) for item in events
    ):
        return "AUTO_IMPROVEMENT_TRACE_MALFORMED"
    outcome = trace.get("outcome")
    if outcome == "NO_CANDIDATE":
        return (
            "PASS"
            if events == ["evaluate-auto-improvement", "silent"]
            and trace.get("writes") is False
            else "AUTO_IMPROVEMENT_TRACE_MALFORMED"
        )
    if outcome == "PROTECTED_TARGET_REFUSED":
        required = [
            "evaluate-auto-improvement",
            "identify-protected-target",
            "refuse",
            "route-owning-workflow",
        ]
        return (
            "PASS"
            if events == required and trace.get("writes") is False
            else "AUTO_IMPROVEMENT_PROTECTED_TARGET_WRITE"
        )
    if outcome == "CONFLICT_RESOLVED_BEFORE_MUTATION":
        required = [
            "load-candidate-sources",
            "show-both-sides",
            "record-selected-supersession-scope",
            "preview-diff",
            "explicit-user-approval",
        ]
        return (
            "PASS"
            if events == ["evaluate-auto-improvement", *required]
            and trace.get("writes") is False
            else "AUTO_IMPROVEMENT_CONFLICT_FLOW_INVALID"
        )
    if outcome != "CANONICAL_WRITE_REVIEWED":
        return "AUTO_IMPROVEMENT_TRACE_MALFORMED"
    required = [
        "specialist-report-candidate",
        "parent-evaluate",
        "tracked-source-check",
        "preview-diff",
        "explicit-user-approval",
        "record-manifest",
        "spawn-reviewer",
        "prewrite-pass",
        "parent-write",
        "checks-pass",
        "postwrite-review",
    ]
    mutation_trace = trace.get("mutation_trace")
    if events != required or not isinstance(mutation_trace, dict):
        return "AUTO_IMPROVEMENT_MUTATION_REVIEW_REQUIRED"
    result = evaluate_mutation_trace(mutation_trace, host_profile)
    if result != "PASS":
        return result
    unresolved = any(
        finding.get("severity") in {"blocker", "high", "medium"}
        for finding in mutation_trace["findings"]
    )
    if (
        mutation_trace.get("terminalStage") != "postwrite"
        or mutation_trace.get("status") != "PASS"
        or mutation_trace.get("blockedReason") != "none"
        or unresolved
    ):
        return "AUTO_IMPROVEMENT_MUTATION_NOT_PASSED"
    if mutation_trace.get("writerIds") != ["parent"]:
        return "AUTO_IMPROVEMENT_PARENT_WRITER_REQUIRED"
    return "PASS"


def _validate_skill_set(
    required: object, conditional: object, *, label: str
) -> tuple[list[str], list[str]]:
    required_values = _canonical_list(required, label=f"{label}.requiredSkills")
    conditional_values = _canonical_list(
        conditional, label=f"{label}.conditionalSkills"
    )
    if set(required_values) & set(conditional_values):
        fail(f"required and conditional skills overlap: {label}")
    skills_root = SKILLS.resolve()
    for skill in [*required_values, *conditional_values]:
        if re.fullmatch(r"[a-z0-9-]+", skill) is None:
            fail(f"invalid skill slug in {label}: {skill}")
        path = (SKILLS / skill / "SKILL.md").resolve()
        if not path.is_relative_to(skills_root) or not path.is_file():
            fail(f"missing or escaping skill in {label}: {skill}")
    return required_values, conditional_values


def _validate_procedures(value: object, *, label: str) -> list[str]:
    procedures = _canonical_list(value, label=label)
    for procedure in procedures:
        _resolve_root_file(procedure, label=label)
    return procedures


def _resolve_root_file(value: str, *, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        fail(f"escaping pointer in {label}: {value}")
    root = ROOT.resolve()
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        fail(f"missing or escaping pointer in {label}: {value}")
    return path


def _frontmatter_tools(path: Path) -> list[str]:
    raw = frontmatter(path).get("tools", "")
    if not raw.startswith("[") or not raw.endswith("]"):
        fail(f"agent tools must be an inline list: {path.relative_to(ROOT)}")
    parts = raw[1:-1].split(",")
    if not parts or any(not item.strip() for item in parts):
        fail(f"agent tools contain an empty token: {path.relative_to(ROOT)}")
    return _canonical_list(
        [item.strip() for item in parts],
        label=f"{path.relative_to(ROOT)}.tools",
    )


def _validate_role_contract_payload(contract: object) -> None:
    if not isinstance(contract, dict) or set(contract) != {
        "schemaVersion",
        "roles",
        "phaseEvents",
    }:
        fail("role contract top-level keys mismatch")
    if type(contract["schemaVersion"]) is not int or contract["schemaVersion"] != 3:
        fail("role contract schema version mismatch")
    roles = contract["roles"]
    events = contract["phaseEvents"]
    if not isinstance(roles, dict) or set(roles) != set(EXPECTED_ROLE_CONTRACTS):
        fail("role contract identity set mismatch")
    if not isinstance(events, dict) or set(events) != set(EXPECTED_PHASE_EVENTS):
        fail("phase event identity set mismatch")

    for role_name, expected in EXPECTED_ROLE_CONTRACTS.items():
        role = roles[role_name]
        label = f"roles.{role_name}"
        if not isinstance(role, dict) or set(role) != ROLE_KEYS:
            fail(f"role contract keys mismatch: {role_name}")
        agent_path = f"agents/{role_name}.agent.md"
        if role["agent"] != agent_path:
            fail(f"role agent pointer mismatch: {role_name}")
        agent_file = _resolve_root_file(role["agent"], label=f"{label}.agent")
        required, conditional = _validate_skill_set(
            role["requiredSkills"], role["conditionalSkills"], label=label
        )
        procedures = _validate_procedures(
            role["requiredProcedures"], label=f"{label}.requiredProcedures"
        )
        tools = _canonical_list(role["tools"], label=f"{label}.tools")
        if required != expected["requiredSkills"]:
            fail(f"required skill set mismatch: {role_name}")
        if conditional != expected["conditionalSkills"]:
            fail(f"conditional skill set mismatch: {role_name}")
        if procedures != expected["requiredProcedures"]:
            fail(f"required procedure set mismatch: {role_name}")
        if set(tools) != expected["tools"]:
            fail(f"role tool set mismatch: {role_name}")
        if set(_frontmatter_tools(agent_file)) != expected["tools"]:
            fail(f"agent frontmatter tool set mismatch: {role_name}")
        if type(role["writes"]) is not type(expected["writes"]):
            fail(f"role boundary type mismatch: {role_name}.writes")
        if type(role["delegates"]) is not bool:
            fail(f"role boundary type mismatch: {role_name}.delegates")
        if type(role["network"]) is not bool:
            fail(f"role boundary type mismatch: {role_name}.network")
        memory_actions = _canonical_list(
            role["memoryActions"], label=f"{label}.memoryActions"
        )
        if type(role["taskSpecificSkills"]) is not str:
            fail(f"role boundary type mismatch: {role_name}.taskSpecificSkills")
        for key in ("writes", "delegates", "network", "taskSpecificSkills"):
            if role[key] != expected[key]:
                fail(f"role boundary mismatch: {role_name}.{key}")
        if memory_actions != expected["memoryActions"]:
            fail(f"role boundary mismatch: {role_name}.memoryActions")

    for event_name, expected in EXPECTED_PHASE_EVENTS.items():
        event = events[event_name]
        label = f"phaseEvents.{event_name}"
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            fail(f"phase event keys mismatch: {event_name}")
        required, conditional = _validate_skill_set(
            event["requiredSkills"], event["conditionalSkills"], label=label
        )
        procedures = _validate_procedures(
            event["requiredProcedures"], label=f"{label}.requiredProcedures"
        )
        sequence = _canonical_list(event["sequence"], label=f"{label}.sequence")
        if (required, conditional, procedures, sequence) != expected:
            fail(f"phase event contract mismatch: {event_name}")
        if "approval" in sequence and "grill-me" in sequence:
            if sequence.index("grill-me") > sequence.index("approval"):
                fail(f"grill-me must precede approval: {event_name}")


def role_contract_failure_code(contract: object) -> str:
    try:
        _validate_role_contract_payload(contract)
    except ValueError as exc:
        message = str(exc)
        if "duplicate values in" in message and "Skills" in message:
            return "ROLE_SKILL_DUPLICATE"
        if "invalid skill slug" in message:
            return "ROLE_SKILL_ESCAPING"
        if "missing or escaping skill" in message:
            return "ROLE_SKILL_UNKNOWN"
        if "required skill set mismatch" in message:
            return "ROLE_SKILL_SET_MISMATCH"
        return "ROLE_CONTRACT_INVALID"
    return "PASS"


def validate_role_contracts() -> None:
    path = ROOT / "agents/role-contracts.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    _validate_role_contract_payload(contract)


def validate_agents() -> None:
    found = set()
    for path in sorted((ROOT / "agents").glob("*.agent.md")):
        metadata = frontmatter(path)
        name = metadata.get("name")
        if name != path.name.removesuffix(".agent.md"):
            fail(f"agent identity mismatch: {path.relative_to(ROOT)}")
        tools = metadata.get("tools", "")
        if "repowise" not in tools or "read" not in tools:
            fail(f"agent capability boundary missing: {path.relative_to(ROOT)}")
        body = path.read_text(encoding="utf-8")
        for target in re.findall(r"`((?:skills|instructions)/[^`]+)`", body):
            if not (ROOT / target).is_file():
                fail(
                    f"broken agent source pointer: {path.relative_to(ROOT)} -> {target}"
                )
        found.add(name)
    if found != REQUIRED_AGENTS:
        fail(
            f"specialist set mismatch: missing={sorted(REQUIRED_AGENTS - found)} extra={sorted(found - REQUIRED_AGENTS)}"
        )


def validate_prompt_and_instruction_schemas() -> None:
    for path in sorted((ROOT / "prompts").glob("*.md")):
        if not path.name.endswith(".prompt.md"):
            fail(f"prompt naming mismatch: {path.relative_to(ROOT)}")
        metadata = frontmatter(path)
        if not metadata.get("description") or "agent" in metadata:
            fail(f"prompt metadata mismatch: {path.relative_to(ROOT)}")
    for path in sorted((ROOT / "instructions").glob("*.md")):
        if not path.name.endswith(".instructions.md"):
            fail(f"instruction naming mismatch: {path.relative_to(ROOT)}")
        metadata = frontmatter(path)
        if metadata.get("applyTo") not in {"**", "'**'"}:
            fail(f"instruction applyTo mismatch: {path.relative_to(ROOT)}")

    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    if manifest.get("name") != "freighthero-agent-assets" or not manifest.get(
        "version"
    ):
        fail("Claude plugin manifest identity mismatch")
    hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
    expected_hooks = {
        "description": "Always-armed canonical auto-improvement check",
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'bash "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/auto-improvement-nudge.sh"',
                        }
                    ]
                }
            ]
        },
    }
    if hooks != expected_hooks:
        fail("Claude auto-improvement plugin hook contract mismatch")
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    if "hooks" in settings:
        fail("duplicate Claude project hooks are not allowed")
    hook_script = ROOT / ".claude/hooks/auto-improvement-nudge.sh"
    hook_text = hook_script.read_text(encoding="utf-8")
    required_hook_text = (
        "stop_hook_active",
        "auto-improvement skill bundled with the active",
        "FreightHero plugin",
        "explicit user approval",
        "never mirror installed host copies",
    )
    if not all(item in hook_text for item in required_hook_text):
        fail("Claude auto-improvement hook safety contract mismatch")
    if "~/.claude" in hook_text or "apply edit directly" in hook_text:
        fail("unsafe Claude auto-improvement hook behavior remains")
    mcp_path = ROOT / ".mcp.json"
    mcp_text = mcp_path.read_text(encoding="utf-8")
    if HARD_HOME.search(mcp_text):
        fail("hardcoded user home: .mcp.json")
    mcp = json.loads(mcp_text)
    server = mcp.get("mcpServers", {}).get("repowise", {})
    expected_keys = {"description", "headers", "type", "url"}
    if set(server) != expected_keys:
        fail("Repowise MCP pointer must declare one HTTP transport")
    if (
        server.get("type") != "http"
        or server.get("url") != "${REPOWISE_SERVICE_URL}/agent/mcp"
        or server.get("headers")
        != {"Authorization": "Bearer ${REPOWISE_ACCESS_TOKEN}"}
    ):
        fail("Repowise MCP HTTP pointer contract mismatch")

    vscode_mcp_path = ROOT / ".vscode/mcp.json"
    vscode_mcp = json.loads(vscode_mcp_path.read_text(encoding="utf-8"))
    vscode_server = vscode_mcp.get("servers", {}).get("repowise", {})
    if vscode_server != {
        "type": "http",
        "url": "${env:REPOWISE_SERVICE_URL}/agent/mcp",
        "headers": {"Authorization": "Bearer ${env:REPOWISE_ACCESS_TOKEN}"},
    }:
        fail("VS Code Repowise MCP pointer contract mismatch")

    for path in (mcp_path, vscode_mcp_path, ROOT / ".codex/config.toml"):
        text = path.read_text(encoding="utf-8")
        if "repowise" not in text.lower() or "REPOWISE_ACCESS_TOKEN" not in text:
            fail(f"protected Repowise pointer missing: {path.relative_to(ROOT)}")


def validate_active_text() -> None:
    hashes: dict[str, list[Path]] = defaultdict(list)
    for root in ACTIVE_ROOTS:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            data = path.read_bytes()
            if not data:
                fail(f"empty canonical asset: {path.relative_to(ROOT)}")
            text = data.decode("utf-8")
            if HARD_HOME.search(text):
                fail(f"hardcoded user home: {path.relative_to(ROOT)}")
            if SECRET.search(text):
                fail(f"literal secret: {path.relative_to(ROOT)}")
            if RETIRED.search(text):
                fail(f"retired active reference: {path.relative_to(ROOT)}")
            hashes[hashlib.sha256(data).hexdigest()].append(path)
    duplicates = [paths for paths in hashes.values() if len(paths) > 1]
    if duplicates:
        fail(
            "duplicate canonical hashes: "
            + ", ".join(str(p.relative_to(ROOT)) for p in duplicates[0])
        )


def validate_source_only() -> None:
    forbidden = [
        "main.go",
        "go.mod",
        "go.sum",
        "cmd",
        "internal",
        "dist",
        "build.sh",
        "build.ps1",
        "install.sh",
        "install.ps1",
        "freighthero-mcp",
    ]
    present = [item for item in forbidden if (ROOT / item).exists()]
    if present:
        fail(f"installable task runtime/distribution remains: {present}")
    if (ROOT / "skills" / "visual-explainer" / ".claude-plugin").exists():
        fail("nested plugin manifest remains")


def validate_hosts() -> None:
    fixtures = json.loads((ROOT / ".github/validation/host-fixtures.json").read_text())
    if not isinstance(fixtures, dict) or set(fixtures) != {
        "supported",
        "ineligible_profiles",
    }:
        fail("host fixture top-level schema drift")
    supported = fixtures["supported"]
    if not isinstance(supported, dict) or set(supported) != {
        "claude",
        "codex",
        "local-copilot",
    }:
        fail("supported host fixture set drift")
    host_keys = {
        "host",
        "model_loop",
        "canonical_source",
        "activation",
        "entry_skill",
        "conformance_mode",
        "hard_enforcement_claim",
        "capabilities",
    }
    for host, fixture in supported.items():
        if not isinstance(fixture, dict) or set(fixture) != host_keys:
            fail(f"host fixture schema drift: {host}")
        if (
            fixture.get("host") != host
            or fixture.get("model_loop") != "native"
            or fixture.get("canonical_source") != "coding-cli"
        ):
            fail(f"invalid native/source-only host fixture: {host}")
        if fixture.get("entry_skill") != "skills/freighthero-entry/SKILL.md":
            fail(f"entry skill drift: {host}")
        if fixture.get("activation") != HOST_ACTIVATIONS[host]:
            fail(f"host activation drift: {host}")
        if mutation_host_eligibility(fixture) != "PASS":
            fail(f"mutation review host capability unavailable: {host}")

    ineligible = fixtures["ineligible_profiles"]
    if not isinstance(ineligible, dict) or set(ineligible) != {
        "claude-no-reviewer-continuity"
    }:
        fail("ineligible host profile set drift")
    for name, profile in ineligible.items():
        if not isinstance(profile, dict) or set(profile) != {
            "base_host",
            "capability_overrides",
            "expected",
        }:
            fail(f"ineligible host profile schema drift: {name}")
        base = profile["base_host"]
        if base not in supported or not isinstance(
            profile["capability_overrides"], dict
        ):
            fail(f"ineligible host profile base drift: {name}")
        candidate = json.loads(json.dumps(supported[base]))
        candidate["capabilities"].update(profile["capability_overrides"])
        if mutation_host_eligibility(candidate) != profile["expected"]:
            fail(f"ineligible host profile does not fail closed: {name}")


def validate_conformance_fixtures() -> None:
    hosts = json.loads((ROOT / ".github/validation/host-fixtures.json").read_text())
    scenarios = json.loads(
        (ROOT / ".github/validation/host-scenarios.json").read_text()
    )
    negatives = json.loads(
        (ROOT / ".github/validation/negative-fixtures.json").read_text()
    )
    scenario_keys = {
        "supported_hosts",
        "task_classes",
        "required_prefix",
        "specialist_prefix",
        "blocking_freshness",
        "specialists",
        "mutation_review",
        "auto_improvement",
    }
    if not isinstance(scenarios, dict) or set(scenarios) != scenario_keys:
        fail("host scenario schema drift")
    if set(scenarios["supported_hosts"]) != set(hosts["supported"]):
        fail("host scenario supported set drift")
    if scenarios["task_classes"] != list(TASK_CLASSES):
        fail("host task class drift")
    if scenarios["required_prefix"] != list(ENTRY_PREFIX):
        fail("entry event prefix drift")
    if scenarios["specialist_prefix"] != list(SPECIALIST_PREFIX):
        fail("specialist event prefix drift")
    if set(scenarios["blocking_freshness"]) != BLOCKING_FRESHNESS:
        fail("blocking freshness state drift")
    if scenarios["specialists"] != SPECIALIST_BOUNDARIES:
        fail("specialist boundary drift")

    review = scenarios["mutation_review"]
    if not isinstance(review, dict) or set(review) != {
        "required_events",
        "ignored_artifact_kinds",
        "durable_artifact_kinds",
        "denied_reviewer_actions",
        "blocking_revisions",
        "positive_trace",
    }:
        fail("mutation review scenario schema drift")
    if review["required_events"] != list(MUTATION_EVENTS):
        fail("mutation review event contract drift")
    if set(review["ignored_artifact_kinds"]) != REVIEW_EXEMPT_KINDS:
        fail("mutation review recursion exemption drift")
    if set(review["durable_artifact_kinds"]) != REVIEW_REQUIRED_KINDS:
        fail("mutation review durable artifact drift")
    if set(review["denied_reviewer_actions"]) != REVIEWER_DENIED_ACTIONS:
        fail("mutation review reviewer prohibition drift")
    if review["blocking_revisions"] != 3:
        fail("mutation review blocker threshold drift")
    for host, profile in hosts["supported"].items():
        trace = json.loads(json.dumps(review["positive_trace"]))
        trace["host"] = host
        if evaluate_mutation_trace(trace, profile) != "PASS":
            fail(f"positive mutation trace failed: {host}")
        for name, auto_trace in scenarios["auto_improvement"].items():
            candidate = json.loads(json.dumps(auto_trace))
            if isinstance(candidate.get("mutation_trace"), dict):
                candidate["mutation_trace"]["host"] = host
            if evaluate_auto_improvement_trace(candidate, profile) != "PASS":
                fail(f"positive auto-improvement trace failed: {host}/{name}")

    negative_keys = {
        "skill_contract_mutations",
        "entry_trace_cases",
        "specialist_trace_cases",
        "specialist_tool_cases",
        "mutation_trace_mutations",
        "auto_improvement_mutations",
        "advisory_tool_cases",
        "escaping_skill_reference",
        "unknown_skill",
        "ambiguous_mutation",
        "undeclared_specialist_tool",
        "generated_canonical_copy",
        "unsupported_host",
        "installer_artifact",
    }
    if not isinstance(negatives, dict) or set(negatives) != negative_keys:
        fail("negative fixture schema drift")
    for key in (
        "skill_contract_mutations",
        "entry_trace_cases",
        "specialist_trace_cases",
        "specialist_tool_cases",
        "mutation_trace_mutations",
        "auto_improvement_mutations",
        "advisory_tool_cases",
    ):
        if not isinstance(negatives[key], list) or not negatives[key]:
            fail(f"negative fixture cases missing: {key}")
        identifiers = {
            item.get("id") for item in negatives[key] if isinstance(item, dict)
        }
        if identifiers != REQUIRED_NEGATIVE_IDS[key]:
            fail(f"negative fixture identity drift: {key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    for check in (
        validate_skills,
        validate_role_contracts,
        validate_agents,
        validate_prompt_and_instruction_schemas,
        validate_active_text,
        validate_source_only,
        validate_hosts,
        validate_conformance_fixtures,
    ):
        check()
    print("Source-only agent assets verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
