"""Reproduce every published claim about optical compression, offline.

Six suites. Five are fully deterministic and need no model; the sixth
(`fidelity`) is the one claim a machine cannot settle alone, so it emits a
scorable trial pack instead of pretending to measure itself.

    python -m optical_compression benchmark --suite all
"""

from __future__ import annotations

import hashlib
import json
import time
import unicodedata
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from . import constants, guard
from .render import glyph_metrics, render
from .store import MemoryCache
from .tokens import compression_ratio, estimate_text_tokens, image_tokens, page_capacity_chars

# Anthropic's published size -> token reference points.
PUBLISHED_SIZES = ((200, 200, 64), (1000, 1000, 1296), (1092, 1092, 1521), (1920, 1080, 1560))

FONT_SIZES = (8, 10, 12, 14, 16, 18)


@dataclass
class SuiteResult:
    name: str
    passed: bool
    rows: list[dict]
    notes: list[str]


def suite_token_model() -> SuiteResult:
    """Validate the patch formula against vendor-published numbers."""
    rows, notes = [], []
    passed = True
    for width, height, expected in PUBLISHED_SIZES:
        got = image_tokens(width, height)
        delta = abs(got - expected) / expected
        ok = delta <= 0.05
        passed = passed and ok
        rows.append(
            {
                "size": f"{width}x{height}",
                "expected": expected,
                "measured": got,
                "delta_pct": round(delta * 100, 2),
                "ok": ok,
            }
        )
    notes.append(
        "The estimator is a FLOOR. It matches three reference points exactly and "
        "comes out ~3% low on 1920x1080 because the real downscale search is "
        "finer than our step-down. Budgets built on it are lower bounds."
    )
    return SuiteResult("token_model", passed, rows, notes)


def suite_density() -> SuiteResult:
    """Ratio and page capacity per font size; confirm the break-even point."""
    rows, notes = [], []
    for font_size in FONT_SIZES:
        char_width, line_height = glyph_metrics(font_size)
        ratio = compression_ratio(char_width, line_height)
        capacity = page_capacity_chars(char_width, line_height)
        rows.append(
            {
                "font_size": font_size,
                "cell": f"{char_width:.0f}x{line_height}",
                "ratio": round(ratio, 2),
                "reduction_pct": round((1 - 1 / ratio) * 100, 1) if ratio > 0 else 0.0,
                "chars_per_page": capacity,
                "beats_text": ratio > 1.0,
            }
        )
    losing = [row["font_size"] for row in rows if not row["beats_text"]]
    marginal = [row["font_size"] for row in rows if 1.0 < row["ratio"] < 1.15]
    notes.append(
        "ratio = 196 / (char_width * line_height). Sizes that lose outright to "
        f"plain text: {losing or 'none in range'}. Sizes within 15% of "
        f"break-even, where the win does not justify the fidelity risk: "
        f"{marginal or 'none'}. Only 'safe', 'balanced' and 'aggressive' are "
        "exposed as presets."
    )
    return SuiteResult("density", True, rows, notes)


def suite_cipher() -> SuiteResult:
    """Prove additive colour mixing cannot encode two symbols per pixel."""
    alphabet = "abcdefghijklmnop"
    palette = [
        (0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 255, 255),
        (128, 0, 0), (0, 128, 0), (0, 0, 128), (128, 128, 0),
        (128, 0, 128), (0, 128, 128), (128, 128, 128), (255, 128, 0),
    ]
    buckets: dict[tuple[int, int, int], list[str]] = {}
    for i, first in enumerate(palette):
        for j, second in enumerate(palette):
            mixed = tuple(min(255, a + b) for a, b in zip(first, second))
            buckets.setdefault(mixed, []).append(alphabet[i] + alphabet[j])

    pairs = len(palette) ** 2
    collided = sum(len(v) for v in buckets.values() if len(v) > 1)
    worst = max(buckets.items(), key=lambda kv: len(kv[1]))
    singles_reachable = sum(1 for colour in palette if colour in buckets)

    rows = [
        {"metric": "input_pairs", "value": pairs},
        {"metric": "distinct_output_colours", "value": len(buckets)},
        {"metric": "colliding_pairs", "value": collided},
        {"metric": "collision_rate_pct", "value": round(collided / pairs * 100, 1)},
        {"metric": "worst_collision_colour", "value": str(worst[0])},
        {"metric": "worst_collision_count", "value": len(worst[1])},
        {"metric": "palette_colours_also_produced_by_a_mix", "value": singles_reachable},
    ]
    notes = [
        "Additive mixing is not injective, so the scheme is undecodable in "
        "principle - before any question of whether a model could read it.",
        "Separately: vision encoders patchify at 28x28 px, so exact per-pixel "
        "RGB never reaches the language model at all.",
    ]
    # The proof is that the scheme FAILS; the suite passes when that failure
    # reproduces. The test is non-injectivity: strictly fewer distinct outputs
    # than inputs. (Exactly one pair survives uniquely - "aa", black on black -
    # so a `collided == pairs` check would be wrong.)
    passed = len(buckets) < pairs and collided >= pairs - 1
    return SuiteResult("cipher_negative_result", passed, rows, notes)


def suite_cache(segments: int = 12) -> SuiteResult:
    """Measure the append-only segment cache speedup.

    Models the real access pattern: a history that grows by one segment per
    turn and is re-rendered each turn. Without a cache that is O(N^2) page
    rasterisations; with one it is O(N).
    """
    corpus = _synthetic_history(segments * 1_800)
    chunks = [corpus[i : i + 1_800] for i in range(0, len(corpus), 1_800)]

    naive_start = time.perf_counter()
    for turn in range(1, len(chunks) + 1):
        _render_all(chunks[:turn], cache=None)
    naive = time.perf_counter() - naive_start

    cache = MemoryCache()
    cached_start = time.perf_counter()
    for turn in range(1, len(chunks) + 1):
        _render_all(chunks[:turn], cache=cache)
    cached = time.perf_counter() - cached_start

    speedup = (naive / cached) if cached else 0.0
    rows = [
        {"metric": "segments", "value": len(chunks)},
        {"metric": "naive_ms", "value": round(naive * 1000, 1)},
        {"metric": "cached_ms", "value": round(cached * 1000, 1)},
        {"metric": "speedup", "value": round(speedup, 1)},
        {"metric": "cache_entries", "value": len(cache)},
        {"metric": "cache_hits", "value": cache.hits},
    ]
    notes = [
        "An append-only history re-rendered every turn is O(N^2) page renders; "
        "memoising by content digest makes it O(N), so the speedup grows as ~N/2. "
        "The headline '20x' corresponds to roughly 40 segments, not to a constant.",
    ]
    return SuiteResult("segment_cache", speedup > 1.0, rows, notes)


def suite_guard() -> SuiteResult:
    """Confirm the guard refuses exactly the content that corrupted in trials."""
    cases = [
        ("uuid", "memory_id=25980152-3285-42c6-8305-3c197fdfa164", False),
        ("sha256", "sha256=30b7e9ba6b5b7642c92af44eddf7b4f6", False),
        ("aws_key", "token=AKIAI44QH8DHBEXAMPLE", False),
        ("jwt", "auth=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij", False),
        ("private_key", "-----BEGIN RSA PRIVATE KEY-----", False),
        ("secret_assign", 'api_key: "s0mesecretvalue"', False),
        ("plain_prose", "The conversation is a disposable hot cache, not a source of truth.", True),
        ("plain_log", "starting the build and waiting for the compiler to finish", True),
    ]
    rows, passed = [], True
    for name, sample, expect_safe in cases:
        verdict = guard.scan(sample)
        ok = verdict.safe_for_auto == expect_safe
        passed = passed and ok
        rows.append(
            {
                "case": name,
                "expected_safe": expect_safe,
                "actual_safe": verdict.safe_for_auto,
                "reasons": list(verdict.reasons),
                "ok": ok,
            }
        )
    notes = [
        "False positives cost a missed compression; false negatives cost silent "
        "corruption. The thresholds are deliberately tuned toward refusing.",
    ]
    return SuiteResult("guard", passed, rows, notes)


def suite_fidelity(outdir: Path) -> SuiteResult:
    """Emit a scorable trial pack. Decode accuracy needs a model in the loop."""
    outdir.mkdir(parents=True, exist_ok=True)
    samples = {
        "code": "def allocate(categories, *, max_chars=8000, max_tokens=2000):\n"
                "    indexed = sorted(enumerate(categories), key=lambda i: i[1].priority)\n"
                "    return [c for _, c in indexed if fits_budget(c.text)]\n" * 40,
        "idents": "commit 21dbd2c9f4ae5aaf09394462 sha256=30b7e9ba6b5b7642c92af44eddf7b4f6\n"
                  "memory_id=25980152-3285-42c6-8305-3c197fdfa164 port=1337 exit=0\n" * 60,
        "logs": "[turn 042] TOOL Bash(cmd='pytest -q') -> exit=0\n"
                "738 passed, 0 failed, 0 xfailed in 12.4s\n" * 60,
        "prose": "The conversation is a disposable hot cache, not a source of truth. "
                 "Safe compaction must keep exact state in current source and tests.\n" * 50,
    }
    rows = []
    for kind, text in samples.items():
        (outdir / f"{kind}.txt").write_text(text, encoding="utf-8")
        for density in ("safe", "balanced", "aggressive"):
            result = render(text, density=density)
            for page in result.pages:
                name = f"{kind}_{density}_p{page.index}.png"
                (outdir / name).write_bytes(page.png)
            rows.append(
                {
                    "kind": kind,
                    "density": density,
                    "pages": len(result.pages),
                    "ratio": round(result.ratio, 2),
                    "reduction_pct": round(result.reduction * 100, 1),
                }
            )
    notes = [
        f"Trial pack written to {outdir}.",
        "To score: have a model transcribe each PNG verbatim, then run "
        "`score_transcription(truth, transcription)` from this module. Report "
        "critical-token accuracy, not just character accuracy - in our trials a "
        "sample scored 98.9% character accuracy while corrupting 25% of hashes.",
    ]
    return SuiteResult("fidelity_pack", True, rows, notes)


# --- scoring helpers (used by the fidelity suite, and by tests) -------------

_CRITICAL = re.compile(r"[A-Za-z0-9_./:-]*\d[A-Za-z0-9_./:-]*|[A-Za-z_][A-Za-z0-9_]{6,}")


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("¬", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def score_transcription(truth: str, got: str) -> dict[str, object]:
    """Character accuracy AND critical-token accuracy.

    The second number is the one that matters. A transcription can score 98.9%
    on characters while losing a quarter of the identifiers, which is precisely
    the failure this whole design is built around.
    """
    t, g = _normalise(truth), _normalise(got)
    distance = levenshtein(t, g)
    truth_critical = _CRITICAL.findall(t)
    got_critical = set(_CRITICAL.findall(g))
    exact = [tok for tok in truth_critical if tok in got_critical]
    return {
        "char_accuracy": round(1 - distance / max(len(t), 1), 4),
        "critical_total": len(truth_critical),
        "critical_exact": len(exact),
        "critical_accuracy": round(len(exact) / max(len(truth_critical), 1), 4),
        "critical_missed": [tok for tok in truth_critical if tok not in got_critical][:15],
    }


def run(suite: str = "all", outdir: Path | None = None) -> dict[str, object]:
    outdir = outdir or Path("optical-benchmark")
    available = {
        "token_model": suite_token_model,
        "density": suite_density,
        "cipher": suite_cipher,
        "cache": suite_cache,
        "guard": suite_guard,
        "fidelity": lambda: suite_fidelity(outdir),
    }
    chosen = list(available) if suite == "all" else [suite]
    unknown = [name for name in chosen if name not in available]
    if unknown:
        raise ValueError(f"unknown suite(s): {', '.join(unknown)}")

    results = [asdict(available[name]()) for name in chosen]
    return {
        "suites": results,
        "passed": all(item["passed"] for item in results),
        "environment": {
            "densities": constants.DENSITIES,
            "tiers": constants.TIERS,
        },
    }


def _render_all(chunks, cache) -> None:
    """Render every chunk, consulting the cache when one is supplied.

    `render` takes the cache itself, so a hit skips rasterisation inside the
    renderer rather than being emulated here.
    """
    for chunk in chunks:
        render(chunk, density="balanced", cache=cache)


def _synthetic_history(chars: int) -> str:
    blocks, index = [], 0
    while sum(len(b) for b in blocks) < chars:
        index += 1
        blocks.append(
            f"[turn {index:03d}] TOOL Read(module_{index}.py) -> 12 lines\n"
            f"    value_{index} = compute(index={index}, scale={index * 7})\n"
            f"    assert value_{index} is not None, 'compute returned nothing'\n"
        )
    return "".join(blocks)[:chars]
