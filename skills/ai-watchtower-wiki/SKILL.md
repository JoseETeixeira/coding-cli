---
name: ai-watchtower-wiki
description: Use when researching, understanding, or planning changes to the AI Watchtower codebase. Load this skill to enforce reading the official wiki before making architectural decisions, designing features, or modifying existing workflows. Use when the user asks about how something works in ai_watchtower, how to add a feature, or how to change architecture.
---

# AI Watchtower Wiki Reference Skill

## Purpose

Ensure the agent always consults the authoritative AI Watchtower documentation wiki before proposing architectural changes, designing new features, or explaining how existing systems work. The wiki is the source of truth for system architecture, data models, API contracts, workflow capabilities, skills, infrastructure, and operational procedures.

## When to use this skill

- The user asks how a subsystem works (e.g., "how does the queue architecture work?")
- The user asks how to add or change a feature (e.g., "how do I add a new workflow?")
- The user asks about architecture or design decisions (e.g., "why is Redis used here?")
- The user is planning a new feature and needs to understand current capabilities
- The user is modifying existing functionality and needs to know affected components
- The user asks about deployment, testing, or operational procedures

## When NOT to use this skill

- The task is a simple code edit with no architectural or design implications
- The answer is already clearly available in the open files or current context
- The user is asking about a different project (backend, frontend, robin-error-dashboard)

## Workflow

### Step 1: Identify the relevant wiki page

Clone the wiki (see Step 2) if not already present, then list available pages to find the best match for the user's question:

```bash
ls /tmp/ai_watchtower_wiki/*.md
```

Each `.md` filename is a wiki page slug (e.g. `Skills-Architecture.md`). Pick the page whose name best matches the user's topic. Read the entire page rather than just snippets — architectural understanding often depends on the full context.

### Step 2: Fetch wiki content

Prefer cloning the wiki repo for reliable access to full page content. On first use in a session (or when content may be stale), clone it:

```bash
git clone https://github.com/Freight-Hero/ai_watchtower.wiki.git /tmp/ai_watchtower_wiki --depth=1 2>/dev/null \
  || git -C /tmp/ai_watchtower_wiki pull
```

Then read the relevant page directly:

```bash
# Page filenames mirror the wiki slug, e.g. Skills-Architecture.md
read_file: /tmp/ai_watchtower_wiki/<Page-Slug>.md
```

If cloning is not possible, fall back to fetching via URL:

```
fetch_webpage: {
  urls: ["https://github.com/Freight-Hero/ai_watchtower/wiki/<Page-Slug>"],
  query: "..."
}
```

You may also browse `https://github.com/Freight-Hero/ai_watchtower/wiki` to discover pages not listed in the table above.

### Step 3: Cross-reference with code

After reading the wiki, validate the explanation against the actual codebase:

1. Use `semantic_search` or `grep_search` to find the relevant files mentioned in the wiki
2. Use `read_file` to inspect key functions, classes, or configurations
3. Use `freighthero-codebase/:explain_code` if available for detailed explanations

### Step 4: Formulate the answer or plan

Base your response on:

- What the wiki says (authoritative documentation)
- What the code confirms (current implementation)
- Any gaps between wiki and code (flag for documentation updates)

If the wiki is missing information the user needs, note it and suggest updating the wiki.

## Rules

1. **Always check the wiki first** before explaining architecture or proposing designs.
2. **Cite the wiki page** when referencing architectural facts.
3. **Validate with code** — the wiki is the intent, the code is the reality.
4. **Propose wiki updates** when you find outdated or missing documentation.
5. **Do not guess** — if the wiki and code disagree, say so and ask for clarification.

## Example prompts that trigger this skill

- "How does the skills system work?"
- "How do I add a new intent?"
- "How does multipick/multidrop work?"
- "What happens when a load is created?"
- "How do I deploy a new workflow?"
- "How does the queue architecture work?"
- "What is the data model for tasks?"
- "How do I add a new broker profile?"
- "How does Robin GPT integrate with the main app?"
- "What are the testing patterns for agent workflows?"

## Related skills

- `batman-understanding` — For structured codebase research and understanding capture
- `visual-explainer` — For generating architecture diagrams and visual summaries
- `mempalace` — For persisting architectural decisions across sessions
