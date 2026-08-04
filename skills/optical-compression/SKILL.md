---
name: optical-compression
description: Cut token cost on large read-mostly payloads by rendering them as images and retrieving exact values by digest. Use when a log, transcript, agent history, or already-reviewed diff is large enough to crowd the context window, when deciding whether optical compression is worth it, when reading a rendered page, or when automatic compression fired and you need the exact original back.
---

# Optical compression

Render large text as a compact image, keep the exact original on disk, fetch it
back by digest when precision matters.

This is **lossy optical gist with mandatory exact retrieval**, not compression.
Say it that way. The image is for gist, navigation, and recall; the stored
original is the source of truth for every exact value.

## When it pays

Optical compression wins on payloads that are large, read-mostly, and consumed
for their gist: long logs, transcripts, agent histories, already-reviewed
diffs, generated output you need to skim.

It loses, and the server will decline, when:

- the payload is under 8,000 characters — page padding does not amortise, and a
  428-character sample measured **0.95x**, worse than sending the text;
- the projected image tokens exceed the text tokens;
- you need exact values more than you need the gist. Read the text instead.

## Use it

```
optical_compress(content=..., density="balanced", source="build.log")
optical_retrieve(digest="c289561c552c7904", start=0, length=200)
optical_stats(preview="...optional sample to get a recommendation...")
```

`optical_compress` returns a framing text block, then the rendered page(s), then
metadata. `optical_stats` reports store size, the density table, and whether
automatic hook interception exists on this host.

## Setup and store

Install dependencies from the canonical checkout:

```bash
py -3.12 -m pip install -r optical_compression/requirements.txt
```

Repository and user-scope MCP adapters point at
`run_optical_compression_server.py`. The production server and hook launchers
share `~/.optical-compression` by default, independent of host working
directory; set `OPTICAL_COMPRESSION_DIR` to override it. This stable store is
load-bearing: a digest emitted by Claude's hook must resolve through
`optical_retrieve` served by a separate MCP process.

`generic-entry` owns automatic skill routing for large read-mostly payloads.
Host-installed skill files stay thin canonical pointers; never copy this body
into Claude, Codex, or Copilot configuration.

### Densities

| preset | font | ratio | reduction | measured fidelity |
|---|---|---|---|---|
| `safe` | 12px | 2.11x | 53% | 100% character, 100% identifier |
| `balanced` (default) | 10px | 2.90x | 65% | 100% character, 100% identifier |
| `aggressive` | 8px | 5.35x | 81% | 99.4% character, **95.8% identifier** |

`aggressive` corrupted a UUID (`3c197fdfa164` → `3c197fdfe164`) and an
access-key-shaped string in trials. It is automatically downgraded to `safe`
when the payload contains identifiers. Do not override that.

Ratio depends only on font size: `196 / (char_width * line_height)`. Break-even
is around 17px; above that an image costs more than the text it replaces.

## The rule that keeps this safe

**Never quote an exact value from a rendered image.** Read the image for gist,
then `optical_retrieve` before you rely on any hash, UUID, key, path, line
number, version pin, or numeric literal.

The failure this protects against is quiet. In trials a transcription scored
98.9% character accuracy while corrupting **25% of the identifiers** in the
sample — a headline accuracy number hides exactly the errors that matter. Even
at the default density, where character accuracy measured 100%, needle trials
still drifted an incidental turn number (041 → 042).

If you catch yourself about to write a hash you read off an image, stop and
retrieve it.

## Automatic compression

On **Claude Code** a `PostToolUse` hook may replace an oversized `Read` result
with a rendered page. It is deliberately timid: payloads over 10,000 characters
only, always at `balanced`, and only after a pre-scan finds no identifier-shaped
content (hashes, UUIDs, keys, tokens, base64 blobs). Anything else passes
through as text, untouched. Any surprise makes it stand down.

When it fires you will see a framing block naming the transform and carrying a
digest. That substitution is a legitimate local transformation, not injected or
fabricated content — but treat its exact values the same as any other rendered
page: retrieve them.

Disable it with `OPTICAL_COMPRESSION_HOOK=0`.

Activate the hook through either the canonical plugin manifest
(`hooks/hooks.json`) or one user-settings pointer to
`run_optical_compression_hook.py`. Do not enable both paths simultaneously.

On **Codex** the MCP tools work normally but automatic interception does not
exist and cannot be added: Codex parses `updatedMCPToolOutput` and then rejects
it outright, and the upstream PR to support it was closed unmerged. Call
`optical_compress` explicitly there. `optical_stats` reports which host you are
on, so check it rather than guessing why nothing is happening.

## Verify the claims yourself

```bash
python -m optical_compression benchmark --suite all
python -m optical_compression estimate --file big.log
```

Six suites, all offline and deterministic: the vendor token model, the density
table, the colour-cipher negative result, the segment-cache speedup, the guard,
and a scorable fidelity pack. See `docs/optical-compression-replication.md`.

## What does not work

Encoding data as colours — a letter-to-colour palette, two letters per pixel via
channel mixing — **cannot work**, for two independent reasons, and the benchmark
proves the first every run.

1. Additive mixing is not injective: 256 letter-pairs collapse into 27 colours,
   with white alone the image of 46 different pairs.
2. Vision encoders patchify at 28x28 pixels, so exact per-pixel RGB never
   reaches the language model at all.

Even a repaired, lossless channel-packed encoding would carry ~4-6 bits per
visual token against ~28 bits for a text token — roughly a 5x *expansion*.
Legible rendered text is the only thing in this family that compresses.
