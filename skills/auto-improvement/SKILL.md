---
name: auto-improvement
description: Continuously refine the active agent's own customization layer — agent definitions, skills, instruction files, and memory artifacts — without waiting for an explicit trigger. Fires whenever (a) the user answers a question you asked and the answer carries durable information, (b) the user asks you to address PR review feedback that targets agent or skill behavior, (c) the user issues a directive that is not already tracked in a PRD, Notion ticket, or repository spec, or that contradicts an existing tracked source (PRDs and tickets are NOT absolute truth — they are often AI-generated and can be wrong), or (d) the host memory file (`CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md`) crosses 40,000 characters. Agent-agnostic: resolves paths via the standard user-level customization rules so it works under Claude Code (`~/.claude/`), Codex / generic agent runtimes (`~/.agents/`), and GitHub Copilot (`.github/`). Mirrors every edit across all installed copies. Refuses to touch a small protected list of authoritative guides (mempalace, cocoindex, karpathy-guidelines).
---

## Purpose

Keep the active agent's customization layer honest, ambient, and current.
This skill is not a slash command; it is a constant background discipline.
Whenever the conversation produces durable information about how the agent
should behave, the skill considers whether that information belongs in the
customization layer and, if it does, proposes the smallest possible edit.

Three jobs, all of them ambient:

1. **Capture** the answer side of every clarifying exchange. If the user
   answers a question with information that will matter next session, the
   answer is a candidate for codification.
2. **Propagate** PR review feedback into the agent / skill / instruction
   files that govern future behavior, when the user asks for the review
   to be addressed.
3. **Compact** memory artifacts when they have grown long enough to waste
   input tokens on every session start.

Treat the customization layer as code: small surgical edits, well
justified, mirrored everywhere the file lives, and verified before
claiming completion.

---

## When this skill fires (no keywords required)

Auto-fire when ANY of the following hold. The skill does not wait for a
trigger phrase and does not require the user to invoke it explicitly.

- **Q-then-A signal.** You asked the user a clarifying question and the
  user answered with information that is durable (a preference, a
  convention, a "we always do X", a "we never do Y", a project-specific
  default). The answer is a candidate to codify.
- **PR review signal.** The user references a PR review, pastes review
  comments, or asks for review feedback to be addressed, AND the review
  contains comments about agent or skill behavior rather than one-off
  code bugs.
- **Directive signal (untracked OR contradicting).** The user issues an
  instruction that changes how the agent should behave AND **at least
  one** of:
  - the instruction is not already covered by a PRD, Notion ticket,
    GitHub issue, repository spec (`.batman/<slug>/`), or an existing
    skill / instruction file — i.e. **untracked**; or
  - the instruction directly **contradicts** the wording of a tracked
    source (the ticket says "use service A" but the user is saying
    "use service B from now on", the PRD says "skip step X" but the
    user is saying "we always run step X first").
  PRDs and Notion tickets are NOT absolute truth — they are often
  AI-generated, copied from a template, or written before the
  implementation settled. When a contradiction surfaces, the tracked
  source is a candidate to be updated, not an immovable authority.
  Always cross-check Notion / GitHub / the local spec folders before
  acting so the contradiction is real.
- **Memory size signal.** The active host's memory file
  (`$CLAUDE_CONFIG_DIR/CLAUDE.md` / `$HOME/.claude/CLAUDE.md` for
  Claude Code, `$HOME/.agents/AGENTS.md` for Codex, repo-local
  `.github/copilot-instructions.md` for Copilot, plus the workspace
  `CLAUDE.md` / `AGENTS.md` when present) exceeds **40,000 characters**.
  Threshold check runs once per session (and again whenever this skill
  writes to one of those files). When over threshold, offer compaction
  immediately via Workflow 4. The 40k floor is below Anthropic's
  ~5-min prompt-cache TTL working set and roughly the point where the
  memory file alone starts eating > 10 % of a session's input budget,
  so compaction pays for itself within a few turns.

The skill stays silent when none of these hold. Casual chat, one-off
implementation notes, debugging asides, and instructions that are
already captured somewhere authoritative AND do not contradict it are
not codification candidates.

---

## When this skill must NOT fire

- The candidate directive targets a file on the **protected list** below.
  Refuse and route to the authoritative source.
- The user explicitly says "do not codify this" or "this is one-off".
- The directive is genuinely transient (e.g. "for this commit, skip the
  changelog" — not a forever rule).
- The directive duplicates an existing rule. Cross-check before writing.

---

## Protected list (refuse all edits through this skill)

These artifacts are the source of truth for "how a thing is supposed to
work". Editing them through `auto-improvement` would let conversational
drift rewrite authoritative guidance.

Authoritative skills (refuse to edit regardless of host):

- `mempalace/`
- `cocoindex/`
- `karpathy-guidelines/`

Memory file sections that mention **mempalace** or **cocoindex** —
preserve verbatim during compaction. The user wants those sections kept
intact so future sessions still bootstrap memory and codebase indexing
correctly.

Everything else is fair game, including `codeReview.instructions.md`,
`code-patterns.md.instructions.md`, agent definitions, project skills,
and prompt templates — these are mutable and the user has explicitly
opted them into this workflow.

When in doubt, treat a file as protected and ask before editing.

---

## Agent-agnostic resolution

The skill never hardcodes host-specific paths. It resolves the target
artifact via the standard user-level customization rules (see
`BASE_SYSTEM_PROMPT.instructions.md` § "Reading User-Level Customization
Files"):

- `USER_AGENTS_DIR`
- `USER_PROMPTS_DIR`
- `USER_INSTRUCTIONS_DIR`
- `USER_SKILLS_DIR`

Known host roots the resolver should check, in priority order:

| Host | User-level root | Per-project root | Memory file |
|---|---|---|---|
| Claude Code | `$CLAUDE_CONFIG_DIR` (or `$HOME/.claude`) | repo-local `CLAUDE.md` | `CLAUDE.md` |
| Codex / generic agents | `$HOME/.agents` | repo-local `AGENTS.md` | `AGENTS.md` |
| VS Code (Copilot) | `$VSCODE_USER_PROMPTS_FOLDER` and `$VSCODE_USER_INSTRUCTIONS_FOLDER` | `.github/{agents,prompts,instructions,skills}/` | repo-local `.github/copilot-instructions.md` |
| Repository-scoped | n/a | `.github/{agents,prompts,instructions,skills}/` | n/a |

Detection: probe the environment variables first, then fall back to the
conventional paths above. Never assume a single host — the same machine
often runs more than one. After writing to one host's copy, walk the
other host roots and mirror the same edit if a counterpart file exists.

If a host root does not exist on the current machine, skip it silently.
If a counterpart file is missing but the host root exists, only create
the file when the user explicitly asks; otherwise leave the gap and
mention it in the response so the user can decide whether to install.

---

## Workflow 1 — Capture answer-side directives (the ambient default)

Trigger: a Q-then-A exchange produces durable information.

Steps:

1. Detect: parse the user's most recent answer for durable signals —
   "always", "never", "from now on", "in this project we", "use X for Y",
   "do not use Z", "prefer A over B".
2. Restate the candidate rule back to the user in one sentence. If the
   rule is ambiguous, do not codify — ask one clarifying question and
   re-run detection on the next answer.
3. Identify the narrowest scope that owns the rule:
   - **Project scope** (e.g. only one repo or one monorepo) → a
     project-specific skill (a sibling skill named after the project,
     e.g. `<project>-projects/SKILL.md`).
   - **Agent scope** (default behavior across projects) → the agent
     definition file for the active host.
   - **Workflow scope** (only during commits, only during reviews, etc.)
     → the relevant prompt file (`commit.prompt.md`,
     `prReview.prompt.md`).
4. Cross-check: is the rule already covered by an existing skill,
   instruction file, or memory entry? Use grep / `find-skills` / Notion
   search. If yes, point at the existing source instead of writing a
   duplicate.
5. Refuse if the narrowest scope lands on the protected list.
6. Draft the edit. The new rule should add the smallest possible
   instruction — never restate existing rules, never reformat
   surrounding content. Quote the conversational turn as the source.
7. Pre-show the diff. Wait for explicit user approval before writing.
8. Apply across every installed host root (mirror rule below).

---

## Workflow 2 — Address PR review feedback

Trigger: the user asks you to address a PR review AND at least one
review comment targets agent or skill behavior.

Steps:

1. Read every review comment relevant to the requested scope. Prefer the
   `github` MCP tools (`pull_request_read`,
   `add_comment_to_pending_review`) over `gh` for fetching.
2. Classify each comment:
   - **Code change** → handle through normal implementation, not this
     skill.
   - **Behavior / convention change** → belongs in agent / skill /
     instruction files. Continue with this workflow.
   - **Documentation change** → belongs in the project's docs folder.
     Out of scope for this skill.
3. For each behavior comment, pick the smallest owning file. Refuse if
   the owning file is on the protected list.
4. Draft the edit. Quote the review comment in the diff commentary so
   future readers can trace the rule back to its source.
5. Pre-show the diff. Wait for explicit user approval before writing.
6. Apply across every installed host root (mirror rule below).
7. Sanity check: re-read the changed file and confirm the new guidance
   does not contradict a protected guide. If it does, revert and ask the
   user to reconcile.

---

## Workflow 3 — Directive (untracked OR contradicting)

Trigger: the user issues an instruction that changes agent behavior AND
either the instruction is not already tracked, OR the instruction
contradicts an existing tracked source. PRDs and Notion tickets are
**not absolute truth** — they are often AI-generated, copied from a
template, or written before the implementation settled. Treat them as
*candidates* to be updated when the user contradicts them, not as
immovable authorities.

Steps:

1. Search for an existing tracked version of the same instruction:
   - active PRD / Notion ticket (use `notion-search` / `notion-fetch`),
   - open GitHub issues (`search_issues`),
   - active Batman spec (`.batman/<slug>/`),
   - existing skill / instruction / agent file (grep `USER_*_DIR` and
     the workspace `coding-cli/{prompts,skills}/`).
2. Compare the user's directive to whatever the search returns.
   Three branches:

   **Branch A — no tracked source found.** Directive is genuinely
   new. Follow Workflow 1 step 3 onward (narrowest scope, refuse on
   protected list, draft, diff, approve, mirror). Optionally offer to
   file a PRD / Notion ticket so the directive also has a tracked home.

   **Branch B — tracked source agrees with the directive.** The
   directive is a restatement of work already on record. Point at the
   existing source. Do not duplicate it in the agent layer; that
   creates two places to keep in sync.

   **Branch C — tracked source CONTRADICTS the directive.** This is
   the interesting case. The user's wording is the new truth; the
   tracked source is stale. Do not refuse, do not silently route to
   the stale source, and do not silently shadow it in the agent
   layer. Instead:

   a. Quote both sides of the contradiction back to the user — the
      tracked source's wording AND the new directive — so the
      contradiction is explicit.
   b. Ask the user where the new wording should land. The default
      menu, recommended option first:
        i.   Update the tracked source (PRD / Notion ticket /
             GitHub issue / `.batman/<slug>/` spec) so it matches
             the new directive. Most common when the tracked source
             is AI-generated or stale.
        ii.  Codify in the agent layer (skill / instruction / agent
             definition) and leave the tracked source as-is.
             Appropriate when the tracked source is intentionally
             historical (e.g. "this is what we decided last quarter,
             but going forward...").
        iii. Both — update the tracked source AND codify in the
             agent layer (rare; mostly when the directive is the
             agent's protocol for handling the ticket's content).
   c. Whichever option the user chooses, apply through the appropriate
      tool (Notion update, GitHub issue edit, spec file edit, or the
      skill / agent / instruction edit path) and pre-show every diff
      before writing. The contradiction itself is part of the audit
      trail and is included in the commit message / Notion comment so
      future readers see what changed and why.
   d. Never silently overwrite a tracked source. Each update must
      have user approval AND a comment that names the contradiction.

3. Refuse if any candidate target lands on the protected list.

---

## Workflow 4 — Memory compaction

Trigger: the user asks to compact a memory file, OR — **as the
ambient automatic case** — the active host's memory file exceeds
**40,000 characters**. The 40k threshold check runs:

- once per session, the first time the file is read or referenced;
- again after every edit this skill makes to one of the memory files
  (so a Workflow 1 / 2 / 3 write that pushes the file over the
  threshold offers compaction immediately on the same turn);
- on demand if the user names a memory file in conversation.

Memory files this skill watches:

- `$CLAUDE_CONFIG_DIR/CLAUDE.md` and `$HOME/.claude/CLAUDE.md` (Claude
  Code);
- `$HOME/.agents/AGENTS.md` (Codex / generic agent runtimes);
- repo-local `CLAUDE.md`, `AGENTS.md`, and
  `.github/copilot-instructions.md` when present in the active
  workspace.

Steps:

1. Measure the target file with `wc -c` (or `len(read_text())`).
   If size ≤ 40,000 characters and the user did not explicitly ask
   for compaction, exit Workflow 4 silently.
2. When over threshold, surface the size in the response and ask the
   user to confirm compaction. Phrasing template:
   `"<path> is <N> characters (over the 40k threshold). Compact now?"`
   Do not proceed without an explicit yes.
3. On approval, resolve the target file via the standard
   customization-file rules. Confirm the path with the user when more
   than one candidate exists.
4. Read the full current contents. Identify each top-level section.
5. Classify each section:
   - **Protected**: any section about MemPalace or CocoIndex, or that
     duplicates content from a protected skill. Keep verbatim.
   - **Compactable**: workflow guardrails, style preferences, history
     notes, repeated boilerplate.
6. Delegate to the existing `caveman:compress` skill for compactable
   sections. The compress skill writes a human-readable `.original.md`
   backup; keep that backup.
7. Stitch the compacted output back together with the protected
   sections verbatim. Section order and headings stay the same so
   existing links and grep patterns still resolve.
8. Diff the result against the original. Pre-show the diff. Wait for
   explicit user approval before writing.
9. After write, re-measure with `wc -c` and report the new size. If
   still over 40k, name the residual sections that resisted
   compaction so the user can decide whether to remove or rewrite
   them by hand.
10. Re-open the file and verify the protected sections are
    byte-identical to the pre-compaction copy. If they are not,
    restore from `.original.md` and report the discrepancy.

Hard limits:

- Never compact a memory file without explicit user approval, even
  when the 40k threshold has tripped. The auto-trigger surfaces the
  candidate; the user authorizes the write.
- Never delete a section unless the user names it.
- Never inline a protected guide's content into a compacted file —
  keep the reference / pointer instead so the canonical source stays
  the only copy.
- Threshold is by **characters**, not tokens. Characters are
  deterministic across hosts and trivial to measure with `wc -c`,
  which keeps the trigger reproducible regardless of the active
  tokenizer.

---

## Mirror rule

Every file this skill edits exists in multiple host roots. Walk all of
them and apply the same edit; never leave one root stale.

For each artifact class, mirror to every root the resolver finds on the
current machine:

| Class | Roots to walk |
|---|---|
| Skill `SKILL.md` | `$USER_SKILLS_DIR/<name>/SKILL.md`, plus `$HOME/.claude/skills/<name>/SKILL.md`, `$HOME/.agents/skills/<name>/SKILL.md`, workspace `coding-cli/skills/<name>/SKILL.md`, repo `.github/skills/<name>/SKILL.md` |
| Agent definition | `$USER_AGENTS_DIR/<name>.{agent.,}md`, plus `$HOME/.claude/agents/<name>.md`, `$HOME/.agents/agents/<name>.agent.md`, workspace `coding-cli/prompts/<name>.agent.md`, repo `.github/agents/<name>.agent.md` |
| Global instructions | `$USER_INSTRUCTIONS_DIR`, plus `$HOME/.claude/CLAUDE.md`, `$HOME/.agents/AGENTS.md`, workspace `coding-cli/prompts/BASE_SYSTEM_PROMPT.instructions.md`, repo `.github/copilot-instructions.md` |
| Prompt template | `$USER_PROMPTS_DIR/<name>.prompt.md`, plus workspace `coding-cli/prompts/<name>.prompt.md`, repo `.github/prompts/<name>.prompt.md` |

Resolution rules:

- Probe environment variables first
  (`USER_SKILLS_DIR`, `USER_AGENTS_DIR`, `USER_INSTRUCTIONS_DIR`,
  `USER_PROMPTS_DIR`, `VSCODE_USER_PROMPTS_FOLDER`,
  `VSCODE_USER_INSTRUCTIONS_FOLDER`, `CLAUDE_CONFIG_DIR`).
- Then check the conventional roots from the agent-agnostic table.
- Skip a root silently when it does not exist.
- After every mirror cycle, run `diff` between every pair the resolver
  found and confirm they are byte-identical (or name an intentional
  divergence in the response so the user can audit).

Never hardcode host usernames or absolute paths. Resolution happens at
edit-time so the same skill works under Claude Code, Codex, Copilot, and
generic agent runtimes without modification.

---

## Guardrails

- **No invented content.** Every new rule cites its source — the
  conversational turn, the PR URL, the review comment, or the file
  location. If you cannot cite the source, do not write the change.
- **Pre-show every diff.** The user approves before any file is
  written. This skill never auto-writes.
- **Refuse on the protected list.** When a candidate edit targets a
  protected file, refuse and explain. Suggest the appropriate
  authoritative path instead.
- **Single concern per edit.** Compaction, PR-review changes, and
  conversational codifications are separate; each gets its own
  pre-shown diff and its own approval.
- **codeReview before commit.** Apply the standard codeReview pass on
  the diff before any commit, per the global "codeReview before commit"
  rule.
- **Honor `compress` invariants.** When delegating to
  `caveman:compress`, let the compress skill own the file format. Do
  not post-edit the compressed output.
- **Never lose information.** Compaction preserves substance; the
  `.original.md` backup is the safety net but reading the diff before
  approval is the primary defense.
- **Stay quiet when there is no candidate.** Silence is the correct
  output for most turns. Ambient does not mean noisy.

---

## Quick decision tree

- **User just answered a clarifying question with durable content?** →
  Workflow 1.
- **User asked to address a PR review?** → Workflow 2.
- **User issued a directive that has no tracked home?** →
  Workflow 3 / Branch A.
- **User issued a directive that contradicts a PRD / Notion ticket /
  GitHub issue / spec?** → Workflow 3 / Branch C. Surface both sides,
  let the user pick: update the tracked source, codify in the agent
  layer, or both. The tracked source is not absolute truth.
- **Active host memory file > 40,000 characters, OR user asked to
  compact?** → Workflow 4.
- **Target is on the protected list?** → Refuse, explain, route to the
  authoritative source.
- **None of the above?** → Silence.

---

## Expected outcome

Following this skill should make the customization layer:

- Pick up answers, review feedback, and untracked directives the first
  time they appear, without the user having to remember a trigger
  phrase.
- Stay in sync across Claude Code, Codex, Copilot, and the workspace
  `coding-cli/` copy without per-host duplication.
- Shrink instead of grow over time, with protected sections kept
  verbatim.
- Never rewrite an authoritative guide or shadow tracked work in a
  PRD / Notion ticket.
