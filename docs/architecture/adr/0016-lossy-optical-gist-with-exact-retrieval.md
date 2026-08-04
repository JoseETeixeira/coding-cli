# 0016 — Optical compression is lossy gist with mandatory exact retrieval

- **Status:** accepted
- **Date:** 2026-08-04
- **Task:** `agentic-image-compression`
- **Supersedes:** nothing

## Context

Rendering text as images genuinely costs fewer tokens than the text: measured
2.90x at the default density, 62.9% fewer tokens on a real 46,637-character
source file. That is worth having.

But the accuracy is not uniform, and the way it fails is dangerous. Across 12
decode trials, the aggressive density scored **99.4% character accuracy while
losing 25% of the identifiers** in a sample — it flipped a hex digit in a UUID
(`3c197fdfa164` → `3c197fdfe164`) and mangled an access-key-shaped string.
Even at the default density, where character accuracy measured 100%, needle
trials drifted an incidental turn number in 2 of 3 runs.

A headline accuracy number hides exactly the errors that matter most. Prose
degrades visibly and recoverably; an identifier degrades invisibly and
catastrophically, because a wrong hash still *looks* like a hash.

We also had a second option available: encode data as colours rather than as
legible glyphs, which would in principle pack far more per pixel.

## Decision

Optical compression is framed, documented, and implemented as **lossy optical
gist with mandatory exact retrieval**, never as "compression".

Concretely:

1. Every render stores the exact original, content-addressed, with atomic writes.
2. Every tool description, the skill, and the framing block attached to every
   rendered payload instruct the reader to retrieve before relying on any exact
   value.
3. A guard classifies identifier-shaped content and refuses it for automatic
   compression; the aggressive density auto-downgrades to safe when identifiers
   are present.
4. Payloads under 8,000 characters are declined rather than rendered, because
   page padding does not amortise below that.
5. Colour-encoded data is rejected outright, and the benchmark proves it every
   run.

## Rationale for rejecting colour encoding

Two independent, decisive failures:

1. **The proposed additive mixing is not injective.** Exhaustively, 256
   letter-pairs collapse into 27 distinct colours; 100% of pairs collide; white
   alone is the image of 46 different pairs; and all 16 palette colours are also
   producible by a mix, so a decoder cannot even distinguish a one-symbol cell
   from a two-symbol one.
2. **Even a repaired, injective encoding is unreadable by the model.** Anthropic
   documents that "Claude views images in patches instead of pixels. Each patch
   is a 28x28-pixel block." One patch is 2,352 RGB subpixel values collapsed
   into a single embedding, after resampling, optional lossy transport
   re-encoding, linear projection, and 24+ layers of attention. There is no
   decoder head mapping embeddings back to RGB. We built the injective version
   and confirmed it cannot be decoded.

And even if both were solved, a robust palette carries ~4-6 bits per visual
token against ~28 bits per text token: a ~5x *expansion*. Legible rendered text
is the only member of this family that compresses at all.

## Consequences

**Good.** The dangerous failure mode is contained by construction rather than by
discipline. An agent that follows the advertised contract cannot act on a
corrupted identifier, because the exact bytes are always one call away. The
negative result on colour encoding is captured as an executable test, so nobody
re-litigates it from intuition.

**Costs.** Every precision-critical read is two calls, not one. The store grows
and needs pruning. The guard refuses about 26% of large real-world payloads —
by design, since every refusal we inspected was correct, but it does cap the
achievable saving.

**Accepted risk.** An agent that ignores the contract and quotes a hash off an
image will be wrong, and quietly. Mitigated by repetition (tool descriptions,
skill, per-payload framing) and by refusing the densities where it is most
likely, but not eliminated. Prompt-cache interaction remains unmeasured.
