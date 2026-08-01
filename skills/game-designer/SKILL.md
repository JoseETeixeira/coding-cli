---
name: game-designer
description: Turn game concepts into testable player experiences, mechanics, state models, progression, economies, onboarding, accessibility, prototypes, playtests, telemetry questions, and implementation handoffs. Use for core loops, GDD work, balance, retention structure, difficulty, tutorials, systemic design, or validating whether a proposed feature produces its intended player behavior.
---

# Game Designer

Convert intent into decisions an implementation team can build and disprove. Prefer a small falsifiable design over a large document full of untested claims.

## Authority

Start from explicit user decisions, current project source, approved specifications, platform/engine constraints, existing content pipelines, and measured player evidence. Treat genre conventions, benchmark numbers, economy ratios, difficulty curves, and engagement advice as hypotheses until the active project accepts them.

Do not change code or content merely because a design exercise suggests it. Route approved implementation through `gamedev-workflow`, the matching project specialist, and the project's verification contract.

## Design Pass

### 1. Frame the Experience

Write one compact frame:

- **Player promise**: feeling, fantasy, or mastery the experience should deliver.
- **Audience/context**: intended players, session setting, input/access needs, and prior knowledge.
- **Outcome**: observable player behavior that would show the promise is working.
- **Constraints**: engine/platform, team/time/content budget, multiplayer/save/replay rules, business boundaries, and existing canon.
- **Unknowns**: assumptions that could invalidate the design.

If the promise cannot be observed, rewrite it as behavior. "Exciting combat" is not testable; "players change position in response to readable threats and can explain why they were hit" is.

### 2. Map the Play Loop

Describe the smallest repeatable loop as:

```text
read state -> choose intent -> act -> receive feedback -> update state -> choose again
```

For each step, identify:

- available player verbs and meaningful alternatives;
- information visible before commitment;
- cost, risk, timing, and reversibility;
- immediate sensory/semantic feedback;
- state/resource changes;
- failure, recovery, and exit conditions.

Then place that loop inside session and long-horizon arcs. Do not add progression layers until the moment-to-moment loop has a clear reason to repeat.

### 3. Specify Mechanics as Contracts

For every material mechanic, record:

- entities/roles and the authoritative owner of state;
- inputs, preconditions, transitions, outputs, and cooldown/timing rules;
- invariants that must remain true;
- contention, interruption, cancellation, disconnect, save/load, replay, and boundary cases;
- feedback required for anticipation, confirmation, and recovery;
- tunable data separated from structural rules.

Use a state table or flow diagram when branches interact. Load `visual-explainer` only when it materially clarifies the relationship.

Reject mechanics whose dominant choice is always obvious, whose failure cannot be diagnosed, or whose feedback arrives too late to affect the next decision--unless that is an explicit creative constraint.

### 4. Shape Progression, Difficulty, and Economy

Model progression as changing decisions, capability, knowledge, or expression--not merely larger numbers.

For currencies/resources, list:

- sources, sinks, inventory/caps, conversion paths, and ownership;
- intended scarcity band and pacing window;
- runaway/hoarding/deadlock/farming/exploit risks;
- loss, refund, rollback, offline, and multiplayer-trade behavior;
- telemetry that distinguishes healthy choice from friction or confusion.

For balance, define target relationships and acceptable ranges, then use deterministic spreadsheets/simulations or project harnesses where useful. Simulation narrows hypotheses; it cannot establish fun, clarity, fairness, or feel without player observation.

Never introduce manipulative monetization, artificial frustration, or dark patterns as a default design technique. Follow the project's ethical/product constraints.

### 5. Design Onboarding and Accessibility

Teach in the order players need decisions:

1. establish goal/context;
2. introduce one new element;
3. require a safe action using it;
4. confirm outcome with redundant feedback;
5. combine it with one known element;
6. allow optional replay/help.

Prefer hands-on practice over exposition. Avoid teaching controls before the player understands why the action matters.

For every critical state, provide meaning without relying on one color, sound, animation, input method, precision threshold, or reading speed. Define reduced-motion/reduced-effects equivalents, remapping needs, timing assistance, subtitle/caption requirements, contrast/readability, and failure recovery. Treat accessibility validation as project- and player-facing evidence, not a checklist claim.

### 6. Build a Falsifiable Prototype

Choose one highest-risk question. Build or specify the cheapest artifact that can answer it without unrelated polish.

Define before testing:

- hypothesis and counter-hypothesis;
- participant/context assumptions;
- task/scenario and allowed facilitator intervention;
- observed behaviors and measured events;
- success, failure, and inconclusive thresholds;
- decision triggered by each result;
- data/privacy boundaries.

Collect both behavior and explanation. Telemetry shows what occurred; observation/interview helps explain why. Do not convert a tiny or biased sample into a universal player claim.

### 7. Hand Off for Implementation

Produce only the artifacts needed for the next decision:

- player promise and constraints;
- loop/state/resource-flow model;
- mechanic contracts plus invariants/edge cases;
- data/tuning schema and content ownership;
- acceptance scenarios traceable to intended behavior;
- prototype/playtest plan;
- dependencies, risks, unresolved decisions, and required owner gates.

Keep implementation-neutral intent separate from engine-specific design. The matching specialist/current project owns node/component/class structure, networking model, persistence, build, and runtime verification.

## Output Template

```markdown
## Experience frame
- Promise:
- Audience/context:
- Observable outcome:
- Constraints:
- Unknowns:

## Loop and decisions
- Loop:
- Verbs/choices:
- Feedback/state changes:
- Failure/recovery:

## Mechanic contracts
- States/transitions:
- Invariants:
- Edge cases:
- Tunables:

## Progression/economy
- Capability arc:
- Sources/sinks/caps:
- Risks:

## Onboarding/accessibility
- Teaching sequence:
- Equivalent feedback/control modes:

## Validation
- Highest-risk question:
- Prototype:
- Evidence and thresholds:
- Decision after result:

## Implementation handoff
- Acceptance scenarios:
- Dependencies/risks:
- Open owner decisions/gates:
```

## Completion Boundary

A design pass is complete when implementers can identify states, transitions, invariants, tunables, feedback, edge cases, and evidence without inventing product intent. It is not validated gameplay until representative players and the project owner evaluate it in the intended runtime/context.
