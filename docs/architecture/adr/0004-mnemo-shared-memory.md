# 0004 — mnemo self-hosted shared agentic memory

Status: accepted · 2026-07-15

## Context

Generic hosts needed durable, cross-agent memory. The attached research recommends a "shared substrate" architecture: an append-only event log as source of truth, projected into vector (and optionally graph/summary) views, with typed/trust-tagged items and ACLs, shared between agents rather than mutated inside each agent's opaque context. The user fixed two constraints: Qdrant as the vector DB on port 1337, and (later) OpenAI embeddings with no local fallback.

## Options considered

1. **Framework (Mem0 / Letta) backed by Qdrant.** Batteries-included, but opinionated abstractions and heavier surface; still not a portable interchange format.
2. **Custom lean MCP server over Qdrant + event log (chosen).** Small, auditable, host-agnostic; both agents spawn the same stdio server against one Qdrant + one data dir, giving shared memory with full control of the schema.
3. **Vendor-native memory (Claude memory tool / Codex memories).** Not shared across vendors; no common schema.

## Decision

Build a lean Python MCP server (`mnemo/`, FastMCP) with:
- Canonical **append-only JSONL event log** per namespace (`~/.mnemo/events/`).
- **Qdrant vector projection** (`mnemo_memory`, port 1337) for semantic recall.
- **OpenAI `text-embedding-3-small`** embeddings; key from `OPENAI_API_KEY` or `~/.mnemo/openai_api_key` (fallback for hosts like Codex that don't pass env through to MCP servers).
- Typed, **trust-tagged** items (observed/inferred/summarized/imagined) with provenance, confidence, sensitivity, ttl, namespace, writer, `allowed_readers`, and **soft revocation** (never hard-delete).
- Payload **ACLs** (public OR reader-in-allowed) and namespace scoping; a conservative PII/secret **redactor** on write.
- 8 tools mirroring the retired repowise memory surface (`memory_status` ~ get_shared_memory_status, `task_context` ~ get_task_context).

Both Claude Code and Codex register the same stdio server → one shared substrate.

## Consequences

- Cross-agent memory sharing works today with full schema control; verified live (Claude read a memory Codex wrote).
- Deferred: graph projection, hierarchical summaries, external policy engine, full PII platform — the payload/redactor cover v1.
- OpenAI dependency for embeddings (network + key); no local fallback by product decision.
- The key file at `~/.mnemo/openai_api_key` is a secret at rest in the user's home; acceptable given the key already lives in the user environment.
