# Agent Context Lifecycle

Language for reasoning about bounded conversation state across coding-agent hosts. These terms distinguish disposable model context from durable repository truth.

## Language

**Hot Context**:
Model-visible conversation, tool output, and injected state processed again on later requests.
_Avoid_: Memory, durable context, transcript archive

**Durable State**:
Current source, tests, Git state, approved artifacts, and explicit decisions that remain re-readable outside conversation history.
_Avoid_: Hot context, summary, model memory

**Active Task State**:
Minimal state needed to continue one task safely, including goal, approved decisions, plan position, evidence pointers, dirty paths, checks, blockers, and pending-operation status.
_Avoid_: Full transcript, session dump, all project knowledge

**Critical Invariant**:
User-approved constraint whose loss could cause unsafe or materially incorrect work across system boundaries.
_Avoid_: Preference, useful detail, remembered assumption

**Revalidation**:
Confirmation against current authoritative sources after conversation state has been compacted or recalled.
_Avoid_: Recall, trust the summary, memory lookup

**Validation Gate**:
Temporary boundary that permits only source reconstruction after compaction and releases material actions only after required current evidence has been reopened and matched.
_Avoid_: New sandbox, approval replacement, summary confidence

**Recovery Epoch**:
One post-compaction reconstruction interval, identified by a lifecycle event, during which source-read evidence and validation status are collected anew.
_Avoid_: Whole session, permanent state, transcript generation

**Action Journal**:
Bounded metadata-only record of material operations and their planned, started, completed, failed, approval-pending, or ambiguous status.
_Avoid_: Command log, raw tool input, transcript copy

**Degraded Mode**:
Visible read-only recovery state used when safe continuation cannot yet be proven from authoritative sources.
_Avoid_: Best effort, silent fallback, normal continuation

**Semantic Parity**:
Same observable preservation and safety guarantees across hosts despite different native controls or numeric thresholds.
_Avoid_: Identical configuration, threshold equality, shared knob

**Compaction Thrashing**:
Repeated compaction caused when summaries or automatic re-entry refill hot context too soon after a prior compaction.
_Avoid_: Normal scheduled compaction, manual task-boundary compaction

**Pilot Layer**:
Isolated Codex profile or Claude settings overlay used to activate host-specific controls without rewriting primary user configuration.
_Avoid_: Global default, installed policy copy, shared numeric threshold
