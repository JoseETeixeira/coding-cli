---
name: freighthero-entry
description: Routes every FreightHero repository research, planning, implementation, review, and documentation task through fresh Repowise evidence, the smallest relevant skill set, fixed native-host specialists, and PRD/ADR gates. Use for work in the FreightHero workspace or any ai_watchtower, backend, frontend, robin-error-dashboard, coding-cli, or Repowise fork repository.
---

# FreightHero entry workflow

1. The parent entry agent reads `auto-improvement` and evaluates its triggers at the beginning of every turn. Stay user-silent when there is no candidate. Specialists never run it or mutate canonical customization; they return optional codification candidates in their handoff.
2. Classify the request from skill and agent metadata. Do not load other skill bodies yet.
3. Select the smallest relevant skill set. Read each selected `SKILL.md` completely and only its directly required references.
   - For any durable file mutation, load `mutation-review` before the first write and keep the same reviewer through PASS or BLOCKED.
   - Load `repowise-memory` for every repository task. It defines the mandatory bounded context query and the safe no-memory fallback.
4. Before repository analysis, planning, execution, or mutation, call Repowise `get_index_status` for the target repository. Continue only when `ready=true`, `freshness=current`, and the served commit/snapshot matches the task. Retry once after an explicit refresh request; otherwise stop.
5. Start the short-lived parent session and run the scoped context procedure in
   `repowise-memory`. Call `get_shared_memory_status`, then `get_task_context`
   with the repository, task, run, specialist identity, and smallest relevant
   kinds; when native MCP is unscoped, use the keyring-mediated
   `repowise session context` command. Run the task-scoped source query even
   when memory is empty or excluded. Prefer `search_codebase` to locate,
   `get_source` for exact spans, `get_answer` to explain, and `get_why` for
   decisions. Keep snapshot, commit, path, span, and hash citations.
6. For behavior-changing work, verify the owning PRD and accepted ADR are current and indexed before implementation. Update them before coding when the decision changes; append implementation outcomes after verification.
7. Delegate only when a fixed specialist is useful. Issue its exact child
   session before spawning it, then provide repository, task, run, specialist,
   approved scope, required skills, and snapshot identity. Every specialist
   repeats freshness and keyring-mediated scoped retrieval before its own work
   and returns a structured handoff with evidence, findings, checks, unresolved
   items, and optional memory or codification candidates.
8. Use the native Claude, Codex, or local Copilot model loop, sandbox, approvals, and credentials. Never route task work through an API-key model. Only the Repowise service may receive its scoped OpenAI credential.
9. Test changed behavior, run the canonical review instructions, update managed documentation, and re-query Repowise after a material scope or worktree-fingerprint change.

Read only the reference needed for the current branch:

- Repository evidence and failure behavior: [repowise.md](references/repowise.md)
- Request classes, workflow, and approvals: [workflow.md](references/workflow.md)
- Specialist tools, write boundaries, and delegation: [host-boundaries.md](references/host-boundaries.md)
- PRD, ADR, and documentation lifecycle: [governance.md](references/governance.md)
