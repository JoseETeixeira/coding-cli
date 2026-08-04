# 0017 — Automatic hook interception ships Claude-Code-only, and says so

- **Status:** accepted
- **Date:** 2026-08-04
- **Task:** `agentic-image-compression`
- **Related:** ADR 0016, ADR 0015 (standalone gpt-image-2 MCP server)

## Context

Optical compression is most valuable when it needs no agent effort — a large
tool result is simply cheaper by the time the model sees it. That requires a
hook that can replace tool output before it enters the transcript.

The two hosts are not symmetric here, and the asymmetry is permanent rather
than a gap waiting to close.

**Claude Code can.** `PostToolUse` → `hookSpecificOutput.updatedToolOutput`
replaces the result. Verified end to end against Claude Code 2.1.221: an
`isImage: true` result with a `data:image/png;base64,...` stdout produced a real
image block, and `structuredContent` as an array produced an ordered
`[text, image, text]` result. The docs state it plainly: *"Replaces the tool's
output with the provided value before it is sent to Claude."*

**Codex cannot, by decision.** `codex-rs/hooks/src/engine/output_parser.rs`
contains `unsupported_post_tool_use_hook_specific_output`, which accepts
`updatedMCPToolOutput` on the wire and then rejects it, failing open with a
warning. Upstream PR #20703, which would have implemented it, was **closed
unmerged**. Codex hooks can block, or add a text-only `additionalContext`.
There is no image-capable hook channel anywhere in the surface.

Codex *can* receive MCP tool images — `convert_mcp_content_to_items` turns them
into `input_image` items, never truncated — so the explicit tool path is
unaffected.

Two further constraints shaped the design:

- Codex's `as_function_call_output_payload` checks `structuredContent` **before**
  content blocks, so a server that sets it silently discards the image and the
  agent receives text with no error at all (openai/codex issue #10334, open).
- Claude Code's `Bash` tool declares `maxResultSizeChars: 30000`. A full
  rendered page is 692 KB base64 as RGB, and 116 KB even re-encoded to 1-bit —
  far past that. The `Read` tool declares no such ceiling.

## Decision

Ship asymmetric, and make the asymmetry impossible to miss.

1. The MCP tools work identically on both hosts. Every tool sets
   `structured_output=False`, so `structuredContent` is never populated and the
   image cannot be silently dropped on Codex. A stdio smoke test asserts this.
2. The automatic hook targets **Claude Code and `Read` only** — `Read` because
   it has no result-size ceiling, unlike `Bash`.
3. `optical_stats` reports `capabilities.automatic_hook` with an explanation
   naming the upstream rejection, so an agent on Codex learns *why* nothing is
   happening instead of assuming a bug.
4. Codex's registration block carries the same explanation as a comment.
5. The hook fails open on every path.

## Alternatives rejected

**Parity by dropping the hook.** Simpler and uniform, but it discards the
passive savings on the host where they are available, to match a limitation the
other host chose deliberately. Levelling down to a permanent constraint is the
wrong trade.

**Wrapper-script emission.** Claude Code natively auto-detects a
`data:image/...;base64,` Bash stdout with no hook at all, so a wrapper could
emit image results directly. Rejected: it only helps commands routed through the
wrapper, and it inherits the 30,000-character `Bash` ceiling that a full page
exceeds.

**Wait for upstream.** The PR was closed, not stalled. There is nothing to wait
for.

## Consequences

**Good.** Claude Code users get passive savings; Codex users get the full
explicit surface with no silent degradation. The `structured_output=False`
requirement is pinned by a test rather than by memory — the failure it prevents
would otherwise be invisible in production.

**Costs.** Two behaviour profiles to document and reason about. Documentation
must stay accurate about which host does what, and the capability probe is the
mechanism that keeps that honest rather than aspirational.

**Revisit if** Codex ever lands output rewriting, or issue #10334 closes and
changes the `structuredContent` constraint.
