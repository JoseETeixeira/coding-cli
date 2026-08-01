# PRD: mnemo shared agentic memory

Status: accepted · 2026-07-15

## Problem

The generic hosts (Claude Code, Codex, Copilot) had no durable, cross-agent memory after MemPalace was retired and repowise was removed. Agents could not share facts, decisions, or context across sessions or across tools. The user wants a self-hosted memory two agents can both read and write (the "inter-agent memory sharing" from the attached research), using Qdrant as the vector DB on port 1337.

## Goals

- One self-hosted memory substrate shared by Claude Code and Codex (and Copilot).
- Qdrant on host port **1337**; OpenAI embeddings (`text-embedding-3-small`), no local fallback.
- Exposed as an MCP server so any host can read/write via tools.
- Durable, typed, trust-tagged memory items with provenance and soft revocation.
- Safe by default: memory is optional context never authority; retrieved text is data not instructions; secrets are redacted on write.

## Non-goals (deferred, documented)

Graph projection (GraphRAG/HippoRAG), hierarchical summarizer (RAPTOR/LongT5), external policy engine (OPA/OpenFGA), full PII platform (Presidio). v1 ships a regex redactor and payload-level ACLs.

## Scope

- Engine at `mnemo/`: append-only JSONL event log (source of truth) → Qdrant vector projection.
- 8 MCP tools: `memory_status`, `task_context`, `memory_write`, `memory_search`, `memory_get`, `memory_list`, `memory_forget`, `memory_stats`.
- Item payload: type, trust_class (observed/inferred/summarized/imagined), timestamp, source_event_id, provenance, confidence, sensitivity, ttl/expires_at, namespace, writer, allowed_readers, tags, revoked.
- Registration for Claude (user scope), Codex (`config.toml`), Copilot (`mcp.json`).
- `shared-memory` + `mnemo-setup` skills; generic-entry loads `shared-memory`.

## Acceptance criteria

- `memory_status` reports a healthy backend (Qdrant 1337, embedder, count).
- A write by agent A is retrievable by agent B (cross-agent sharing) — verified live: Claude read a memory written by Codex.
- `memory_forget` excludes an item from future search; namespace + reader ACLs isolate memory.
- Engine unit tests and an MCP stdio smoke test pass.

## Verification

`py -3.12 -m pytest mnemo/tests` · `py -3.12 mnemo/tests/mcp_smoke.py` · live `claude` + `codex exec` runs exercising the tools.
