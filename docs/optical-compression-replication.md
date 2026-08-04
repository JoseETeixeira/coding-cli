# Replicating the optical-compression results

Every number in the PRD, ADR 0016, and the skill is reproducible offline. No
network, no credentials, no randomness, no clock dependence. Same inputs always
produce identical PNGs.

```bash
python -m optical_compression benchmark --suite all
```

Six suites. Five settle themselves; the sixth needs a model in the loop and says
so rather than pretending otherwise.

## Prerequisites

Python 3.12, Pillow, and one monospace font (Consolas, Courier New, DejaVu Sans
Mono, or Menlo — probed in that order). The test suite skips rather than fails
if none is present.

## 1. Token model — `--suite token_model`

Validates the billing formula against Anthropic's published size→token table.

```
200x200   -> 64     exact
1000x1000 -> 1296   exact
1092x1092 -> 1521   exact
1920x1080 -> 1560   we compute 1508 (3.3% low)
```

Claude bills whole 28×28-pixel patches: `tokens = ceil(w/28) * ceil(h/28)`,
capped at 1568 (standard) or 4784 (Claude 4.7+ high-res), with an
aspect-preserving downscale when exceeded.

**Read the last row as a warning, not a rounding error.** Our estimator steps
down in 2% increments where the vendor runs a finer search, so it can
*under*-report cost. Treat every budget built on it as a floor.

## 2. Density table — `--suite density`

Ratio and page capacity per font size.

| font | cell | ratio | reduction | chars/page |
|---|---|---|---|---|
| 8 | 4×9 | 5.44x | 81.6% | 34,071 |
| 10 | 6×11 | 2.97x | 66.3% | 18,400 |
| 12 | 7×13 | 2.15x | 53.6% | 13,430 |
| 14 | 8×15 | 1.63x | 38.8% | 10,074 |
| 16 | 9×17 | 1.28x | 21.9% | 7,995 |
| 18 | 10×19 | 1.03x | 3.1% | 6,380 |

Ratio is `196 / (char_width * line_height)` — it depends only on font size, not
on image size. Break-even is just past 18px. The shipped presets stop at 12/10/8
because everything above 14px buys too little to justify any fidelity risk.

Pages are sized to `page_box()` = 1092px (standard tier), **not** the 1568px
edge limit. Rendering to the full edge would cost 3,136 patches against a 1,568
ceiling, triggering a downscale that shrinks the glyphs and degrades decode
accuracy precisely where it is already tightest.

## 3. Colour-cipher negative result — `--suite cipher`

Proves the letter-to-colour proposal cannot work. The suite passes when the
failure reproduces.

```
input pairs                          256
distinct output colours               27
colliding pairs                      255  (only "aa" survives uniquely)
worst collision       (255,255,255) <- 46 distinct pairs
palette colours also produced by a mix  16/16
```

Additive mixing is not injective, so the scheme is undecodable *in principle* —
before any question of whether a model could read it. Separately, vision
encoders patchify at 28×28px, so exact per-pixel RGB never reaches the language
model at all. And even a repaired injective encoding would carry ~4–6 bits per
visual token against ~28 bits per text token: a ~5x expansion.

## 4. Segment cache — `--suite cache`

Models an append-only history re-rendered each turn: O(N²) page rasterisations
without a cache, O(N) with one.

Measured 6.3x at 12 segments; the standalone harness measured 10.2x at 18. The
speedup scales as roughly N/2, so the widely-cited "20x" corresponds to about 40
segments — it is a property of the access pattern, not a constant.

## 5. Guard — `--suite guard`

Eight cases: six identifier shapes that must be refused, two prose samples that
must pass.

Calibration on real repository files ≥10k chars: **17 of 23 pass (74%)**, and
every refusal was correct — files genuinely containing hashes, secret
assignments, or base64 blobs. False positives cost a missed compression; false
negatives cost silent corruption, so the thresholds lean toward refusing.

## 6. Fidelity pack — `--suite fidelity`

The one claim a machine cannot settle alone. Writes PNGs plus ground-truth text
for four content types × three densities.

```bash
python -m optical_compression benchmark --suite fidelity --outdir ./pack
```

Then, for each PNG:

1. Have a model transcribe it **verbatim**, instructing it not to autocorrect —
   an autocorrected hash reads as a successful decode.
2. Score it:

```python
from optical_compression.benchmark import score_transcription
score_transcription(truth, transcription)
```

**Report `critical_accuracy`, not `char_accuracy`.** This is the whole point: in
our trials a transcription scored **98.9% character accuracy while corrupting
25% of the identifiers**. Three typos destroyed a quarter of the hashes.

### Published fidelity results

12 trials, 4 content types (code / identifiers / logs / prose) × 3 densities:

| density | char accuracy | critical accuracy |
|---|---|---|
| 12px `safe` | 100% | 100% |
| 10px `balanced` | 100% | 100% |
| 8px `aggressive` | 99.4% | **95.8%** |

The 8px failures: `3c197fdfa164` → `3c197fdfe164`, and
`AKIAI44QH8DHBEXAMPLE` → `AKIAI4Q4HDBHEXAMPLE`.

### Needle retrieval

A 34,247-character agent history rendered to one page. Three independent trials
each recovered **15/15 planted facts** with exact verbatim quotes, matching a
plain-text control. Two of three still misread an incidental turn number
(041 → 042) — semantic recall is excellent, incidental numerics drift.

## End-to-end check

```bash
python -m optical_compression compress --file context_compaction/activation.py --outdir ./pages
python -m optical_compression retrieve --digest <digest> --raw > roundtrip.txt
```

Expected: 46,637 chars → 3 pages, 11,660 → 4,329 tokens (**2.69x, 62.9%
reduction**), and `roundtrip.txt` byte-identical to the source.

## Wire contract

```bash
python tests/optical_compression/mcp_smoke.py
```

16 gates over real stdio JSON-RPC. The load-bearing one is
`structuredContent is None`: Codex checks that field *before* content blocks, so
if it is ever populated the image is silently discarded and the agent receives
text with no error (openai/codex issue #10334).

## Comparison with published work

Glyph (arXiv:2510.17800, Tsinghua/Zhipu) reports 3–4x. We measure 2.90x at the
default density.

The gap is expected and is the honest headline: Glyph's figure comes from a
model **fine-tuned for the task**. 2.90x is what a general-purpose model
delivers with no training, which is the regime this repository operates in.
