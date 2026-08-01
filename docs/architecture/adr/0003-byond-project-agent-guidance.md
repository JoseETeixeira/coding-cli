---
status: Accepted
date: 2026-07-14
scope: coding-cli
task: byond-project-agent-guidance
supersedes: []
superseded_by: []
---

# ADR 0003: use one conditional skill for BYOND project guidance

## Status

Accepted on 2026-07-14 after explicit user approval.

## Context

BYOND work needs documentation-grounded DM changes and an actual Dream Maker compile. Dragon Ball Universe also has animation-registry, persistence, UI, description, balance, and indentation contracts. Embedding these rules in a broad system instruction or separate Claude and Codex bodies would load irrelevant context and allow host guidance to drift. A literal user-home path would also violate canonical source validation.

## Decision

Store all BYOND and Dragon Ball Universe behavior in `skills/byond-projects/SKILL.md`. Let its metadata trigger only for BYOND project work. Keep `AGENTS.md`, `agents/batman.agent.md`, and `prompts/execute-task.prompt.md` as thin pointers to that skill.

The skill requires BYOND documentation retrieval before BYOND-specific claims or changes, primary reliance on returned passages with source identifiers, and a stop-and-request-source response when the knowledge base cannot support the task. It also requires documentation-based implementation selection, DM compatibility, and Dream Maker compilation. It compiles the active project's `.dme`; the Dragon Ball Universe command derives the user home from `$env:USERPROFILE` rather than embedding a username.

## Alternatives

- Duplicate the complete rules in Claude and Codex instructions: rejected because copies drift and violate the source-only model.
- Put the complete rules in the global base instruction: rejected because unrelated tasks would always load BYOND-only context.
- Keep the existing execution-prompt block only: rejected because research, review, and non-spec work could bypass it.
- Preserve a literal absolute user-home path: rejected because canonical validation prohibits hardcoded user homes.

## Consequences

Claude and Codex share one task-specific authority while retaining thin host adapters. BYOND work fails closed when documentation support or compilation is unavailable instead of claiming verification. The documentation tool and Dream Maker remain external runtime dependencies; this change does not install or configure them. Local skip-worktree entry adapters remain intentionally host-specific, while the tracked skill and execution-prompt pointer carry canonical behavior.

## Rollout and rollback

Validate the skill, source assets, host scenarios, governance manifest, and direct host-pointer contents. Rollback removes the pointers and skill and records a superseding ADR rather than rewriting this accepted decision.

## References

- Product record: `docs/product/byond-project-agent-guidance-prd.md`
- Shared skill: `skills/byond-projects/SKILL.md`

## Implementation outcome

Implemented on 2026-07-14. The conditional skill and three thin pointers are active. Skill validation, 12 host scenarios, isolated canonical source validation, and Linux-path governance validation passed. No BYOND source was changed, so Dream Maker compilation was not applicable to this delivery.
