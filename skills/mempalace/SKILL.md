---
name: mempalace
description: Use MemPalace to recover prior context, reuse durable knowledge, avoid repeating investigations, and persist valuable outcomes from the current session.
---

## Purpose

Use MemPalace to recover prior context, reuse durable knowledge, avoid repeating investigations, and persist valuable outcomes from the current session.

MemPalace is not a replacement for the live conversation context, open files, or the current repository state. It is the long-lived memory layer.

---

## When to use MemPalace

Use MemPalace when any of the following are true:

- The user is continuing prior work.
- The prompt references previous sessions, earlier discussions, past decisions, or unfinished tasks.
- The task depends on preferences, conventions, architecture decisions, naming, standards, or historical reasoning established before this session.
- The work spans multiple iterations and should be recoverable later.
- A subagent is starting work and prior related investigation may exist.
- The user asks about “what we decided”, “where we left off”, “how this was done before”, or similar history-sensitive questions.

Typical triggers:

- “continue”
- “resume”
- “pick this up”
- “where were we”
- “what were we doing”
- “last time”
- “carry on”
- “keep going”
- “how did we solve this before”
- “what did we decide about X”

---

## When not to use MemPalace

Do not force MemPalace into every task.

Avoid unnecessary memory calls when:

- The task is fully self-contained in the current prompt.
- The answer depends only on the files currently open or explicitly provided.
- The request is simple, one-off, and does not benefit from prior context.
- The needed answer is already clearly available in the active context.

Avoid diary spam. Persist only work that would genuinely help a future session.

---

## Core operating protocol

### 1. At the start of relevant work

First call:

- `mcp_mempalace_mempalace_status`

This confirms MemPalace is available and reminds the agent of the current memory protocol.

### 1a. Bootstrap the current project (auto-init + auto-mine when needed)

Before any retrieval, ensure the current project is initialized AND has at least
one mine pass on record. Skip when the project has clearly already been
bootstrapped (a recent mine entry shows up in `diary_read`/`search`, or
`status` reports drawers for the project's wing).

Detection:

1. Resolve the project root for the current task. The natural anchor is the
   workspace root (the top-level repo directory), or the directory the user
   referenced when starting work.
2. Check `mcp_mempalace_mempalace_status`. If the response shows zero drawers
   for the project's wing, OR if the palace has no `mempalace.yaml` for this
   project, the project has not been initialized.
3. Look for a `mempalace.yaml` in the project root. Missing file = not
   initialized.

Bootstrap actions, in order, both run from the project root:

1. If no `mempalace.yaml` exists:
   ```bash
   mempalace init .
   ```
   This creates `mempalace.yaml`, registers a wing for the project, and
   prepares the palace directory.
2. Once initialized, run an initial mine so retrieval has something to work
   against:
   ```bash
   mempalace mine .
   ```
   On large repos this may take a few minutes; the user wins back the cost
   on the first prompt that needs project history.

Rules:

- **Init and mine BEFORE retrieval.** A `diary_read` / `search` against an
  empty wing wastes a tool call and produces a false "no prior context"
  signal. Bootstrapping first means the very first retrieval is honest.
- **Don't re-init.** Running `mempalace init .` on a project that already
  has `mempalace.yaml` is a no-op but is unnecessary noise. Check first.
- **Don't re-mine on every session.** Once a project has been mined at
  least once, subsequent sessions rely on hook-driven incremental mines.
  Only run `mempalace mine .` again if the user explicitly asks, or if
  the project root contains many files the palace clearly has not yet
  seen (large gap between filesystem and `status` counts for the wing).
- If `mempalace init` or `mempalace mine` fails, surface the error and
  continue without retrieval. Never block the user's task on a memory
  bootstrap failure.

Then decide whether retrieval is needed.

For history-sensitive or resume-style work, use one or both of:

- `mcp_mempalace_mempalace_diary_read`
- `mcp_mempalace_mempalace_search`

Use `diary_read` when reconstructing chronology, prior session flow, or unfinished work.

Use `search` when looking for a concept, decision, preference, system, component, issue, or topic that may have been discussed before.

If specialized MemPalace agents may help, call:

- `mcp_mempalace_mempalace_list_agents`

Then use the most relevant specialist instead of improvising.

---

## Retrieval strategy

### Prefer retrieval before guessing

If the prompt suggests prior context matters, retrieve first.

Do not confidently invent prior state.

When context is ambiguous, say that you are checking memory rather than pretending continuity.

### Use the right tool for the job

#### `mcp_mempalace_mempalace_status`
Use at the beginning of relevant work to validate the memory layer and refresh the protocol.

#### `mcp_mempalace_mempalace_diary_read`
Use when:
- continuing prior work
- reconstructing timelines
- resuming after compaction
- recovering prior user goals
- understanding what was already tried

#### `mcp_mempalace_mempalace_search`
Use when:
- searching for decisions, topics, preferences, architecture, bugs, standards, or prior findings
- identifying whether similar work already exists
- checking whether the current task has historical context beyond the active conversation

#### `mcp_mempalace_mempalace_list_agents`
Use when:
- the task might fit a specialist
- the repository/workspace has recurring memory-heavy workflows
- you want a disciplined recovery path rather than ad hoc searching

---

## Writing protocol

Persist useful outcomes with:

- `mcp_mempalace_mempalace_diary_write`

Write only when the result has future value.

Good candidates for persistence:

- a meaningful user goal was completed
- important findings were established
- files, systems, or configs were changed
- a debugging path led to a concrete conclusion
- an architecture decision was made
- a partial investigation produced reusable insight
- a subagent completed scoped work
- compaction is about to happen and context would otherwise be lost

Do not write trivial diary entries for every small turn.

---

## AAAK diary format

When writing a diary entry, keep it concise and factual in AAAK form:

- **Ask**: what the user wanted
- **Actions**: what was done
- **Artifacts/Answers**: what was found, decided, changed, or produced
- **Known follow-ups**: unresolved items, validation still needed, next likely step

### Example shape

- Ask: User wanted to resume the pipeline migration work and determine the next safe implementation step.
- Actions: Checked MemPalace status, read prior diary entries, reviewed earlier findings on the Groovy-to-Go migration path, and compared the pending tasks against the current request.
- Artifacts/Answers: Recovered prior decisions about service boundaries, identified the unfinished validation around publish-stage parity, and proposed the next step as integration test coverage for the publish flow.
- Known follow-ups: Validate edge cases around rollback behavior and confirm whether CMDB attachment behavior was already migrated.

Keep entries compact, concrete, and easy to search later.

---

## Subagent behavior

When acting as or spawning a subagent:

1. Check `mcp_mempalace_mempalace_status`
2. Read/search for relevant prior work if the task may already have context
3. Keep the investigation scoped
4. Before stopping, write a concise diary entry with:
   - task goal
   - concrete findings
   - files/systems touched
   - unresolved follow-up

Subagents should not dump verbose narratives into memory. They should persist only the useful result.

---

## Resume handling

For prompts that clearly mean “continue previous work”:

1. Call `mcp_mempalace_mempalace_status`
2. Call `mcp_mempalace_mempalace_diary_read`
3. Use `mcp_mempalace_mempalace_search` if the diary alone is not enough
4. State that you are checking memory when the prior state is unclear
5. Continue only after reconstructing enough context to avoid guessing

---

## Guardrails

- Never invent prior work that was not retrieved.
- Never claim continuity unless memory or the active context supports it.
- Never spam diary writes for trivial progress.
- Prefer concise, searchable entries over long summaries.
- Prefer factual persistence over speculative persistence.
- Use MemPalace to reduce repeated work, not to replace reasoning.
- When current repo state conflicts with memory, trust the current repo state and note the discrepancy.

---

## Practical decision rule

Use this quick rule:

- **Need continuity?** → `status` + `diary_read`
- **Need historical facts on a topic?** → `status` + `search`
- **Need a specialist?** → `list_agents`
- **Need to preserve meaningful work?** → `diary_write`

---

## Expected outcome

Following this skill should make the agent:

- better at resuming interrupted work
- less likely to hallucinate prior context
- more consistent across long-running tasks
- better at preserving reusable findings
- safer around context compaction and subagent boundaries