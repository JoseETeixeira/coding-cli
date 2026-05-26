---
applyTo: '**'
---

## CRITICAL: Visual Explainer

When the user asks for a diagram, architecture overview, diff review, plan review, project recap, slide deck, or a complex comparison table, resolve and read the user-level `visual-explainer/SKILL.md` file using the standard user-level skill resolution rules: prefer `USER_SKILLS_DIR`, then fall back to `~/.agents/skills/visual-explainer/SKILL.md`.

Prefer `visual-explainer` over ASCII art when:

- the user explicitly wants a visual explanation;
- the output would otherwise become a large table;
- the output would benefit from a browser-rendered diagram, review page, or slide deck.

Use the matching prompt template from `USER_PROMPTS_DIR` when available, such as:

- `generate-web-diagram.prompt.md`
- `generate-visual-plan.prompt.md`
- `generate-slides.prompt.md`
- `diff-review.prompt.md`
- `plan-review.prompt.md`
- `project-recap.prompt.md`
- `fact-check.prompt.md`
- `share-page.prompt.md`

Write generated HTML to `~/.agent/diagrams/` unless the user asks for another path. Open the result in a browser when the environment permits it. If browser access is blocked, report the file path and continue.

Before writing any behavioral claim about the target system into a visual-explainer artifact (demo page, project recap, architecture overview, diff review, slide deck), verify the claim against the actual code: read the default value of any feature flag you cite, confirm a code path runs by tracing the call, and grep the keyword you are about to assert ("auto-destroy", "automatic retry", "self-healing", etc.) against the source. Do not lift optimistic phrasing from CHANGELOG entries, PR descriptions, or prior summaries — those describe intent, not necessarily current runtime state. If a feature is wired but gated behind a `false`-by-default toggle, say "wired but gated" in the artifact, not "works automatically".
