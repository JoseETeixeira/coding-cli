#!/usr/bin/env python3
"""Bind repository approval receipts to the current workspace Batman inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]
POLICIES = (
    WORKSPACE / "coding-cli/.github/governance/approved-inputs.json",
    WORKSPACE / "repowise-fork/.github/governance/approved-inputs.json",
)


def _sha256(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"approval input is not a regular file: {path}")
    resolved = path.resolve()
    if not resolved.is_relative_to(WORKSPACE.resolve()):
        raise SystemExit(f"approval input escapes workspace: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    receipts = []
    for policy_path in POLICIES:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        receipt = policy.get("current_amendment")
        if not isinstance(receipt, dict):
            raise SystemExit(f"missing current amendment receipt: {policy_path}")
        receipts.append(receipt)
    if receipts[0] != receipts[1]:
        raise SystemExit("repository approval receipts disagree")

    receipt = receipts[0]
    if receipt.get("task") != "freighthero-agent-platform-modernization":
        raise SystemExit("unexpected current amendment task")
    for kind in ("requirements", "design"):
        relative = receipt.get(f"{kind}_path")
        expected = receipt.get(f"{kind}_sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise SystemExit(f"malformed {kind} approval receipt")
        actual = _sha256(WORKSPACE / relative)
        if actual != expected:
            raise SystemExit(f"{kind} approval hash drift")
    print("workspace approval inputs verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
