# FreightHero canonical agent assets

For every FreightHero repository task, read and follow `skills/freighthero-entry/SKILL.md`. This checkout is the canonical source for shared agents, prompts, instructions, and skills. Do not generate or install copies into user directories.

At the beginning of every parent entry turn, read `skills/auto-improvement/SKILL.md` and evaluate its triggers. Stay user-silent when none match. Specialists only return codification candidates; the parent previews canonical diffs and waits for explicit user approval before writing.

Before repository work, require a current Repowise snapshot and run a scoped query. Use host-native model loops, sandbox, approvals, and credentials. Only Repowise may use its scoped OpenAI API credential.
