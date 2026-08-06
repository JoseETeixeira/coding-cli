#!/usr/bin/env python3
"""Validate canonical gamedev skill integration without mutating it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SKILL_NAMES = (
    "gamedev-workflow",
    "game-developer",
    "3d-modeling",
    "game-designer",
    "godot-genre-shooter-fps",
    "godot-particles",
    "godot-performance-optimization",
    "motion-design",
    "verify-3d-animation",
)
LOCAL_SKILL_NAMES = frozenset(
    {"gamedev-workflow", "game-designer", "verify-3d-animation"}
)
VENDORED_NAMES = tuple(
    name for name in SKILL_NAMES if name not in LOCAL_SKILL_NAMES
)
EXPECTED_SOURCES = {
    "game-developer": (
        "Jeffallan/claude-skills",
        "e8be415bc94d8d6ebddc2fb50e5d03c6e27d4319",
        "skills/game-developer",
    ),
    "3d-modeling": (
        "majiayu000/claude-skill-registry",
        "ef926663574f5f7a0c19b0429b2540373279ed45",
        "skills/data/3d-modeling",
    ),
    "godot-genre-shooter-fps": (
        "thedivergentai/GD-Agentic-Skills",
        "ebffc2b4f39b54dcf343b52dc9845a4ecc451cf2",
        "skills/godot-genre-shooter-fps",
    ),
    "godot-particles": (
        "thedivergentai/GD-Agentic-Skills",
        "ebffc2b4f39b54dcf343b52dc9845a4ecc451cf2",
        "skills/godot-particles",
    ),
    "godot-performance-optimization": (
        "thedivergentai/GD-Agentic-Skills",
        "ebffc2b4f39b54dcf343b52dc9845a4ecc451cf2",
        "skills/godot-performance-optimization",
    ),
    "motion-design": (
        "lottiefiles/motion-design-skill",
        "f9a8a041b85185ee4881b3471d3415e939aac772",
        "skills/motion-design",
    ),
}
EXPECTED_LICENSES = {
    "game-developer": (
        (
            "MIT",
            "LICENSE.upstream",
            "Jeffallan/claude-skills",
            "sha256:06dcddbb6908a0c6dd4a9e8ec822eea41d5a460a53089fecccc8a68049e99241",
        ),
    ),
    "3d-modeling": (
        (
            "Apache-2.0",
            "LICENSE.upstream",
            "omer-metin/skills-for-antigravity",
            "sha256:9b19b4bf2d7c6df1974e35c761c84f10f258d9fcab64a60c292b2752e81a9ec2",
        ),
        (
            "MIT",
            "LICENSE.registry",
            "majiayu000/claude-skill-registry",
            "sha256:6d5a74f51cfd9a94b89e38663a47ed1cc0173ecf640bbe4b21057cb2eb080830",
        ),
    ),
    "godot-genre-shooter-fps": (
        (
            "LGPL-3.0-only",
            "LICENSE.upstream",
            "thedivergentai/GD-Agentic-Skills",
            "sha256:e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118",
        ),
    ),
    "godot-particles": (
        (
            "LGPL-3.0-only",
            "LICENSE.upstream",
            "thedivergentai/GD-Agentic-Skills",
            "sha256:e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118",
        ),
    ),
    "godot-performance-optimization": (
        (
            "LGPL-3.0-only",
            "LICENSE.upstream",
            "thedivergentai/GD-Agentic-Skills",
            "sha256:e3a994d82e644b03a792a930f574002658412f62407f5fee083f2555c5f23118",
        ),
    ),
    "motion-design": (
        (
            "MIT",
            "LICENSE.upstream",
            "lottiefiles/motion-design-skill",
            "sha256:9fc2e8685daa09e28d54b6afa8a38f168417c5735a3cd676c80c159785e93a80",
        ),
    ),
}
EXPECTED_EXCLUDED_SOURCE = {
    "repository": "majiayu000/claude-skill-registry",
    "commit": "ef926663574f5f7a0c19b0429b2540373279ed45",
    "path": "skills/gaming/game-designer",
    "skill_file_sha256": "0a48d86b38632b75b003ac5925c1824d96c19da1d2151d45e4191023b08383eb",
    "metadata_file_sha256": "c249dd58d38642ff32faabaae4348fb9a0db394bd1f53467cb2479ae59787c3a",
}
EXPECTED_ROUTES = {
    "game-design": ("game-designer",),
    "game-implementation": ("game-developer",),
    "3d-modeling": ("3d-modeling", "verify-3d-animation"),
    "3d-rig-animation": ("verify-3d-animation",),
    "visible-animation": ("verify-3d-animation",),
    "godot-fps": ("godot-genre-shooter-fps",),
    "godot-fps-visible-animation": (
        "godot-genre-shooter-fps",
        "verify-3d-animation",
    ),
    "godot-particles": ("godot-particles", "verify-3d-animation"),
    "godot-performance": ("godot-performance-optimization",),
    "motion-design": ("motion-design", "verify-3d-animation"),
    "byond-compose": ("game-designer",),
    "byond-visible-animation": ("verify-3d-animation",),
    "cross-discipline": (
        "game-designer",
        "godot-particles",
        "motion-design",
        "verify-3d-animation",
    ),
    "non-game-animation": (),
}
REQUIRED_VERIFICATION_CASE_GATES = {
    "static-source-driven-3d-match": {
        "source-inspection",
        "comparable-capture",
        "gameplay-view",
        "transform-spaces",
        "reference-match",
    },
    "source-backed-first-person-pose": {
        "source-inspection",
        "comparable-capture",
        "gameplay-view",
        "transform-spaces",
        "skeleton-rest-pose",
        "first-person-occlusion",
        "deformation",
        "fail-closed",
    },
    "skeletal-loop-multi-frame": {
        "full-motion-discovery",
        "30-fps-schedule",
        "endpoints",
        "critical-frames",
        "per-frame-results",
        "temporal-continuity",
        "loop-seam",
        "fail-closed",
        "ready-for-owner-review",
    },
    "godot-fps-visible-animation": {
        "engine-version-check",
        "gameplay-view",
        "first-person-occlusion",
        "30-fps-schedule",
        "per-frame-results",
        "live-editor-verification",
        "owner-visual-acceptance",
    },
    "godot-particle-budget": {
        "renderer-version-check",
        "effect-budget",
        "reduced-effects",
        "30-fps-schedule",
        "per-frame-results",
        "owner-visual-acceptance",
    },
    "ui-motion-accessible": {
        "reduced-motion",
        "semantic-state",
        "30-fps-schedule",
        "per-frame-results",
        "owner-onscreen-acceptance",
    },
    "byond-visible-animation": {
        "byond-rag",
        "dream-maker",
        "project-verification",
        "30-fps-schedule",
        "per-frame-results",
    },
    "non-game-animation": {"scope-boundary", "no-implicit-verifier"},
    "gameplay-implementation": {"non-visual-verifier-omission"},
}
POINTER_FILES = (
    "AGENTS.md",
    "agents/batman.agent.md",
    "prompts/execute-task.prompt.md",
)
POINTER_TEXT = "skills/gamedev-workflow/SKILL.md"
POINTER_TRIGGER_MARKERS = (
    "3D models/transforms/rigs/poses",
    "visible game animation",
)
README_MARKER = "source-aligned model/animation verification"
ROUTER_REQUIRED_MARKERS = (
    "`verify-3d-animation`",
    "provided source",
    "comparable gameplay evidence",
    "more than one animation frame",
    "every scheduled/critical frame",
    "owner acceptance",
)
VERIFIER_FRONTMATTER_MARKERS = (
    "3d model",
    "transform",
    "rig",
    "skeleton",
    "pose",
    "deformation",
    "animation",
)
VERIFIER_REQUIRED_MARKERS = (
    "supplied or project-authoritative source material",
    "comparable capture",
    "object, local, world, import, skeleton-rest, bone-pose, root-motion, and camera spaces",
    "elbow and biceps",
    "skinning and deformation",
    "max(2, ceil(source_frame_count / 30))",
    "contact, extreme, passing, transition, blend, loop-seam, and known-risk",
    "verify every captured frame",
    "evidence ledger",
    "ready for owner review",
    "repository/static, dcc/export, engine import, runtime/windowed, reference-match, per-frame/temporal, accessibility, owner, and release",
)
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
NAME_PATTERN = re.compile(r"(?m)^name:\s*['\"]?([^'\"\r\n]+)")
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.checks = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.errors.append(message)


def load_json(path: Path, validation: Validation) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        validation.errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    validation.require(isinstance(data, dict), f"{path}: root must be an object")
    return data if isinstance(data, dict) else {}


def resolve_contained(
    root: Path, candidate: Path, validation: Validation, label: str
) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    validation.require(
        resolved == resolved_root or resolved_root in resolved.parents,
        f"{label}: path escapes {resolved_root}: {resolved}",
    )
    return resolved


def frontmatter_name(path: Path, validation: Validation) -> str | None:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        validation.errors.append(f"{path}: unreadable: {exc}")
        return None
    match = FRONTMATTER_PATTERN.match(content)
    validation.require(match is not None, f"{path}: missing valid YAML frontmatter")
    if not match:
        return None
    name_match = NAME_PATTERN.search(match.group(1))
    validation.require(name_match is not None, f"{path}: missing frontmatter name")
    return name_match.group(1).strip() if name_match else None


def validate_router_content(repo_root: Path, validation: Validation) -> None:
    path = repo_root / "skills/gamedev-workflow/SKILL.md"
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        validation.errors.append(f"{path}: unreadable: {exc}")
        return
    lowered = content.lower()
    for marker in ROUTER_REQUIRED_MARKERS:
        validation.require(
            marker.lower() in lowered,
            f"{path}: missing verifier routing marker {marker!r}",
        )


def validate_verifier_content(skills_root: Path, validation: Validation) -> None:
    skill_dir = skills_root / "verify-3d-animation"
    skill_path = skill_dir / "SKILL.md"
    metadata_path = skill_dir / "agents/openai.yaml"
    if not skill_path.is_file():
        validation.require(False, f"missing verifier skill: {skill_path}")
        return

    try:
        content = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        validation.errors.append(f"{skill_path}: unreadable: {exc}")
        return

    validation.require(
        len(content.splitlines()) < 500,
        f"{skill_path}: skill must remain below 500 lines",
    )
    frontmatter = FRONTMATTER_PATTERN.match(content)
    validation.require(frontmatter is not None, f"{skill_path}: invalid frontmatter")
    frontmatter_text = frontmatter.group(1).lower() if frontmatter else ""
    for marker in VERIFIER_FRONTMATTER_MARKERS:
        validation.require(
            marker in frontmatter_text,
            f"{skill_path}: frontmatter missing trigger {marker!r}",
        )

    lowered = content.lower()
    for marker in VERIFIER_REQUIRED_MARKERS:
        validation.require(
            marker.lower() in lowered,
            f"{skill_path}: missing verification contract marker {marker!r}",
        )

    validation.require(metadata_path.is_file(), f"missing metadata: {metadata_path}")
    if metadata_path.is_file():
        try:
            metadata = metadata_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            validation.errors.append(f"{metadata_path}: unreadable: {exc}")
        else:
            expected_metadata = [
                "interface:",
                '  display_name: "Verify 3D Animation"',
                '  short_description: "Verify source fidelity across animation frames"',
                '  default_prompt: "Use $verify-3d-animation to compare this game model or animation with its source and verify every required frame before completion."',
            ]
            validation.require(
                metadata.splitlines() == expected_metadata,
                f"{metadata_path}: interface metadata must match the approved contract",
            )

    actual_files = {
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_file()
    }
    validation.require(
        actual_files == {"SKILL.md", "agents/openai.yaml"},
        f"{skill_dir}: unexpected skill files {sorted(actual_files)}",
    )


def markdown_files(skills_root: Path) -> list[Path]:
    files: list[Path] = []
    for name in SKILL_NAMES:
        files.extend((skills_root / name).glob("**/*.md"))
    return sorted(path for path in files if path.is_file())


def validate_links(skills_root: Path, validation: Validation) -> None:
    for path in markdown_files(skills_root):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            validation.errors.append(f"{path}: unreadable: {exc}")
            continue
        for raw_target in LINK_PATTERN.findall(content):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = target.split("#", 1)[0]
            candidate = resolve_contained(
                skills_root, path.parent / target, validation, f"{path} link"
            )
            validation.require(
                candidate.exists(), f"{path}: dangling relative link {raw_target}"
            )


def validate_upstream(skill_dir: Path, validation: Validation) -> None:
    path = skill_dir / "UPSTREAM.json"
    validation.require(path.is_file(), f"{path}: missing")
    if not path.is_file():
        return
    data = load_json(path, validation)
    validation.require(data.get("schema_version") == 1, f"{path}: schema_version must be 1")
    validation.require(data.get("skill") == skill_dir.name, f"{path}: skill mismatch")
    source = data.get("source")
    validation.require(isinstance(source, dict), f"{path}: source must be object")
    if isinstance(source, dict):
        validation.require(bool(source.get("repository")), f"{path}: repository missing")
        validation.require(bool(source.get("path")), f"{path}: source path missing")
        validation.require(
            bool(COMMIT_PATTERN.fullmatch(str(source.get("commit", "")))),
            f"{path}: invalid commit",
        )
        expected_source = EXPECTED_SOURCES[skill_dir.name]
        validation.require(
            tuple(source.get(key) for key in ("repository", "commit", "path"))
            == expected_source,
            f"{path}: source does not match approved pin",
        )
    origin_chain = data.get("origin_chain")
    validation.require(
        isinstance(origin_chain, list), f"{path}: origin_chain must be array"
    )
    if skill_dir.name == "3d-modeling" and isinstance(origin_chain, list):
        validation.require(len(origin_chain) == 1, f"{path}: origin chain mismatch")
        if len(origin_chain) == 1 and isinstance(origin_chain[0], dict):
            expected_origin = (
                "omer-metin/skills-for-antigravity",
                "e8dcf4e8737921a10088bd5c9eb65e81f74c051f",
                "skills/3d-modeling",
            )
            validation.require(
                tuple(
                    origin_chain[0].get(key)
                    for key in ("repository", "commit", "path")
                )
                == expected_origin,
                f"{path}: 3D content origin mismatch",
            )
    elif isinstance(origin_chain, list):
        validation.require(origin_chain == [], f"{path}: unexpected origin chain")
    upstream_files = data.get("upstream_files")
    validation.require(
        isinstance(upstream_files, dict) and bool(upstream_files),
        f"{path}: upstream_files missing",
    )
    adapted_files: set[str] = set()
    adaptations = data.get("adaptations")
    validation.require(
        isinstance(adaptations, list),
        f"{path}: adaptations must be array",
    )
    if isinstance(adaptations, list):
        for record in adaptations:
            validation.require(
                isinstance(record, dict), f"{path}: invalid adaptation record"
            )
            if isinstance(record, dict):
                relative = str(record.get("file", ""))
                validation.require(
                    bool(relative) and relative not in adapted_files,
                    f"{path}: missing/duplicate adapted file {relative!r}",
                )
                adapted_files.add(relative)
                validation.require(
                    bool(str(record.get("kind", "")).strip())
                    and bool(str(record.get("reason", "")).strip()),
                    f"{path}: adaptation {relative!r} needs kind and reason",
                )
    modified_files: set[str] = set()
    if isinstance(upstream_files, dict):
        for relative, digest in upstream_files.items():
            parts = Path(relative).parts
            validation.require(
                bool(relative) and not Path(relative).is_absolute() and ".." not in parts,
                f"{path}: unsafe upstream path {relative}",
            )
            validation.require(
                bool(SHA256_PATTERN.fullmatch(str(digest))),
                f"{path}: invalid SHA-256 for {relative}",
            )
            current = skill_dir / relative
            resolve_contained(skill_dir, current, validation, f"{path} upstream file")
            validation.require(current.is_file(), f"{path}: missing upstream file {relative}")
            if current.is_file():
                current_digest = "sha256:" + hashlib.sha256(current.read_bytes()).hexdigest()
                if current_digest != digest:
                    modified_files.add(relative)
    validation.require(
        modified_files == adapted_files,
        f"{path}: modified files {sorted(modified_files)} do not match adaptations {sorted(adapted_files)}",
    )
    local_only = data.get("local_only")
    validation.require(isinstance(local_only, list), f"{path}: local_only must be array")
    if isinstance(local_only, list) and isinstance(upstream_files, dict):
        declared_local = set(str(item) for item in local_only)
        current_files = {
            item.relative_to(skill_dir).as_posix()
            for item in skill_dir.rglob("*")
            if item.is_file()
        }
        actual_local = current_files - set(upstream_files)
        validation.require(
            actual_local == declared_local,
            f"{path}: local-only files {sorted(actual_local)} do not match manifest {sorted(declared_local)}",
        )
    licenses = data.get("licenses")
    validation.require(
        isinstance(licenses, list) and bool(licenses), f"{path}: licenses missing"
    )
    if isinstance(licenses, list):
        expected_licenses = EXPECTED_LICENSES[skill_dir.name]
        validation.require(
            len(licenses) == len(expected_licenses),
            f"{path}: license record count mismatch",
        )
        for index, record in enumerate(licenses):
            validation.require(isinstance(record, dict), f"{path}: invalid license record")
            if not isinstance(record, dict):
                continue
            if index < len(expected_licenses):
                validation.require(
                    tuple(
                        record.get(key)
                        for key in ("spdx", "file", "source", "sha256")
                    )
                    == expected_licenses[index],
                    f"{path}: license record {index} does not match approved source",
                )
            license_file = skill_dir / str(record.get("file", ""))
            resolve_contained(skill_dir, license_file, validation, f"{path} license")
            validation.require(
                license_file.is_file() and license_file.stat().st_size > 0,
                f"{path}: missing license file {license_file.name}",
            )
            expected_digest = str(record.get("sha256", ""))
            validation.require(
                bool(SHA256_PATTERN.fullmatch(expected_digest)),
                f"{path}: invalid license SHA-256 for {license_file.name}",
            )
            if license_file.is_file() and SHA256_PATTERN.fullmatch(expected_digest):
                current_digest = (
                    "sha256:" + hashlib.sha256(license_file.read_bytes()).hexdigest()
                )
                validation.require(
                    current_digest == expected_digest,
                    f"{path}: license SHA-256 mismatch for {license_file.name}",
                )


def validate_origin(
    repo_root: Path, skill_dir: Path, validation: Validation
) -> None:
    path = skill_dir / "ORIGIN.json"
    validation.require(path.is_file(), f"{path}: missing")
    if not path.is_file():
        return
    data = load_json(path, validation)
    validation.require(data.get("schema_version") == 1, f"{path}: schema_version must be 1")
    validation.require(data.get("skill") == "game-designer", f"{path}: skill mismatch")
    validation.require(
        data.get("authorship") == "clean-room-canonical", f"{path}: authorship mismatch"
    )
    validation.require(
        data.get("basis") == ["approved requirements", "general game-design knowledge"],
        f"{path}: invalid authorship basis",
    )
    excluded = data.get("excluded_source")
    validation.require(isinstance(excluded, dict), f"{path}: excluded_source must be object")
    if isinstance(excluded, dict):
        validation.require(
            bool(COMMIT_PATTERN.fullmatch(str(excluded.get("commit", "")))),
            f"{path}: invalid excluded commit",
        )
        validation.require(
            "restricted" in str(excluded.get("reason", "")).lower(),
            f"{path}: restriction reason missing",
        )
        for key, expected in EXPECTED_EXCLUDED_SOURCE.items():
            validation.require(
                excluded.get(key) == expected,
                f"{path}: excluded {key} does not match approved evidence",
            )
    evidence_relative = str(data.get("comparison_evidence", ""))
    validation.require(
        evidence_relative
        == ".batman/gamedev-skills-workflow/evidence/game-designer-overlap.json",
        f"{path}: comparison evidence path mismatch",
    )
    evidence_path = resolve_contained(
        repo_root,
        repo_root / evidence_relative,
        validation,
        f"{path} comparison evidence",
    )
    validation.require(evidence_path.is_file(), f"{evidence_path}: missing")
    if not evidence_path.is_file():
        return

    evidence = load_json(evidence_path, validation)
    validation.require(
        evidence.get("schema_version") == 1,
        f"{evidence_path}: schema_version must be 1",
    )
    local = evidence.get("local")
    validation.require(
        isinstance(local, dict), f"{evidence_path}: local must be object"
    )
    if isinstance(local, dict):
        skill_file = skill_dir / "SKILL.md"
        current_digest = hashlib.sha256(skill_file.read_bytes()).hexdigest()
        validation.require(
            local.get("path") == "skills/game-designer/SKILL.md",
            f"{evidence_path}: local path mismatch",
        )
        validation.require(
            local.get("sha256") == current_digest,
            f"{evidence_path}: stale local SHA-256",
        )
        validation.require(
            isinstance(local.get("normalized_token_count"), int)
            and local.get("normalized_token_count", 0) > 0,
            f"{evidence_path}: invalid local token count",
        )

    compared_source = evidence.get("excluded_source")
    validation.require(
        isinstance(compared_source, dict),
        f"{evidence_path}: excluded_source must be object",
    )
    if isinstance(compared_source, dict) and isinstance(excluded, dict):
        for key in ("repository", "commit"):
            validation.require(
                compared_source.get(key) == excluded.get(key),
                f"{evidence_path}: excluded {key} mismatch",
            )
        validation.require(
            compared_source.get("path") == f"{excluded.get('path')}/SKILL.md",
            f"{evidence_path}: excluded path mismatch",
        )
        validation.require(
            compared_source.get("sha256") == excluded.get("skill_file_sha256"),
            f"{evidence_path}: excluded skill hash mismatch",
        )
        validation.require(
            compared_source.get("metadata_sha256")
            == excluded.get("metadata_file_sha256"),
            f"{evidence_path}: excluded metadata hash mismatch",
        )
        validation.require(
            compared_source.get("content_retained_in_repository") is False,
            f"{evidence_path}: excluded content retention must be false",
        )

    method = evidence.get("method")
    result = evidence.get("result")
    validation.require(
        isinstance(method, dict), f"{evidence_path}: method must be object"
    )
    validation.require(
        isinstance(result, dict), f"{evidence_path}: result must be object"
    )
    if isinstance(method, dict) and isinstance(result, dict):
        threshold = method.get("fail_threshold_words")
        maximum = result.get("maximum_contiguous_match_words")
        validation.require(
            isinstance(threshold, int) and threshold > 0,
            f"{evidence_path}: invalid overlap threshold",
        )
        validation.require(
            isinstance(maximum, int)
            and isinstance(threshold, int)
            and maximum < threshold,
            f"{evidence_path}: overlap threshold failed",
        )
        validation.require(
            result.get("exact_copy") is False
            and result.get("failing_runs_12_or_more") == []
            and result.get("status") == "pass",
            f"{evidence_path}: clean-room result failed",
        )


def validate_routing(repo_root: Path, validation: Validation) -> None:
    path = repo_root / "skills/gamedev-workflow/references/routing-cases.json"
    data = load_json(path, validation)
    validation.require(data.get("schema_version") == 1, f"{path}: schema_version must be 1")
    cases = data.get("cases")
    validation.require(
        isinstance(cases, list) and len(cases) >= 16,
        f"{path}: expected at least 16 routing cases",
    )
    if not isinstance(cases, list):
        return
    ids: set[str] = set()
    seen_routes: set[str] = set()
    for case in cases:
        validation.require(isinstance(case, dict), f"{path}: each case must be object")
        if not isinstance(case, dict):
            continue
        case_id_value = case.get("id")
        validation.require(
            isinstance(case_id_value, str), f"{path}: case id must be string"
        )
        case_id = case_id_value if isinstance(case_id_value, str) else ""
        validation.require(
            bool(case_id) and case_id not in ids,
            f"{path}: missing/duplicate case id {case_id!r}",
        )
        ids.add(case_id)
        route_value = case.get("route")
        validation.require(
            isinstance(route_value, str), f"{path}: {case_id} route must be string"
        )
        route = route_value if isinstance(route_value, str) else ""
        seen_routes.add(route)
        validation.require(route in EXPECTED_ROUTES, f"{path}: unknown route {route!r}")
        expected = EXPECTED_ROUTES.get(route)
        primary_skills = case.get("primary_skills")
        validation.require(
            isinstance(primary_skills, list)
            and all(isinstance(item, str) for item in primary_skills),
            f"{path}: {case_id} primary_skills must be a string array",
        )
        if expected is not None and isinstance(primary_skills, list):
            validation.require(
                tuple(primary_skills) == expected,
                f"{path}: {case_id} primary skill mismatch",
            )
        task = case.get("task")
        validation.require(
            isinstance(task, str) and bool(task.strip()),
            f"{path}: {case_id} task missing",
        )
        existing_skills = case.get("existing_skills")
        validation.require(
            isinstance(existing_skills, list)
            and all(isinstance(item, str) for item in existing_skills),
            f"{path}: {case_id} existing_skills must be a string array",
        )
        specialist = case.get("specialist")
        validation.require(
            specialist is None or isinstance(specialist, str),
            f"{path}: {case_id} specialist must be string or null",
        )
        required_gates = case.get("required_gates")
        validation.require(
            isinstance(required_gates, list)
            and bool(required_gates)
            and all(isinstance(item, str) for item in required_gates),
            f"{path}: {case_id} gates missing",
        )
    validation.require(
        set(EXPECTED_ROUTES).issubset(seen_routes),
        f"{path}: missing routes {sorted(set(EXPECTED_ROUTES) - seen_routes)}",
    )
    by_id = {
        str(case.get("id")): case for case in cases if isinstance(case, dict)
    }
    for case_id, expected_gates in REQUIRED_VERIFICATION_CASE_GATES.items():
        case = by_id.get(case_id)
        validation.require(case is not None, f"{path}: required case {case_id!r} missing")
        if isinstance(case, dict):
            required_gates = case.get("required_gates")
            if not (
                isinstance(required_gates, list)
                and all(isinstance(item, str) for item in required_gates)
            ):
                continue
            actual_gates = set(required_gates)
            validation.require(
                expected_gates.issubset(actual_gates),
                f"{path}: {case_id} missing gates {sorted(expected_gates - actual_gates)}",
            )
    conflict = next(
        (
            case
            for case in cases
            if isinstance(case, dict)
            and case.get("id") == "godot-fps-version-conflict"
        ),
        None,
    )
    validation.require(conflict is not None, f"{path}: version conflict case missing")
    if isinstance(conflict, dict):
        required_gates = conflict.get("required_gates")
        if isinstance(required_gates, list) and all(
            isinstance(item, str) for item in required_gates
        ):
            gates = set(required_gates)
            validation.require(
                {
                    "engine-version-check",
                    "project-source-wins",
                    "conceptual-only-on-conflict",
                }.issubset(gates),
                f"{path}: version conflict precedence gates missing",
            )


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_idempotence(skills_root: Path, validation: Validation) -> None:
    before = {name: tree_hash(skills_root / name) for name in SKILL_NAMES}
    plan = {
        name: "skip-existing" if (skills_root / name).exists() else "install"
        for name in SKILL_NAMES
    }
    validation.require(
        all(action == "skip-existing" for action in plan.values()),
        f"second-install plan would mutate: {plan}",
    )
    after = {name: tree_hash(skills_root / name) for name in SKILL_NAMES}
    validation.require(before == after, "read-only idempotence simulation changed hashes")


def validate_host_duplicates(skills_root: Path, validation: Validation) -> None:
    host_roots = (
        Path.home() / ".codex/skills",
        Path.home() / ".agents/skills",
        Path.home() / ".claude/skills",
    )
    canonical = skills_root.resolve()
    for host_root in host_roots:
        if host_root.resolve() == canonical:
            continue
        for name in SKILL_NAMES:
            validation.require(
                not (host_root / name).exists(), f"host mirror exists: {host_root / name}"
            )


def validate(repo_root: Path) -> Validation:
    validation = Validation()
    repo_root = repo_root.resolve()
    skills_root = resolve_contained(repo_root, repo_root / "skills", validation, "skills root")
    for name in SKILL_NAMES:
        skill_dir = resolve_contained(
            skills_root, skills_root / name, validation, f"skill {name}"
        )
        validation.require(skill_dir.is_dir(), f"missing skill directory: {skill_dir}")
        skill_file = skill_dir / "SKILL.md"
        validation.require(skill_file.is_file(), f"missing SKILL.md: {skill_file}")
        if skill_file.is_file():
            validation.require(
                frontmatter_name(skill_file, validation) == name,
                f"{skill_file}: name must be {name}",
            )

    validate_links(skills_root, validation)
    for name in VENDORED_NAMES:
        if (skills_root / name).is_dir():
            validate_upstream(skills_root / name, validation)
    if (skills_root / "game-designer").is_dir():
        validate_origin(repo_root, skills_root / "game-designer", validation)
    validate_router_content(repo_root, validation)
    validate_verifier_content(skills_root, validation)
    validate_routing(repo_root, validation)
    if all((skills_root / name).is_dir() for name in SKILL_NAMES):
        validate_idempotence(skills_root, validation)
    validate_host_duplicates(skills_root, validation)

    for relative in POINTER_FILES:
        path = repo_root / relative
        validation.require(path.is_file(), f"pointer file missing: {path}")
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            validation.require(
                content.count(POINTER_TEXT) == 1,
                f"{path}: expected one thin gamedev pointer",
            )
            for marker in POINTER_TRIGGER_MARKERS:
                validation.require(
                    marker in content,
                    f"{path}: missing gamedev trigger marker {marker!r}",
                )

    readme_path = repo_root / "README.md"
    validation.require(readme_path.is_file(), f"README missing: {readme_path}")
    if readme_path.is_file():
        readme = readme_path.read_text(encoding="utf-8")
        validation.require(
            README_MARKER in readme,
            f"{readme_path}: missing verifier discovery marker {README_MARKER!r}",
        )
    validation.require(
        (repo_root / "skills/byond-projects/SKILL.md").is_file(),
        "existing BYOND routing target no longer resolves",
    )
    return validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    args = parser.parse_args()
    result = validate(args.repo_root)
    if result.errors:
        print(f"FAIL: {len(result.errors)} error(s), {result.checks} checks")
        for error in result.errors:
            print(f"- {error}")
        return 1
    print(f"PASS: gamedev integration ({result.checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
