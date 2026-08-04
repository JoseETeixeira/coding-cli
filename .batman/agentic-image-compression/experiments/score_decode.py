"""Score model transcriptions of rendered-text images against ground truth.

Deterministic, offline. Reports character accuracy (1 - normalised Levenshtein),
plus a separate "critical token" accuracy over identifiers, hashes, and numbers,
because a transcription can look great while corrupting the one hash that matters.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def normalise(text: str) -> str:
    """Collapse whitespace and the newline marker so layout noise is not scored."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("¬", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


CRITICAL = re.compile(r"[A-Za-z0-9_./:-]*\d[A-Za-z0-9_./:-]*|[A-Za-z_][A-Za-z0-9_]{6,}")


def critical_tokens(text: str) -> list[str]:
    """Identifiers, hashes, numbers: the spans where a single wrong char is fatal."""
    return CRITICAL.findall(text)


def score(truth: str, got: str) -> dict:
    t, g = normalise(truth), normalise(got)
    distance = levenshtein(t, g)
    char_acc = 1 - distance / max(len(t), 1)

    truth_crit = critical_tokens(t)
    got_crit = set(critical_tokens(g))
    exact = [tok for tok in truth_crit if tok in got_crit]
    crit_acc = len(exact) / max(len(truth_crit), 1)
    missed = [tok for tok in truth_crit if tok not in got_crit]

    return {
        "truth_chars": len(t),
        "got_chars": len(g),
        "edit_distance": distance,
        "char_accuracy": round(char_acc, 4),
        "critical_total": len(truth_crit),
        "critical_exact": len(exact),
        "critical_accuracy": round(crit_acc, 4),
        "critical_missed": missed[:15],
    }


def main() -> None:
    results_path = Path(sys.argv[1])
    trials_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("trials")
    payload = json.loads(results_path.read_text(encoding="utf-8"))

    rows = []
    for entry in payload:
        kind, fs = entry["kind"], entry["fs"]
        truth = (trials_dir / f"{kind}.txt").read_text(encoding="utf-8")
        row = {
            "kind": kind,
            "fs": fs,
            "legibility": entry.get("legibility", "?"),
            **score(truth, entry.get("transcription", "")),
        }
        rows.append(row)

    rows.sort(key=lambda r: (r["fs"], r["kind"]))
    header = f"{'kind':<8}{'fs':>3}  {'legibility':<10}{'char_acc':>9}{'crit_acc':>9}  missed"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['kind']:<8}{r['fs']:>3}  {r['legibility']:<10}"
            f"{r['char_accuracy']:>8.1%}{r['critical_accuracy']:>9.1%}  "
            f"{','.join(r['critical_missed'][:3])}"
        )

    print()
    for fs in sorted({r["fs"] for r in rows}):
        subset = [r for r in rows if r["fs"] == fs]
        mean_char = sum(r["char_accuracy"] for r in subset) / len(subset)
        mean_crit = sum(r["critical_accuracy"] for r in subset) / len(subset)
        print(f"fs={fs:<3} mean char_acc={mean_char:.1%}  mean crit_acc={mean_crit:.1%}")

    Path("trials/scores.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
