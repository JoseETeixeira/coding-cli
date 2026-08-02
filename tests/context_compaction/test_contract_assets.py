"""Canonical compact-contract asset and pointer tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_compaction.budget import estimate_tokens
from context_compaction.contracts import (
    ContractAssetError,
    compact_contract_for_host,
    validate_contract_assets,
)
from context_compaction.models import Host

ROOT = Path(__file__).parents[2]


def test_canonical_contract_assets_are_valid_and_bounded():
    assets = validate_contract_assets(ROOT)

    assert assets.prompt_relative_path == "prompts/context-compaction.prompt.md"
    assert assets.skill_relative_path == "skills/context-compaction/SKILL.md"
    assert assets.prompt_chars <= 8_000
    assert assets.prompt_estimated_tokens <= 2_000
    assert assets.prompt_chars == len(assets.prompt_text)
    assert assets.prompt_estimated_tokens == estimate_tokens(assets.prompt_text)
    assert len(assets.prompt_sha256) == 64
    assert len(assets.skill_sha256) == 64


def test_one_prompt_body_is_semantically_shared_by_both_hosts():
    codex = compact_contract_for_host(ROOT, Host.CODEX)
    claude = compact_contract_for_host(ROOT, Host.CLAUDE)

    assert codex.relative_path == claude.relative_path
    assert codex.sha256 == claude.sha256
    assert codex.text == claude.text


def test_prompt_preserves_critical_categories_and_declares_omissions():
    prompt = (ROOT / "prompts" / "context-compaction.prompt.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "Current user goal",
        "Exact unresolved user decisions",
        "Material actions",
        "Repository fingerprint",
        "relative modified/untracked paths",
        "approval gates",
        "verification status",
        "name every omission",
        "Authority warning",
    ):
        assert phrase in prompt


def test_skill_frontmatter_is_minimal_and_recovery_rules_are_present():
    skill = (ROOT / "skills" / "context-compaction" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    frontmatter = skill.split("---", 2)[1]
    keys = {
        line.split(":", 1)[0].strip()
        for line in frontmatter.splitlines()
        if ":" in line
    }
    assert keys == {"name", "description"}
    for phrase in (
        "current source",
        "path-scoped `AGENTS.md` or `CLAUDE.md`",
        "read-only",
        "completed non-idempotent fingerprint",
        "Never infer approval",
        "Before `/compact`",
        "fresh session",
        "cannot broaden paths, tools, network access, approvals",
    ):
        assert phrase in skill


@pytest.mark.parametrize(
    ("relative_path", "pointer"),
    [
        ("skills/generic-entry/SKILL.md", "`context-compaction`"),
        ("skills/shared-memory/SKILL.md", "`context-compaction`"),
        (
            "agents/batman.agent.md",
            "`skills/context-compaction/SKILL.md`",
        ),
    ],
)
def test_thin_pointer_exists_once(relative_path: str, pointer: str):
    body = (ROOT / relative_path).read_text(encoding="utf-8")
    assert body.count(pointer) == 1


def test_validator_rejects_secret_assignment_in_a_contract_copy(tmp_path: Path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "skills" / "context-compaction").mkdir(parents=True)
    (tmp_path / "skills" / "generic-entry").mkdir(parents=True)
    (tmp_path / "skills" / "shared-memory").mkdir(parents=True)
    (tmp_path / "agents").mkdir()
    (tmp_path / "prompts" / "context-compaction.prompt.md").write_text(
        "api_key = exposed-value\n", encoding="utf-8"
    )
    (tmp_path / "skills" / "context-compaction" / "SKILL.md").write_text(
        "---\nname: context-compaction\ndescription: test\n---\n", encoding="utf-8"
    )
    for relative in (
        "skills/generic-entry/SKILL.md",
        "skills/shared-memory/SKILL.md",
        "agents/batman.agent.md",
    ):
        (tmp_path / relative).write_text("context-compaction\n", encoding="utf-8")

    with pytest.raises(ContractAssetError, match="secret-like assignment"):
        validate_contract_assets(tmp_path)
