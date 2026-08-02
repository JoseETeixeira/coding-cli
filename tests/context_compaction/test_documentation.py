"""Operator documentation stays aligned with the guarded pilot contract."""

from pathlib import Path

ROOT = Path(__file__).parents[2]
DOCS = ROOT / "docs" / "context-compaction"


def test_operator_document_set_and_open_gate_labels_are_explicit():
    expected = {"README.md", "compatibility.md", "troubleshooting.md", "rollback.md"}
    assert {path.name for path in DOCS.iterdir() if path.is_file()} == expected

    combined = "\n".join(
        (DOCS / name).read_text(encoding="utf-8") for name in sorted(expected)
    )
    for phrase in (
        "disabled by default",
        "Real user-level activation",
        "real host unmeasured",
        "owner acceptance",
        "context-pilot.config.toml",
        "claude-context-pilot.settings.json",
        "owned_file_drift",
        "fresh pointer-first handoff",
    ):
        assert phrase.casefold() in combined.casefold()


def test_readmes_changelog_and_evidence_index_do_not_claim_rollout_completion():
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    mnemo_readme = (ROOT / "mnemo" / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    evidence = (
        ROOT
        / ".batman"
        / "cross-host-context-compaction"
        / "spec"
        / "evidence"
        / "index.md"
    ).read_text(encoding="utf-8")

    assert "source presence is not activation" in " ".join(root_readme.casefold().split())
    assert "contract version 2" in mnemo_readme
    assert "No real user Codex or Claude Code configuration" in changelog
    assert "Task 10 exact real user-level activation preview" in evidence
    assert "owner acceptance remain separate" in " ".join(evidence.casefold().split())
