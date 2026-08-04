# PRD — Agentic compression using images

- **Task slug:** `agentic-image-compression`
- **Status:** implemented (2026-08-04)
- **Source artifact:** `.batman/agentic-image-compression/steering/understanding.md`
- **Author:** José Eduardo Teixeira

## Problem

The context window is the scarce resource in long agent sessions. Large
read-mostly payloads — logs, transcripts, agent histories, already-reviewed
diffs — consume thousands of tokens for content the agent mostly needs the
*gist* of. Neither Claude Code nor Codex lets an agent rewrite its own context,
so the only lever is what a tool returns.

Published work (Glyph, arXiv:2510.17800; DeepSeek-OCR) claims text rendered as
images costs materially fewer tokens than the same text. The question this task
had to answer first was whether that reproduces here, on general-purpose models,
with no fine-tuning.

## Goals

1. Cut token cost on large read-mostly payloads by at least 50%.
2. Never silently corrupt a value the agent will act on.
3. Work on both Claude Code and Codex, and be honest where they differ.
4. Let anyone reproduce every published number offline.

## Non-goals

- Replacing `Read` as the default path. This is opt-in, or narrowly automatic.
- Compressing small payloads. Below ~8,000 characters it costs more than it saves.
- Lossless context compression. That is not what this is.
- Colour-encoded data. Proven non-viable; see ADR 0016 and the benchmark.

## What was measured

Compression ratio depends only on font size: `196 / (char_width * line_height)`.
Break-even is ~17px.

| density | font | ratio | reduction | character acc. | identifier acc. |
|---|---|---|---|---|---|
| `safe` | 12px | 2.11x | 53% | 100% | 100% |
| `balanced` | 10px | 2.90x | 65% | 100% | 100% |
| `aggressive` | 8px | 5.35x | 81% | 99.4% | **95.8%** |

- **Decode fidelity**: 12 trials across code, identifiers, logs, and prose.
- **Needle retrieval**: a 34,247-character history on one page — 3 independent
  trials each recovered 15/15 planted facts verbatim, matching a plain-text
  control, though 2 of 3 drifted an incidental turn number.
- **End to end**: `context_compaction/activation.py`, 46,637 chars → 3 pages,
  11,660 → 4,329 tokens (**2.69x, 62.9% reduction**), exact retrieval
  byte-identical.
- **Segment caching**: memoisation over an append-only log, O(N²) → O(N).
  Measured 10.2x at 18 segments; scales ~N/2, so the cited "20x" is ~40 segments.

All three of the originally cited claims (>50% reduction, >95% accuracy, ~20x
caching speedup) reproduce. Glyph's 3-4x does not, and should not: that figure
comes from a model fine-tuned for the task.

## Solution

An offline MCP server exposing three tools:

- `optical_compress(content, density, source, tier)` — renders to 1-bit PNG
  pages, stores the exact original, returns framing text + images + metadata.
- `optical_retrieve(digest, start, length)` — exact verbatim text, bounded spans.
- `optical_stats(preview)` — store stats, density table, host capabilities.

Plus a guarded `PostToolUse` hook on Claude Code, a CLI, and a six-suite
replication benchmark.

## Acceptance criteria — all met

| # | Criterion | Result |
|---|---|---|
| 1 | ≥50% token reduction on a real payload | 62.9% on a 46k file |
| 2 | Exact retrieval is byte-identical | verified, 46,637 == 46,637 |
| 3 | Identifier-bearing payloads refused automatically | guard, 74% pass rate on real files, every refusal correct |
| 4 | Small payloads declined, not degraded | declines under 8,000 chars |
| 5 | Image reaches the model on both hosts | stdio smoke: `structuredContent` absent, 16/16 gates |
| 6 | Host asymmetry visible, never silent | `optical_stats.capabilities` |
| 7 | Every claim reproducible offline | `benchmark --suite all`, all pass |
| 8 | Hook never damages a tool result | fails open; live-tested both ways |
| 9 | Workflow and host activation are wired | canonical `generic-entry`; repo + user MCP adapters; Claude `Read` hook pointer |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Silent identifier corruption | Guard refuses; `aggressive` auto-downgrades; retrieval is mandatory and advertised in every tool description |
| Model distrusts substituted output | Framing block states the transform is system-side and local — a measured behaviour, not a guess |
| Token estimator drift | Pinned to the vendor table in tests; documented as a **floor** (~3% low on one reference size) |
| Hook damages tool results | Fails open on any surprise; a shape mismatch degrades to a no-op |
| Store loss or split working directories | Atomic content-addressed writes in one stable `~/.optical-compression` store shared by both launchers; explicit override remains available |
| Prompt-cache interaction | **Unmeasured.** Savings may be smaller for content that would have been cached anyway |

## Dependencies

FastMCP and Pillow, owned by `optical_compression/requirements.txt` rather than
another server's dependency file. The hook imports rendering lazily so a
missing Pillow degrades to a no-op rather than breaking every tool call.
