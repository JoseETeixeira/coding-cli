#!/usr/bin/env python3
"""Frozen retired-oracle versus current source-retrieval parity benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
CORPUS = ROOT / "tests/benchmarks/retrieval/corpus.yaml"


def tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[a-z0-9_.$/-]+", value.lower())))


def score(path: str, content: str, query: str) -> float:
    normalized_path = path.lower()
    normalized_content = content.lower()
    normalized_query = query.lower().strip()
    result = 0.0
    if normalized_path == normalized_query:
        result += 1000
    elif normalized_query in normalized_path:
        result += 40
    if normalized_query in normalized_content:
        result += 30
    for token in tokens(query):
        if token in normalized_path:
            result += 8
        result += min(normalized_content.count(token), 8)
    return result


def new_search(paths: list[str], query: str, limit: int = 5) -> list[str]:
    ranked = []
    for path in paths:
        source = WORKSPACE / path
        content = source.read_text(encoding="utf-8", errors="replace")
        ranked.append((score(path, content, query), path))
    return [path for value, path in sorted(ranked, key=lambda item: (-item[0], item[1])) if value > 0][
        :limit
    ]


def ndcg(rank: int | None) -> float:
    return 0.0 if rank is None else 1 / math.log2(rank + 2)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=".github/governance/retrieval-parity-report.json")
    args = parser.parse_args()
    fixture = json.loads(CORPUS.read_text(encoding="utf-8"))
    corpus = fixture["cases"]
    old_oracle = fixture["old_oracle"]
    paths = sorted({case["expected_path"] for case in corpus})
    missing = [path for path in paths if not (WORKSPACE / path).is_file()]
    if missing:
        raise SystemExit(f"corpus source missing: {missing}")
    results = []
    new_latency: list[float] = []
    for case in corpus:
        started = time.perf_counter()
        new = new_search(paths, case["query"])
        new_latency.append((time.perf_counter() - started) * 1000)
        expected = case["expected_path"]
        old_rank = case["old_rank"]
        new_rank = new.index(expected) + 1 if expected in new else None
        source = (WORKSPACE / expected).read_bytes()
        results.append(
            {
                **case,
                "old_rank": old_rank,
                "new_rank": new_rank,
                "new_top5": new,
                "citation_hash": hashlib.sha256(source).hexdigest(),
                "citation_identity": bool(new_rank and source),
                "old_ndcg5": ndcg(old_rank),
                "new_ndcg5": ndcg(new_rank),
            }
        )

    exact = [row for row in results if row.get("exact")]
    top3 = [row for row in results if row["category"] in {"traceback", "configuration", "markdown", "adr", "prd", "low_centrality"}]
    conceptual = [row for row in results if not row.get("exact")]
    metrics = {
        "cases": len(results),
        "exact_rank_one": sum(row["new_rank"] == 1 for row in exact) / len(exact),
        "top3_recall": sum(bool(row["new_rank"] and row["new_rank"] <= 3) for row in top3) / len(top3),
        "citation_identity": sum(row["citation_identity"] for row in results) / len(results),
        "old_conceptual_ndcg5": statistics.mean(row["old_ndcg5"] for row in conceptual),
        "new_conceptual_ndcg5": statistics.mean(row["new_ndcg5"] for row in conceptual),
        "old_latency_ms": old_oracle["latency_ms"],
        "new_latency_ms": {"p50": statistics.median(new_latency), "p95": percentile(new_latency, 0.95)},
    }
    passed = (
        metrics["exact_rank_one"] == 1.0
        and metrics["top3_recall"] >= 0.95
        and metrics["citation_identity"] == 1.0
        and metrics["new_conceptual_ndcg5"] >= metrics["old_conceptual_ndcg5"]
    )
    report = {"passed": passed, "metrics": metrics, "results": results}
    report_path = ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, **metrics}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
