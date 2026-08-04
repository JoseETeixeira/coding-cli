# Understanding — agentic compression using images

Task slug: `agentic-image-compression`
Phase 1 (Understanding). Status: approved by user (2026-08-04).
Date: 2026-08-04

## What was asked

Two proposals, evaluated separately because they turned out to have opposite verdicts:

- **A. Visual-token rendering** — render long observation-action histories to images and feed
  those instead of text, with segment optical caching and adaptive self-compression.
  Claimed: >50% token reduction, >95% accuracy retention, up to 20x rendering speedup.
- **B. Colour-cipher packing** — map each letter to a basic colour and pack two letters per
  pixel by mixing channels ("green + blue = yellow").

The instruction was conditional: *"If viable, implement it."* So Phase 1 is a feasibility study
with real measurements, not a literature summary.

## Discovery performed

Agentic grep/read over the repository (there is no `search_codebase` tool on this host) plus the
mnemo `task_context` preflight (namespace `repo:coding-cli`, 5 items returned, all concerning the
prior `cross-host-context-compaction` and `create-gpt-image-2-skill-and-tool` tasks — related but
not overlapping). 17-agent feasibility workflow + 4-agent needle-retrieval workflow.

Existing prior art **in this repo**:

- `context_compaction/` (6,454 lines) — a *continuity guard* for recovering after the host's own
  native compaction. It is **not** a token-reduction codec. `storage.py` is a single-slot JSON
  state file plus a bounded event ring, **not** a content-addressed blob store, so it does not
  already provide a segment cache.
- `skills/context-compaction/SKILL.md` — the re-entry protocol after native compaction.
- `gpt_image_2/server.py` — working precedent for a standalone MCP server in this repo that
  **returns image content blocks** via the FastMCP `Image` helper (`gpt_image_2/server.py:29`).
- `benchmarks/context_compaction/educode-probes.v1.json` + `context_compaction/benchmark.py` —
  an existing benchmark harness shape to imitate.
- A `headroom` MCP is already connected this session (`headroom_compress` / `headroom_retrieve` /
  `headroom_stats`) — it does *textual* compress-with-retrieval. The proposed feature is the
  optical analogue of the same compress/retrieve contract, which is a useful precedent for the API
  shape and a possible overlap to reconcile.

## Measured results

Harness: `.batman/agentic-image-compression/experiments/` (`render_lab.py`, `score_decode.py`).
Deterministic, offline, no randomness. Font: Consolas. Scoring: normalised Levenshtein for
character accuracy, plus a separate **critical-token** accuracy over identifiers/hashes/numbers,
because a transcription can score 98.9% overall while corrupting a quarter of the hashes.

### Token model (corrected and validated)

Claude bills whole **28x28-pixel patches**: `tokens = ceil(w/28) * ceil(h/28)`, capped at
**1568 tokens** (standard) or **4784** (Claude 4.7+ high-res), with an aspect-preserving downscale
when exceeded. Validated against Anthropic's published table: 200x200 -> 64, 1000x1000 -> 1296,
1092x1092 -> 1521 (all exact). The 1920x1080 -> 1560 case comes out 3% low in our estimator, so
the estimator is a **floor, not a guarantee**.

The compression ratio depends only on font size, not image size:
`ratio = 196 / (char_width * line_height)`.

| font | cell px | chars/image (standard) | ratio | reduction | char acc | critical acc |
|------|---------|------------------------|-------|-----------|----------|--------------|
| 8    | 4x9     | 32,520                 | 5.35x | 81.3%     | 99.4%    | **95.8%**    |
| 10   | 6x11    | 17,640                 | 2.90x | 65.5%     | 100%     | 100%         |
| 12   | 7x13    | 12,865                 | 2.11x | 52.7%     | 100%     | 100%         |
| 14   | 8x15    | 9,720                  | 1.60x | 37.4%     | —        | —            |

Break-even is font size ~17px; above that an image costs more than the text it replaces.

### A. Visual-token rendering — VIABLE, with bounds

- **Decode fidelity**: 12 trials across 4 content types (code, identifiers, logs, prose) x 3
  densities. At fs10 and fs12: **100% character and 100% critical-token accuracy**. At fs8:
  99.4% char but **95.8% critical** — and the failures are the dangerous kind: a UUID flipped
  `3c197fdfa164` -> `3c197fdfe164`, and an access-key-shaped string mangled
  `AKIAI44QH8DHBEXAMPLE` -> `AKIAI4Q4HDBHEXAMPLE`.
- **Needle retrieval** (the real use case): a 34,247-char agent history rendered to one page.
  Three independent trials each recovered **15/15 planted facts** with exact verbatim quotes,
  matching the plain-text control. But two of three trials misread an incidental turn number
  (041 -> 042) — semantic recall is excellent, incidental numerics drift.
- **Segment optical caching**: confirmed and explained. It is memoisation over an append-only
  log, turning O(N^2) re-rendering into O(N). Measured 10.2x at 18 segments; speedup scales
  as ~N/2, so the claimed "20x" lands around 40 segments. Cache hits are essentially free.
- **Prior art**: Glyph (arXiv:2510.17800, Tsinghua/Zhipu) reports 3-4x — but with a model
  **fine-tuned for the task**. Our 2.90x with a general-purpose model is consistent and slightly
  below, which is the expected direction.

### B. Colour-cipher packing — NOT VIABLE

Two independent, decisive failures:

1. **The mixing rule is not injective.** Exhaustive analysis of the proposed additive mix
   (`green + blue`): 256 input pairs collapse to **27 distinct colours; 100% of pairs collide**.
   White alone is the image of 46 different pairs. All 16 palette colours are also producible by
   a mix, so a decoder cannot even tell a one-symbol cell from a two-symbol cell. Information
   drops from a theoretical 8 bits/cell to 4.75, and non-recoverably. (Note: `green + blue` is
   cyan, not yellow — but the flaw is structural, not a palette-choice error.)
2. **Even a fixed, injective encoding cannot be read by the model.** We built the repaired
   version (R channel = symbol 1, G channel = symbol 2 — lossless and bijective) and tested it.
   The model could not decode it and correctly explained why: Anthropic's own documentation
   states *"Claude views images in patches instead of pixels. Each patch is a 28x28-pixel block."*
   One patch = 2,352 RGB subpixel values collapsed into one embedding, after resampling, optional
   lossy transport re-encoding, linear projection, and 24+ layers of attention mixing. There is no
   decoder head that maps embeddings back to RGB.
3. **Even if it worked, it would be expansion, not compression.** A robust palette survives at
   roughly one symbol per 28x28 patch = 4-6 bits per visual token, versus ~28 bits (about 3.8
   characters) per text token. That is a ~5x *expansion*.

The scheme is machine-decodable (PIL reading pixels programmatically) but that is not compression
of the context window — it is just a worse file format than gzip, and the context window, not disk,
is the constrained resource.

## What this means for design

The honest framing is **lossy optical gist with mandatory exact retrieval**, not "compression".

- Safe operating point: **font size 10**, ~2.9x, 65% reduction, measured lossless on our corpus.
- fs8 (5.35x) must be opt-in and must never carry identifiers.
- The image is for **gist, navigation, and recall**. Anything that will be used as an exact value
  — hashes, IDs, paths, line numbers, credentials, version pins — must be fetched back as text by
  content hash. This mirrors the `headroom_compress`/`headroom_retrieve` contract.
- Minimum viable payload: small inputs do not amortise padding. Below roughly 8-10k characters,
  rendering *loses*. Measured: a 428-char code sample at fs12 scored **0.95x** — worse than text.
- Neither host lets an agent rewrite its own context window. The only real insertion point is
  **tool output**: an MCP tool returning an image content block instead of text. `gpt_image_2` is
  the working precedent that this is possible here.

## Verified host capabilities

Established by source reading plus two end-to-end runtime tests, not by assumption.

| capability | Claude Code | Codex CLI |
|---|---|---|
| MCP tool returns image content block | YES (`gpt_image_2` precedent) | YES (`convert_mcp_content_to_items`) |
| Hook can replace tool output | **YES** (`PostToolUse.updatedToolOutput`) | **NO — explicitly rejected** |
| Hook can inject an image | YES (`isImage:true` or `structuredContent`) | NO channel exists |

- **Claude Code**: `PostToolUse` → `hookSpecificOutput.updatedToolOutput` genuinely replaces the
  result. Verified twice at runtime against Claude Code 2.1.221: `isImage:true` with a
  `data:image/png;base64,...` stdout produced a real image block, and `structuredContent` as an
  array produced an ordered `[text, image, text]` result. Claude Code *also* natively auto-detects
  a `data:image/...;base64,` Bash stdout with no hook at all.
- **Codex**: `codex-rs/hooks/src/engine/output_parser.rs` contains
  `unsupported_post_tool_use_hook_specific_output`, which rejects `updatedMCPToolOutput` and fails
  open with a warning. Upstream PR #20703 to support it was **closed unmerged**. Codex hooks can
  block or add text-only `additionalContext`; there is no image path.
- **Codex MCP caveat**: `as_function_call_output_payload` checks `structuredContent` *before*
  content blocks, so any server setting it silently discards the image (open issue #10334).
  `gpt_image_2` avoids this via `structured_output=False`; the new server must do the same.
- **Size caps**: a full page is 692 KB base64 as RGB, 116 KB re-encoded 1-bit (an 83% saving worth
  taking unconditionally — the render is pure black on white). Bash declares
  `maxResultSizeChars: 30000`, which a full page exceeds; the `Read` tool has no such cap, so the
  hook must target Read shapes rather than Bash.
- **Trust behaviour**: in both runtime tests the model spontaneously flagged the substituted result
  as fabricated/injected and said it would treat it as untrusted — even when an accompanying text
  block explained the compression. The framing text is load-bearing and must read as a legitimate
  system-side transformation.

## Decisions taken (user, 2026-08-04)

1. **Proposal B is dropped**, retained only as a documented negative result with its proof.
2. **Scope**: standalone MCP server (mirroring `gpt_image_2`) exposing `optical_compress` /
   `optical_retrieve` / `optical_stats`, content-addressed segment cache, plus a skill,
   registration on both hosts, a replication benchmark, and PRD/ADRs — **and** automatic hook
   interception.
3. **Auto-hook policy — guarded**: auto-render only payloads over ~10k chars, always at fs10,
   and only after a pre-scan finds no dense identifier content (hashes, UUIDs, keys, tokens,
   base64 blobs). Anything failing the scan passes through as text, untouched. Every render stores
   the exact original for retrieval by hash.
4. **Host asymmetry — ship asymmetric and document it**: the MCP tool works on both hosts; the
   auto-hook is Claude Code only, targeting Read to avoid the Bash cap. A capability probe must
   make the difference explicit so nothing silently no-ops on Codex.

## Risks

- **Silent identifier corruption** is the top risk; mitigated by the retrieval contract and by
  refusing to render content matching secret/identifier patterns at aggressive densities.
- **Estimator under-counts** by ~3% in one validated case; treat budgets as floors.
- Pillow is **not** currently a dependency of this repo; adding it needs a new extras group.
- Prompt caching interactions are unmeasured. If a payload would be cached anyway, optical
  compression may save less than the raw ratio suggests.
