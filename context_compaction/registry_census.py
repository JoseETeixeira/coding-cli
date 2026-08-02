"""Read-only census of Claude's host registry. Prints; never writes, never launches.

Three guarded cells rejected `registry_semantic_drift` about 1.05 s after child start,
and ADR 0014's diagnostics narrowed that to the closed category `feature_state` without
retaining field identity. This answers the remaining question from the *outside*: while
the owner starts Claude natively, which protected top-level fields actually move, and
would the ADR 0013 guard have rejected each start?

It exists to make the next Task 10 decision evidence-backed rather than inferred. It
activates nothing, writes nothing, and launches nothing -- the owner drives the host.

Deliberately reuses `claude_registry`'s own helpers rather than reimplementing them, so
a clean census here means the guard would also have been clean. It is the one place that
prints raw field names: ADR 0014 bounds what the *guard persists* into events, status,
and state, and this persists nothing at all.

    py -3.12 -m context_compaction.registry_census --duration 120

Then start Claude natively in another terminal and exit it. Repeat with the lever:

    set DISABLE_GROWTHBOOK=1     (cmd)     $env:DISABLE_GROWTHBOOK=1   (PowerShell)
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .claude_registry import (
    ClaudeRegistryError,
    _canonical_sha256,
    _field_category,
    _matching_project_keys,
    _protected_field_fingerprints,
    _protected_value,
    _read_registry,
    _registry_fields,
)

_EXEMPT_NOTE = "exempt by ADR 0013 (numStartups, target project subtree)"


def _snapshot(registry: Path, repository_key: str) -> tuple[str, dict[str, str], int]:
    """Protected semantic hash, per-field fingerprints, and numStartups."""
    value, _byte_count, _content_sha256 = _read_registry(registry)
    num_startups, projects = _registry_fields(value)
    matches = _matching_project_keys(projects, repository_key) if repository_key else ()
    protected = _protected_value(value, matches)
    return (
        _canonical_sha256(protected),
        _protected_field_fingerprints(protected),
        num_startups,
    )


def _read_with_retry(
    registry: Path, repository_key: str, attempts: int = 5, pause: float = 0.05
) -> tuple[str, dict[str, str], int] | None:
    """The host rewrites this file while we poll; a torn read is expected, not fatal."""
    for _ in range(attempts):
        try:
            return _snapshot(registry, repository_key)
        except (ClaudeRegistryError, OSError, ValueError):
            time.sleep(pause)
    return None


def _changed(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    return sorted(
        name
        for name in {*before, *after}
        if before.get(name) != after.get(name)
    )


def run_census(
    registry: Path,
    repository_key: str,
    duration: float,
    interval: float,
) -> dict[str, Any]:
    baseline = _read_with_retry(registry, repository_key)
    if baseline is None:
        raise SystemExit("could not read a stable registry snapshot; is the path right?")

    semantic, fingerprints, startups = baseline
    print(f"registry     : {registry}")
    print(f"exempted     : {_EXEMPT_NOTE}")
    print(f"target key   : {repository_key or '(none -- nothing exempted from projects)'}")
    print(f"baseline     : semantic={semantic[:16]} numStartups={startups}")
    print(f"watching     : {duration:.0f}s at {interval:.2f}s intervals. Start Claude now.")
    print("-" * 78)

    observations: list[dict[str, Any]] = []
    field_counter: Counter[str] = Counter()
    deadline = time.monotonic() + duration
    last_mtime = registry.stat().st_mtime_ns
    started = time.monotonic()

    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            mtime = registry.stat().st_mtime_ns
        except OSError:
            continue
        if mtime == last_mtime:
            continue
        last_mtime = mtime

        current = _read_with_retry(registry, repository_key)
        if current is None:
            continue
        new_semantic, new_fingerprints, new_startups = current
        if new_semantic == semantic and new_startups == startups:
            continue  # only exempt state moved -- the guard would not have seen this

        elapsed = time.monotonic() - started
        names = _changed(fingerprints, new_fingerprints)
        categories = sorted({_field_category(name).value for name in names})
        field_counter.update(names)
        observations.append(
            {
                "at_seconds": round(elapsed, 3),
                "changed_fields": names,
                "categories": categories,
                "num_startups_delta": new_startups - startups,
                "would_guard_reject": bool(names),
            }
        )
        verdict = "REJECT" if names else "allowed"
        print(
            f"[{elapsed:7.3f}s] {verdict:8} "
            f"numStartups {startups}->{new_startups}  "
            f"{', '.join(names) or '(exempt state only)'}"
        )
        if categories:
            print(f"{'':11} categories: {', '.join(categories)}")

        semantic, fingerprints, startups = new_semantic, new_fingerprints, new_startups

    print("-" * 78)
    if not observations:
        print("NO protected drift observed. The guard would have stayed clean.")
    else:
        print(f"{len(observations)} protected change(s) observed. Fields, by frequency:")
        for name, count in field_counter.most_common():
            print(f"  {count:3}x  {name:40} -> {_field_category(name).value}")
        print()
        print("Each of these is a separate blocker: suppressing one only exposes the next.")

    return {
        "registry": str(registry),
        "observations": observations,
        "changed_fields": dict(field_counter),
        "clean": not observations,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-pilot-registry-census",
        description="Read-only Claude registry drift census. Writes nothing.",
    )
    parser.add_argument("--registry", default=str(Path.home() / ".claude.json"))
    parser.add_argument(
        "--repo",
        default="",
        help="allowlisted repository root to exempt, matching a real activation",
    )
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = Path(args.registry).expanduser().resolve(strict=False)
    repository_key = (
        str(Path(args.repo).expanduser().resolve(strict=False)) if args.repo else ""
    )
    result = run_census(registry, repository_key, args.duration, args.interval)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
