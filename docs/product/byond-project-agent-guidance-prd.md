---
status: Active
approved: 2026-07-14
owner: BYOND project maintainers
task: byond-project-agent-guidance
---

# PRD: BYOND project agent guidance

## Problem

BYOND and Dragon Ball Universe changes can silently use invalid DM syntax, rely on unsupported assumptions, omit persistence or animation registries, or finish without a Dream Maker compile. Existing guidance was embedded in one execution prompt, so Claude, Codex, and non-workflow tasks could miss it or drift into duplicated host-specific copies.

## Outcome

Claude and Codex discover one conditional BYOND skill from the canonical `coding-cli` checkout. Host entry instructions and the implementation prompt contain only thin pointers. The skill owns BYOND documentation retrieval, source citation, DM compatibility, compilation, and Dragon Ball Universe project safeguards.

## Required behavior

- Trigger for BYOND projects and `.dme`, `.dm`, `.dmm`, `.dmf`, or `.dms` files.
- Query `#byond-rag-docker/:search_byond_docs` from the user request before BYOND-specific claims or changes.
- Treat retrieved passages as primary evidence and cite their source identifiers.
- Disclose unsupported retrieval, stop BYOND-specific implementation, and request a source or location to index or supply instead of inventing support.
- Use documentation to choose among valid implementations for project constraints.
- Keep changes compatible with BYOND DM syntax, the engine, and runtime.
- Compile modified BYOND code against the active `.dme`; use the approved Dragon Ball Universe command on this host.
- Enforce the Dragon Ball Universe animation registry, persistence, UI/UX, description, balance, testing, and tab-indentation rules.

## Acceptance

1. Claude and Codex entry instructions point to the same `byond-projects` skill without copying its rule body.
2. The implementation prompt points to the same skill and no longer contains a second BYOND authority.
3. Skill metadata triggers on BYOND file types and Dragon Ball Universe work.
4. The skill contains every approved documentation, compile, and project-specific rule.
5. Canonical source, host-scenario, skill, and governance validation passes.

## Out of scope

- Installing or configuring the BYOND documentation MCP.
- Changing BYOND or Dragon Ball Universe game code in `coding-cli`.
- Claiming compile compatibility when Dream Maker cannot run.

## Rollout and rollback

Supported hosts load the skill through the existing source-only checkout. Rollback removes the host and prompt pointers, retires the skill, and supersedes ADR 0003; it does not create generated host copies or mutate unrelated host configuration.

## Implementation outcome

Implemented on 2026-07-14. The shared skill, Codex and Claude adapter pointers, and execution-prompt pointer now use one BYOND authority. Skill validation, all 12 host scenarios, isolated canonical source validation, and Linux-path governance validation passed. No BYOND compile was required because this change modifies only agent assets and governance documentation.
