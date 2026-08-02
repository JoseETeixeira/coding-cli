"""Validation and host-neutral loading for canonical compaction assets."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .budget import DEFAULT_REENTRY_CHARS, DEFAULT_REENTRY_TOKENS, estimate_tokens
from .models import Host

PROMPT_RELATIVE_PATH = "prompts/context-compaction.prompt.md"
SKILL_RELATIVE_PATH = "skills/context-compaction/SKILL.md"
_MAX_ASSET_BYTES = 64 * 1024
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:api[_-]?key|access[_-]?token|password|secret|bearer)\s*[:=]\s*\S+"
)
_POINTERS = {
    "skills/generic-entry/SKILL.md": "`context-compaction`",
    "skills/shared-memory/SKILL.md": "`context-compaction`",
    "agents/batman.agent.md": "`skills/context-compaction/SKILL.md`",
}


class ContractAssetError(ValueError):
    pass


@dataclass(frozen=True)
class ContractAssets:
    prompt_relative_path: str
    skill_relative_path: str
    prompt_text: str
    prompt_chars: int
    prompt_estimated_tokens: int
    prompt_sha256: str
    skill_sha256: str


@dataclass(frozen=True)
class HostCompactContract:
    host: Host
    relative_path: str
    text: str
    sha256: str


def validate_contract_assets(repository_root: str | Path) -> ContractAssets:
    root = Path(repository_root).resolve(strict=True)
    if not root.is_dir():
        raise ContractAssetError("contract root is not a directory")

    prompt_path = _safe_asset(root, PROMPT_RELATIVE_PATH)
    skill_path = _safe_asset(root, SKILL_RELATIVE_PATH)
    prompt = _read_asset(prompt_path)
    skill = _read_asset(skill_path)

    prompt_chars = len(prompt)
    prompt_tokens = estimate_tokens(prompt)
    if prompt_chars > DEFAULT_REENTRY_CHARS:
        raise ContractAssetError("compact prompt exceeds character budget")
    if prompt_tokens > DEFAULT_REENTRY_TOKENS:
        raise ContractAssetError("compact prompt exceeds estimated-token budget")
    for name, body in (("prompt", prompt), ("skill", skill)):
        if _SECRET_ASSIGNMENT.search(body):
            raise ContractAssetError(f"secret-like assignment in {name}")

    _validate_skill_frontmatter(skill)
    for relative_path, pointer in _POINTERS.items():
        body = _read_asset(_safe_asset(root, relative_path))
        if body.count(pointer) != 1:
            raise ContractAssetError(f"missing or duplicated compact pointer in {relative_path}")

    return ContractAssets(
        prompt_relative_path=PROMPT_RELATIVE_PATH,
        skill_relative_path=SKILL_RELATIVE_PATH,
        prompt_text=prompt,
        prompt_chars=prompt_chars,
        prompt_estimated_tokens=prompt_tokens,
        prompt_sha256=_sha256(prompt),
        skill_sha256=_sha256(skill),
    )


def compact_contract_for_host(
    repository_root: str | Path, host: Host
) -> HostCompactContract:
    if not isinstance(host, Host):
        raise ContractAssetError("unsupported compact-contract host")
    assets = validate_contract_assets(repository_root)
    return HostCompactContract(
        host=host,
        relative_path=assets.prompt_relative_path,
        text=assets.prompt_text,
        sha256=assets.prompt_sha256,
    )


def _safe_asset(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve(strict=True)
    if not path.is_file() or not path.is_relative_to(root):
        raise ContractAssetError(f"unsafe or missing contract asset: {relative_path}")
    return path


def _read_asset(path: Path) -> str:
    if path.stat().st_size > _MAX_ASSET_BYTES:
        raise ContractAssetError("contract asset is oversized")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractAssetError("contract asset is unreadable UTF-8") from exc


def _validate_skill_frontmatter(skill: str) -> None:
    if not skill.startswith("---\n"):
        raise ContractAssetError("skill frontmatter is missing")
    parts = skill.split("---", 2)
    if len(parts) != 3:
        raise ContractAssetError("skill frontmatter is malformed")
    fields: dict[str, str] = {}
    for line in parts[1].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ContractAssetError("skill frontmatter is malformed")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    if set(fields) != {"name", "description"}:
        raise ContractAssetError("skill frontmatter must contain only name and description")
    if fields["name"] != "context-compaction" or not fields["description"]:
        raise ContractAssetError("skill frontmatter values are invalid")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
