# PRD and ADR lifecycle

Behavior-changing implementation requires an owning approved PRD and accepted ADRs indexed at the current source hashes. Proposed or conflicting decisions block implementation.

Before coding:

- identify the owning PRD and accepted ADRs through Repowise;
- verify lifecycle, approval hashes, scope, supersession, conflicts, and exact source spans;
- update the PRD and create a new/superseding ADR before implementing a changed decision;
- never rewrite accepted ADR core sections.

After implementation:

- append implementation outcomes, verification evidence, rollout and rollback state;
- reconcile PRD completion or partial/cancelled status;
- update every behavior-facing document and managed wiki topic in place;
- refresh Repowise and verify no-op stability, citations, links, and the final snapshot.
