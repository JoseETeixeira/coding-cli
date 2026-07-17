---
name: auto-improvement
description: Maintains the canonical coding-cli customization source when durable user directives, agent-behavior review feedback, tracked-source contradictions, or oversized host memory require a change. Use ambiently for agent, skill, prompt, instruction, or memory behavior changes while preserving protected guides and explicit approval safety.
---

# Auto-improvement

Treat `coding-cli` as the only canonical source for shared agents, skills, prompts, and instructions. Host configuration contains pointers only; never mirror canonical bodies into Claude, Codex, Copilot, or user directories.

The parent entry agent evaluates these triggers at the beginning of every turn. “Always armed” means always evaluated, never permission to write silently. Specialists do not run this workflow or edit canonical customization; they return codification candidates to the parent in their structured handoff.

Fire when:

- a user answer supplies a durable behavior rule;
- requested PR feedback changes agent or skill behavior;
- a directive is untracked or contradicts a PRD, ADR, issue, or Batman spec;
- an active host memory file exceeds 40,000 characters.

Stay user-silent for transient instructions, duplicates, ordinary code fixes, explicit “do not codify” requests, and turns with no candidate.

## Workflow

1. Inspect the current turn for a trigger. Load tracked sources only when a candidate exists.
2. Restate the candidate rule in one sentence. If it is ambiguous, ask one clarifying question instead of codifying, and re-run detection on the answer.
3. Search PRDs, ADRs, issues, `.batman/`, and canonical `coding-cli` assets for the rule.
4. If an existing source agrees, do not duplicate it.
5. If sources conflict, show the exact contradiction and obtain a decision about updating the tracked source, the customization source, or both.
6. Choose the narrowest canonical file by the scope that owns the rule: one project → a project-specific skill; default behavior across projects → the agent definition; one workflow only → that workflow's prompt file. Refuse protected targets.
7. Show the proposed diff and wait for explicit approval before writing.
8. Apply one concern, cite its source in the change record, validate source assets, and verify host pointers still resolve.
9. After writing, state in one line what changed and where.
10. Never edit installed/generated host copies. A host-specific behavior belongs in a thin pointer or adapter, not a copied body.

## Protected targets

Do not edit these through auto-improvement:

- `skills/karpathy-guidelines/`

Route changes to their owning review workflow. Agent definitions, code-review instructions, and code-pattern instructions remain mutable with approval.

## Memory compaction

Check memory file size once per session on first read or reference, again after every write this skill makes to one, and on demand when the user names one. Measure with `wc -c`. When a file exceeds 40,000 characters, show the candidate compaction diff and wait for approval. Delegate compactable sections to the `caveman-compress` skill: it owns the output format and writes the human-readable `.original.md` backup, so keep that backup and never post-edit its output. Keep protected sections byte-identical, preserve section order and headings, and never delete a section the user has not named. Re-measure with `wc -c` after the write, report the new size, name any residual sections still over budget, and restore from the backup on verification failure.

## Guardrails

- Never invent durable rules or sources.
- Never expose or copy credentials.
- Never broaden native host tools, sandbox, network, paths, or approvals.
- Keep accepted ADR core sections immutable.
- Keep edits small and preserve unrelated user changes.
- Run the canonical code-review instructions before commit.
