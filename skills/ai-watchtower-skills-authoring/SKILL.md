---
name: ai-watchtower-skills-authoring
description: Use when creating, reviewing, or modifying AI Watchtower skills (SKILL.md files) in the FreightHero codebase. Covers the SOP-to-Skills migration architecture, progressive disclosure tiers, broker isolation, composition layers, authoring rules, and validation. Use when the user asks how to write a skill, where to put content, how composition works, or how to validate skills. Also use during code review of any change under `ai_watchtower/app/skills/`.
---

# AI Watchtower Skills Authoring

## CRITICAL: Canonical authoring guide is mandatory

Before authoring, modifying, or reviewing **any** AI Watchtower skill content, you MUST read and follow the canonical guide:

```
ai_watchtower/docs/architecture/skills/authoring-guide.md
```

Resolve it relative to the FreightHero workspace root. Common absolute paths:

- macOS dev workspace: `/Users/edu/Desktop/freighthero/ai_watchtower/docs/architecture/skills/authoring-guide.md`
- Any other checkout: `<repo_root>/ai_watchtower/docs/architecture/skills/authoring-guide.md`

Read it in full at least once per authoring or review session. This SKILL.md is a routing index; the authoring-guide.md is the source of truth. Where this skill and the canonical guide disagree, **the canonical guide wins**.

Use this skill as a quick map; jump into the canonical guide for:

- §1 mental model, three loading tiers, FreightHero runtime facts
- §2 layer discipline (`standards/`, `intents/`, `broker-profiles/`, `workflows/`, overrides, references)
- §3 content economy (no engineering references, one term per concept, no time-sensitive content, default + escape hatch)
- §4 degrees of freedom and §4.3 no-voodoo-constants
- §5 progressive disclosure — when to extract a reference, naming, single level depth, no stubs, routing-table pattern
- §6 catalog hygiene, name contract, description contract, selection test
- §7 broker dimension — tool-table language, default-in-intent, named-procedures catalog, caller/callee contracts (§7.6.7a, §7.6.7b)
- §8 distributed self-containment, single-invocation completeness, boundary statements
- §9 evaluation-driven authoring and Claude A / Claude B loop
- §10 anti-patterns catalogue
- §11 reviewer checklist — run this as a pass/fail gate
- §12 token budgets reference
- §13 audit playbook

## Operating modes for this skill

### Authoring mode (writing or rewriting skills)

1. Open the canonical guide and skim §1, §2, §5, §8.
2. Identify the layer (§2 table). If unsure, re-read §2.1 through §2.4.
3. Draft the common path inline (§8.1) and extract conditional branches to `references/` (§5.2 triggers).
4. Apply the §11 reviewer checklist to your draft before requesting review.
5. Measure: `wc -l SKILL.md workflow-overrides/*.md` — must stay under 500 lines / ~5,000 tokens (§5.1, §12).

### Review mode (PR or diff review on `ai_watchtower/app/skills/`)

1. Re-open the canonical guide. Have §10 (anti-patterns) and §11 (reviewer checklist) in scope.
2. Walk the §11 checklist top to bottom. Mark every pass/fail.
3. Cross-check the diff against §10 anti-patterns. Flag any match with the section number (e.g., "§10.1 monolith" or "§10.4 meta-mechanism leakage").
4. Verify token budget per §5.1 / §12 using the `wc` commands.
5. For broker profile changes, verify §7.1 (no invisible tool references), §7.2 (unambiguous tool-table language), §7.3 (default-in-intent), §7.5 (no workflow logic in profile body), §7.6 (named-procedures catalog opt-in).
6. For multi-stage scenarios, verify §8.3 single-invocation completeness — no reliance on prior-invocation skill state.
7. Output findings using the `caveman-review` severity prefixes (🔴 bug, 🟡 risk, 🔵 nit, ❓ q). Cite the violated section number for every 🔴/🟡 finding.

## Purpose

Guide the agent through the AI Watchtower skills authoring system. The skills runtime replaces static SOP markdown with a progressive-disclosure, broker-isolated, workflow-scoped catalog of agent instructions. This skill ensures skills are authored correctly, placed in the right layer, and validated against the runtime's rules and the canonical authoring-guide.md.

## When to use this skill

- The user asks how to write or structure a skill
- The user asks where to put content (standards, intents, broker-profiles, workflows, references)
- The user asks how skill composition works (overrides, shipper rules, broker profiles)
- The user is reviewing skill content for correctness or efficiency
- The user is adding a new intent, broker profile, or standard
- The user asks about the skills runtime architecture
- The user is migrating SOP content to the skills tree

## When NOT to use this skill

- The task is about general AI Watchtower architecture (use `ai-watchtower-wiki`)
- The task is about backend API development or infrastructure
- The user is asking about Robin GPT or frontend code

## Core Architecture

### Progressive Disclosure Tiers

The runtime uses three loading tiers to manage token costs:

| Tier | Method | What loads | Token cost |
|---|---|---|---|
| **Tier 1: Metadata** | `get_skill_catalog()` | `name` + `description` from frontmatter | ~100 tokens/skill |
| **Tier 2: Skill body** | `load_skill()` | SKILL.md body + auto-composed overrides | Target <5,000 tokens |
| **Tier 3: References** | `load_skill_reference()` | Individual files from `references/` | Pay-per-use |

**Economic insight:** Decompose conditional content from Tier 2 (always paid) to Tier 3 (pay only when branch triggers).

### Content Layers (where content belongs)

| Content type | Layer | Example |
|---|---|---|
| Universal rule shared everywhere | `standards/` | Channel matching, escalation rules |
| Broker-specific binding or exception | `broker-profiles/` | Ally escalation model, Fort Freight TMS-only |
| Operational procedure the agent executes | `intents/` | initial-contact, unresponsive-driver |
| Workflow routing context | `workflows/` | confirm-delivery intent catalog |
| Shipper rule regardless of broker | `shipper-overrides/` | Kraft lumper-payment rule |
| Broker+shipper delta (diverges from canonical) | `broker-profiles/<broker>/shipper-overrides/` | Ally/Aldi delay-specific override |
| Rare branch detail loaded on demand | `references/` | Attachment-document routing |
| Workflow-specific add-on to shared intent | `workflow-overrides/` | confirm-delivery terminology |

### The Nine-Block Composition Model

When `load_skill()` is called, the runtime composes up to nine content blocks in order. Later blocks beat earlier ones (most-specific wins):

1. **Base intent body** — `intents/<skill>/SKILL.md`
2. **Intent × workflow override** — `intents/<skill>/workflow-overrides/*.md`
3. **Broker profile body** — `broker-profiles/<broker>/SKILL.md`
4. **Shared named-procedures catalog** — `broker-profiles/_shared/escalation-models/<model>/named-procedures.md`
5. **Broker × workflow override** — `broker-profiles/<broker>/workflow-overrides/*.md`
6. **Canonical shipper base** — `shipper-overrides/<shipper>.md`
7. **Canonical shipper × workflow** — `shipper-overrides/<shipper>/*.md`
8. **Broker shipper-delta base** — `broker-profiles/<broker>/shipper-overrides/<shipper>.md`
9. **Broker shipper-delta × workflow** — `broker-profiles/<broker>/shipper-overrides/<shipper>/*.md`

## Authoring Rules

### Rule 1: SKILL.md is a table of contents, not a book

The skill body provides an overview and routing instructions. Detailed procedures live in reference files loaded on demand via `load_skill_reference()`.

### Rule 2: The context window is a public good

Every token competes with conversation history, other skills, broker profiles, and agent reasoning. The bar for inclusion is not "is this true?" but "does the agent need this, here, now?"

Three challenges before writing any paragraph:
1. Does the agent really need this?
2. Can I assume it knows this? (Claude is capable — only add project-specific, non-obvious, or error-prone content)
3. Does this paragraph justify its token cost?

### Rule 3: Do not duplicate standards blindly

Reference standards inline when the rule is universal:
```markdown
If `reply_best_email_thread` returns `No email thread found.`, follow `standards/email-thread-exception`.
```

Keep instructions inline only when they are part of the step-by-step procedure at the agent's decision point.

### Rule 4: Intents must be complete for their scope — but not monolithic

The **common path** (most frequent trigger) must be fully inline in the intent body. **Conditional branches** belong in `references/` and are loaded on demand. Each reference is self-contained and lists all required tool calls for its branch.

### Rule 5: Scope content to the loading context

If a section would be useless when the agent is handling a different workflow, it does not belong in the base skill or broker profile. Move it to the relevant intent, workflow-override, or reference.

**Test:** "Would this section be useful regardless of which workflow or broker is active?"

**Bad:** BOL clarification flow in `broker-profiles/ally/SKILL.md` (only relevant during confirm_pickup)
**Good:** Escalation model in `broker-profiles/ally/SKILL.md` (applies to all workflows)

## Skill Frontmatter Contract

Every real skill directory must contain `SKILL.md` with YAML frontmatter:

```yaml
---
name: initial-contact
description: First contact with driver at pickup/delivery location
type: intent
workflows:
  - confirm-pickup
  - confirm-delivery
---
```

Validation rules (`SkillsService.validate_skill_format()`):
- `name` is required, must be kebab-case, must match directory name
- `description` is required (keep under 1024 chars)
- Intent skills must declare `workflows:`
- Body should stay below recommended size threshold

## Workflow Scope and Isolation

### Catalog-isolated vs hard-enforced

- **Catalog-isolated:** Intent is filtered out of Tier-1 catalog for undeclared workflows
- **Hard-enforced:** Runtime refuses to load intent outside declared workflow scope

Today, intent workflow scope is **both** catalog-isolated and hard-enforced. This prevents agents from executing procedures that lack required tools for the current workflow.

### Broker isolation

The runtime is designed so an agent for broker A cannot load broker B's profile. Enforced by:
- Slug validation and `_assert_within()` prevent filesystem escape
- `_enforce_broker_isolation()` prevents cross-broker profile access

The only exception is `default`, the fallback broker profile accessible to any broker context.

## Runtime Components

| Component | Responsibility |
|---|---|
| `app/services/skills_service.py` | Catalog scan, loading, broker isolation, composition, validation |
| `app/utils/skill_tools.py` | Agent-facing `load_skill` and `load_skill_reference` tools |
| `app/services/sop_source.py` | Variant-aware dispatcher between legacy SOPs and Skills |
| `app/utils/skills/skill_agent_factory.py` | Specialized agents for initiate_tracking-style flows |

**Critical invariant:** Always use `SkillsService` — never open skill files directly. It validates slugs, protects against path traversal, enforces broker isolation, applies fallback logic, and auto-composes overrides.

## Validation and Testing

### Format validation

Run unit tests to enforce the skill contract:
```bash
pytest tests/unit/services/test_skill_format_validation.py
```

### Workflow isolation

Verify intents are properly scoped:
```bash
pytest tests/unit/services/test_skill_workflow_isolation.py
```

### Behavioral tests (tool_only framework)

Test agent behavior against skills:
```bash
doppler run -c local -- uv run pytest tests/deep_agents/workflow/{workflow}/tool_only/ -k "<scenario>"
```

## How to Add a New Intent

1. Create directory: `app/skills/intents/<intent-slug>/`
2. Write `SKILL.md` with frontmatter (include `workflows:` list)
3. Add `references/` directory for conditional branches
4. Add `workflow-overrides/` if workflow-specific add-ons needed
5. Add intent to relevant workflow context skill under `app/skills/workflows/`
6. Verify required tools exist in `deep_agent_tools`
7. Run format validation tests
8. Write tool_only behavioral tests

## How to Add a New Broker Profile

1. Copy `app/skills/broker-profiles/_template/SKILL.md`
2. Fill in escalation model, tool mappings, guardrails
3. Add `named_procedures:` frontmatter if using Model A or B
4. Add `shipper-overrides/` if broker diverges from canonical
5. Add `workflow-overrides/` if workflow-specific exceptions
6. Verify profile loads via catalog API or `SkillsService.load_skill()`

## How to Add a New Standard

1. Create directory: `app/skills/standards/<standard-slug>/`
2. Write `SKILL.md` with universal rule
3. Reference it from intents/broker profiles instead of duplicating
4. Update any affected skills to reference the standard inline

## Key Reference Documents

Read these documents in `ai_watchtower/docs/architecture/skills/` for deep understanding:

| Document | Purpose |
|---|---|
| `authoring-guide.md` | **MANDATORY** — canonical reference for writing, reviewing, and auditing skills. Always read before authoring or reviewing. |
| `README.md` | Onboarding entry point, mental model, content tree snapshot |
| `authoring-and-operations.md` | Operations guide: validation, testing, safe additions |
| `composition-cheatsheet.md` | Quick reference for the 9-block composition model |
| `runtime-and-composition.md` | Runtime execution details, service boundaries, invariants |

## Example prompts that trigger this skill

- "How do I write a new skill?"
- "Where should I put this broker-specific rule?"
- "How does skill composition work?"
- "How do I add a new intent for confirm-delivery?"
- "How do I review a skill for token efficiency?"
- "What's the difference between standards and broker profiles?"
- "How do I add a shipper override for Kraft?"
- "How do I validate my new skill?"
- "How do references work in the skills system?"
- "How do I migrate this SOP content to skills?"

## Related skills

- `ai-watchtower-wiki` — For general AI Watchtower architecture and wiki reference
- `batman-understanding` — For structured codebase research before authoring
- `mempalace` — For persisting authoring decisions and patterns across sessions
