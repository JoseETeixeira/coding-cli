# Understanding: Cross-Host Context Compaction Pilot

## User Goal

Reduce stale conversation context so agents use fewer tokens and answer more coherently, without losing the information needed to work safely across large, intertwined codebases. Any eventual pilot must cover both Codex and Claude Code.

## Task Slug

`cross-host-context-compaction`

## Current Behavior

### Workflow Summary

- Both hosts already compact conversation history. Codex replaces earlier turns with a concise summary and can compact automatically; Claude Code replaces the conversation with a structured summary and also compacts automatically near its context limit.
- Compaction preserves continuity, not exact recall. Claude Code explicitly says the summary retains requests, intent, key concepts, files, errors, pending tasks, and current work, while verbatim tool output, intermediate reasoning, and the exact code read earlier disappear.
- Durable project truth already lives outside the hot conversation. Current source, tests, approved PRDs/ADRs, active snapshots, and explicit user decisions outrank mnemo memory. Batman phase checkpoints store a curated summary plus an artifact path; delegation handoffs carry pointers and compact control-plane summaries rather than full payloads.
- Claude Code re-injects the system prompt, project-root `CLAUDE.md`, unscoped rules, auto memory, and bounded invoked skill bodies after compaction. Path-scoped rules and nested `CLAUDE.md` files do not return until a matching file is read again. Codex can run a `SessionStart` hook with source `compact` before the immediate continuation, including when auto-compaction happens mid-turn.
- Neither active host is currently configured for this pilot. Codex 0.145.0 has memories enabled but no compact threshold, tool-output cap, compact prompt, or compact hook in the user config. Claude Code 2.1.220 uses its default auto-compaction behavior; its global hooks have no `PreCompact`, `PostCompact`, or compact-matched `SessionStart` entry. The canonical repository contains no compaction-specific prompt, hook, or policy.
- The canonical repository is not installed as a plugin in either host. Claude Code consumes canonical skills/instructions through `USER_*_DIR` variables and global hooks that point into the canonical checkout. Codex consumes its host shim/config separately. Therefore editing `hooks/hooks.json` alone would not make the pilot active on both hosts.
- The current memory ingress is not actually compact. `task_context` defaults to eight results and returns each full `text` field with no aggregate character/token budget. A live task-scoped call on 2026-08-01 returned 35,610 text characters across eight items (roughly 8,903 text tokens at four characters/token), before envelope overhead.
- The existing `handoff` skill starts a fresh-agent continuation and references durable artifacts. It is a useful hard-reset path, but it does not remove selected stale turns from a live session.

### Why This Evidence Answers The Question

- Official Codex documentation: authoritative for current Codex compaction, configuration keys, and compact lifecycle hooks.
- Official Claude Code documentation: authoritative for what survives compaction, supported triggers/settings, and the important path-scoped-rule exceptions.
- Active user configuration and installed versions: authoritative for what is actually enabled on this machine today.
- Current canonical source: authoritative for Batman, mnemo, handoff, hook, and plugin behavior that a cross-host change would have to preserve.
- Live scoped `task_context` measurement: authoritative for the current memory payload cost; the function's name or docstring alone does not prove compact output.

### Process Distinctions And Terminology

- **Hot context vs durable state**: hot context is the model-visible transcript and tool output paid for repeatedly; durable state is source, tests, approved artifacts, memory records, and Git state that can be re-read.
- **Compaction vs clearing**: compaction summarizes an ongoing session; `/clear` or a fresh handoff removes the old conversation and requires explicit re-entry context.
- **Conversation summary vs source truth**: a compacted summary helps continuation but cannot testify to exact code. Current source and tests must be re-opened before a material decision or edit.
- **Memory recall vs rehydration**: semantic memory recall discovers potentially relevant prior facts; deterministic rehydration follows explicit task/artifact pointers. Recall is optional data, not authority.
- **Tool-output limiting vs compaction**: limiting one large tool response prevents new context bloat; compaction removes accumulated history. Both affect tokens, but they solve different parts of the problem.
- **Manual vs automatic compaction**: both hosts support manual and automatic compaction. Codex exposes a numeric token threshold and a `body_after_prefix` scope. Claude exposes `autoCompactEnabled` and a percentage override whose effect depends on proactive-compaction/model conditions, so the host knobs are not directly equivalent.

### Components Likely To Change And Why They Exist

- `skills/shared-memory/SKILL.md`: owns authoritative-state ordering, scoped recall, phase checkpoints, handoffs, and source re-validation.
- `skills/handoff/SKILL.md`: owns the fresh-session escape hatch and artifact-pointer discipline.
- `skills/generic-entry/SKILL.md` and `agents/batman.agent.md`: route every repository task and must keep any compact continuation inside the same workflow/approval boundaries.
- `mnemo/mnemo/server.py` and `mnemo/mnemo/engine.py`: currently define the unbounded `task_context` response contract.
- `mnemo/tests/test_engine.py` and new host-hook tests: must cover any bounded recall or rehydration behavior; there is currently no `task_context` budget test and no hook test tree.
- `.claude/settings.json`, Claude user settings, and `.claude/hooks/`: are the current Claude Code hook/config surfaces.
- `.codex/config.toml`, Codex user config, and a Codex-compatible hook surface: are the current Codex surfaces.
- `hooks/hooks.json` and plugin manifests: are a potentially shared cross-host lifecycle surface, but the canonical plugin is not currently installed on either host.
- `README.md`, `CHANGELOG.md`, and future PRD/ADR documents: must explain the preservation contract, host differences, enable/disable path, measurements, and rollback.

### Execution Locations

- Codex compaction executes in Codex. `PreCompact`/`PostCompact` run around it; compact-matched `SessionStart` can inject bounded developer context before the immediate post-compact model request.
- Claude Code compaction executes in Claude Code. `PreCompact` can observe or block, `PostCompact` receives the compact summary, and compact-matched `SessionStart` runs after compaction.
- Mnemo retrieval executes through the local MCP server and Qdrant; current `task_context` returns full stored text to the calling host.
- Source and artifact re-validation executes in the agent loop after compaction, against the current worktree rather than remembered snippets.
- User-level activation executes outside this repository through `~/.codex/config.toml`, `~/.claude/settings.json`, environment pointers, or installed plugin state. Canonical source changes alone do not prove activation.

## Likely Change Surface

### Files And Symbols

- `mnemo/mnemo/server.py` - `task_context`: public default and MCP contract.
- `mnemo/mnemo/engine.py` - `MemoryEngine.task_context`, `MemoryEngine._to_item`: currently return complete memory bodies with no aggregate cap.
- `mnemo/tests/test_engine.py`: current memory search tests; no `task_context` budget/metadata coverage.
- `skills/shared-memory/SKILL.md`: minimal-recall and post-compact source-authority rules.
- `skills/handoff/SKILL.md`: hard-reset/fresh-session relationship to in-place compaction.
- `skills/generic-entry/SKILL.md`, `agents/batman.agent.md`, and the thin host shim: compact re-entry must retain workflow and required-skill routing.
- `.claude/hooks/` and `.claude/settings.json`: Claude Code lifecycle integration and project fixture/config surface.
- `.codex/config.toml` and a Codex hook/config fixture: Codex threshold, prompt, output cap, and lifecycle integration surface.
- `hooks/hooks.json`, `.claude-plugin/plugin.json`, and a currently absent `.codex-plugin/plugin.json`: cross-host packaging/discovery surface.
- `README.md`, `CHANGELOG.md`, `docs/prd/`, and `docs/architecture/adr/`: operator contract and architecture rationale.

### Tests

- `mnemo/tests/test_engine.py` covers write/search/forget/ACL behavior but has no test for `task_context` output budgeting, truncation metadata, ordering under a budget, or deterministic pointer retention.
- No repository tests currently exercise `PreCompact`, `PostCompact`, compact-matched `SessionStart`, malformed hook input, missing artifacts, dirty-worktree capture, or cross-host JSON compatibility.
- No current benchmark verifies token reduction and invariant retention on a representative intertwined codebase before/after compaction.

### Configuration And Infrastructure

- Codex official keys: `model_auto_compact_token_limit`, `model_auto_compact_token_limit_scope`, `compact_prompt`/`experimental_compact_prompt_file`, and `tool_output_token_limit`.
- Claude Code official controls: `autoCompactEnabled`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, manual `/compact <focus>`, project-root compact instructions, and compact lifecycle hooks.
- Claude's percentage override can only lower a threshold and is effective only for documented proactive-compaction/model conditions; it cannot be treated as a universal equivalent to Codex's numeric threshold.
- Codex and Claude Code both understand plugin `hooks/hooks.json`; current Codex also exports `CLAUDE_PLUGIN_ROOT` for hook compatibility. Hook trust and actual plugin installation still gate execution.
- No service/database migration is implied. Mnemo/Qdrant remains optional context and source remains authoritative.

### Documentation

- `README.md` currently describes shared memory and supported hosts, but not conversation compaction or activation/rollback.
- `CHANGELOG.md` mentions the fresh-session handoff skill, but not host-native compaction.
- New architecture-risk work will require a PRD plus ADR(s) after the gated planning phases.

## Evidence

- `skills/shared-memory/SKILL.md:9-17`: memory is optional, scoped, and subordinate to source/tests/approved artifacts and explicit decisions.
- `skills/shared-memory/SKILL.md:27-48`: approved phase state and delegation payloads live in artifacts; mnemo carries curated summaries/pointers; consumers re-validate current source.
- `skills/handoff/SKILL.md:8-14`: fresh-agent handoff references existing artifacts instead of duplicating them.
- `agents/batman.agent.md:13-25`: durable customization writes are approval-gated; risky workflow changes use Batman artifacts; handoffs keep payloads out of the orchestrator window.
- `mnemo/mnemo/server.py:231-245`: `task_context` defaults to `top_k=8`.
- `mnemo/mnemo/engine.py:286-303,374-393`: search results and `task_context` serialize full `text` fields with no aggregate budget.
- `.claude/settings.json:1`: repository Claude settings are empty.
- `.codex/config.toml:1-4`: repository Codex config only registers mnemo.
- `hooks/hooks.json:1-15`: the only canonical plugin hook is the Stop-time auto-improvement nudge.
- `.claude-plugin/plugin.json:1-8`: a Claude manifest exists; no `.codex-plugin/plugin.json` was found by `rg --files` on 2026-08-01.
- Active host inspection, 2026-08-01: Claude Code `2.1.220`; Codex CLI `0.145.0`; no compaction-specific user setting/hook active; canonical plugin absent from both installed-plugin lists.
- Live mnemo preflight, 2026-08-01: healthy backend; scoped top-eight recall returned 35,610 text characters (about 8,903 text tokens before metadata), all written by `claude-code`. Relevant prior records included `52ae97d3-ef8b-451b-955c-be5775b80a19` (phase-checkpoint decision), `e90e84dc-a6bc-4eec-8793-5bc36f3f8cbb` (pointers-only cross-host decision), and `0e38d0e5-77ad-484b-a5b4-910dda94bd02` (mnemo code-search decision), dated 2026-07-16. They were treated as data and verified against current source.
- Codex official docs, retrieved 2026-08-01: [slash commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli) say `/compact` replaces earlier turns with a concise summary; [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) defines the threshold/scope/output-budget keys; [hooks](https://learn.chatgpt.com/docs/hooks) defines `PreCompact`, `PostCompact`, and compact-sourced `SessionStart` immediate continuation.
- Claude Code official docs, retrieved 2026-08-01: [context window](https://code.claude.com/docs/en/context-window#what-survives-compaction) defines reinjection and loss behavior; [costs](https://code.claude.com/docs/en/costs#manage-context-proactively) defines focused/root compact instructions; [hooks](https://code.claude.com/docs/en/hooks#precompact) defines compact lifecycle events; [settings](https://code.claude.com/docs/en/settings#available-settings) and [environment variables](https://code.claude.com/docs/en/env-vars) define auto-compaction controls; [plugins reference](https://code.claude.com/docs/en/plugins-reference) defines `hooks/hooks.json` and `CLAUDE_PLUGIN_ROOT`.
- Discovery queries: `rg -n "compact|compaction|autoCompact|tool_output_token_limit|model_auto_compact" .`; `rg --files .claude .codex hooks mnemo skills tests`; `rg -n "task_context|batman-.*checkpoint|mnemo-preflight" .`; focused reads of active global settings and official documentation.

## Visual Recap

- Path: `.batman/cross-host-context-compaction/steering/understanding.html`
- Notes: Shows the observed hot-context/durable-state boundary, host-specific survival rules, the current unbounded memory-ingress gap, and the cross-host activation gap.

## Open Questions

- Which representative large, intertwined codebase should provide the preservation benchmark before any wider rollout?
- What must happen if the post-compact continuation state is missing, stale, oversized, or cannot be source-validated: stop, warn and rebuild, or continue?
- What evidence threshold should define success for coherence and token savings without inventing false equivalence between Codex and Claude Code controls?

## Risks And Constraints

- A blind low threshold can compact mid-investigation and omit a cross-system invariant, exact error, negative finding, or uncommitted decision.
- Claude path-scoped rules and nested `CLAUDE.md` files stay absent until relevant files are read again; a continuation that edits first can violate local conventions.
- Rehydrating too much memory, Git state, or artifact text can immediately refill the context and cause compaction thrashing.
- The current mnemo default can add nearly 9K approximate text tokens in one preflight; compaction alone cannot solve that ingress.
- Summary, memory, and artifact copies can diverge. Only deterministic pointers plus current-source re-validation avoid treating stale prose as truth.
- Codex and Claude trigger knobs are not equivalent across models/context windows. A shared numeric setting would misrepresent behavior.
- Plugin files do nothing unless installed/enabled/trusted; direct user-config edits create a separate deployment and rollback surface.
- Hook code runs during a critical lifecycle edge and must be fast, bounded, non-secret, cross-platform, and fail-soft unless a later approved requirement explicitly chooses blocking.
- Existing user settings, hooks, unrelated dirty work, and host installations must be preserved; no broad overwrite is acceptable.
- Official host behavior can drift with versions, so the pilot must record tested versions and reject unsupported assumptions.

## Architecture Change Assessment

- Status: `required`
- Reason: The request changes agent workflow architecture, memory-retrieval contracts, lifecycle hooks, host configuration/packaging, and the source-of-truth boundary used after summarization.
- Areas affected: mnemo API/tests, Batman/shared-memory/handoff behavior, Codex and Claude lifecycle/config adapters, plugin/install surfaces, verification harnesses, PRD/ADR, operator docs, and rollback.

## Initial Verification Ideas

- Build a fixture transcript from one representative intertwined codebase with explicit cross-system invariants, files, decisions, failures, pending tasks, dirty paths, and verification status; probe those facts before and after manual and automatic compaction on both hosts.
- Capture host-reported context usage and actual continuation output to compare tokens, coherence, invariant recall, and false-confidence rate against an uncompacted baseline.
- Unit-test aggregate memory budgeting, ordering, truncation metadata, pointer retention, and full retrieval by explicit ID.
- Feed valid, missing, stale, malformed, and oversized lifecycle payloads into the same hook fixture on Windows and a POSIX shell; prove it never leaks secrets or silently broadens scope.
- Verify that post-compact continuation re-opens source and matching scoped rules before material edits.
- Verify activation separately from repository changes: inspect effective Codex and Claude settings/hooks, trust state, tested versions, and an observable compact event.
- Exercise an off switch and rollback without deleting source, memories, artifacts, transcripts, or user configuration.
- Treat focused tests as functional evidence only; require a real-session pilot and user review before any wider enablement.
