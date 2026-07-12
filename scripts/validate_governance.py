#!/usr/bin/env python3
"""Dependency-free governance checks for coding-cli source assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR_ROOT = ROOT / "docs" / "architecture" / "adr"
POLICY = ROOT / ".github" / "governance" / "approved-inputs.json"
MANIFEST = ROOT / ".github" / "governance" / "accepted-adr-core-sha256.json"
CORE_HEADINGS = {"status", "context", "decision", "alternatives", "consequences"}


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"missing frontmatter: {path.relative_to(ROOT)}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SystemExit(f"unterminated frontmatter: {path.relative_to(ROOT)}")
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip('"')
    return result


def core_hash(path: Path) -> str:
    sections: list[str] = []
    heading: str | None = None
    body: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if heading in CORE_HEADINGS:
                sections.append(f"## {heading}\n" + "\n".join(body).strip())
            heading = match.group(1).strip().lower()
            body = []
        elif heading is not None:
            body.append(line.rstrip())
    if heading in CORE_HEADINGS:
        sections.append(f"## {heading}\n" + "\n".join(body).strip())
    if not sections:
        raise SystemExit(f"accepted ADR has no core: {path.relative_to(ROOT)}")
    return hashlib.sha256(("\n\n".join(sections) + "\n").encode()).hexdigest()


def accepted_manifest() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): core_hash(path)
        for path in sorted(ADR_ROOT.glob("[0-9][0-9][0-9][0-9]-*.md"))
        if frontmatter(path).get("status") == "Accepted"
    }


def validate_links(path: Path) -> None:
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        clean = target.split("#", 1)[0]
        if not clean or "://" in clean or clean.startswith("mailto:"):
            continue
        if not (path.parent / clean).resolve().is_file():
            raise SystemExit(f"broken link in {path.relative_to(ROOT)}: {target}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-manifest", action="store_true")
    args = parser.parse_args()
    if args.print_manifest:
        print(json.dumps(accepted_manifest(), indent=2, sort_keys=True))
        return 0

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    records = sorted(ADR_ROOT.glob("[0-9][0-9][0-9][0-9]-*.md"))
    ids = [path.name[:4] for path in records]
    duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise SystemExit(f"duplicate ADR IDs: {duplicates}")

    governed = records + sorted((ROOT / "docs" / "product").glob("*.md"))
    for path in governed:
        metadata = frontmatter(path)
        if not metadata.get("status"):
            raise SystemExit(f"missing lifecycle status: {path.relative_to(ROOT)}")
        if metadata.get("task") == policy["task"]:
            for key in ("requirements_sha256", "design_sha256"):
                if metadata.get(key) != policy[key]:
                    raise SystemExit(f"approval hash drift in {path.relative_to(ROOT)}: {key}")
        validate_links(path)

    if accepted_manifest() != json.loads(MANIFEST.read_text(encoding="utf-8")):
        raise SystemExit("accepted ADR core drift; add a superseding ADR")
    print("coding-cli governance verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

