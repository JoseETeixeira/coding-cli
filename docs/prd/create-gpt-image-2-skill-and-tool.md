# Product Requirements: GPT Image 2 Skill And Tool

- **Status**: approved
- **Approved**: 2026-08-02
- **Source specification**: `.batman/create-gpt-image-2-skill-and-tool/spec/requirements.md`
- **Understanding**: `.batman/create-gpt-image-2-skill-and-tool/steering/understanding.md`

## Purpose

Add one canonical `gpt-image-2` skill and one standalone local MCP server so Claude Code, Codex, and VS Code / Copilot agents can intentionally generate and edit raster images through OpenAI's direct Image API. The capability must isolate the user's API credential, validate inputs before paid calls, save durable local files safely, return bounded viewable previews, and preserve one implementation across hosts.

## Users And Outcomes

- A creator can ask an agent to generate a new image or edit local reference images without constructing API requests.
- A calling agent receives stable generate/edit schemas, useful errors, durable output paths, and small inline previews.
- A maintainer can verify normal behavior with no paid traffic, then run one explicit low-cost live smoke.
- The credential owner can use the Windows user `OPENAI_API_KEY` without placing its value in source, configuration, logs, results, fixtures, evidence, or memory.

## Approved Product Contract

### Skill

The `gpt-image-2` skill activates for explicit OpenAI-backed raster generation and editing. It chooses the correct operation, inspects local references before edits, preserves user-stated invariants, discloses external cost/moderation/latency, inspects each successful result, and performs only targeted in-scope iterations. Vector/SVG/code-native work continues to use its owning workflow.

### Tools

The standalone stdio MCP server exposes `generate_image` and `edit_image`. Both fix the model to `gpt-image-2`; neither accepts model/endpoint overrides, API keys, arbitrary headers, URLs, or OpenAI file IDs. Edit inputs are local PNG, JPEG/JPG, or WebP files, with ordered multiple references and an optional locally validated alpha mask.

### Defaults

- quality: `high`
- size: `1024x1024`
- format: `png`
- count: `n=1`
- output directory: `<working-directory>/generated-images/`
- basename: `image`
- collisions: `image.png`, `image-2.png`, `image-3.png`; never overwrite

Explicit valid controls may change quality, dimensions, output format/compression, count, moderation, opaque/auto background, basename, and absolute output directory. Transparent output is rejected because `gpt-image-2` does not support it.

### Results

All valid outputs are base64-decoded, image-validated, and safely published as local files. Results include operation/model, absolute path, MIME type, bytes, dimensions, image index, and safe available OpenAI metadata. Bounded inline MCP image previews accompany files when the approved byte/count policy permits; paths remain authoritative.

### Credentials And Errors

Credential precedence is process `OPENAI_API_KEY`, then the Windows current-user environment store. Missing credentials fail before network access. User/moderation errors are not retried unchanged; only narrowly defined transient failures may receive bounded retries. Raw prompts, inputs, image payloads, Authorization headers, and credential-bearing bodies do not enter logs or results.

### Distribution

Canonical source lives in `coding-cli`. Repository adapters and the user's current `~/.claude.json`, `~/.codex/config.toml`, and VS Code User `mcp.json` receive thin registrations targeting the canonical checkout. A merge/sync and host MCP reload are required before unrelated sessions can use the new server. Marketplace/plugin packaging and copied host bodies are excluded.

## Acceptance Summary

Completion requires:

1. Validated skill metadata and exact two-tool MCP surface.
2. Fake-backed unit and stdio tests for API shapes, validation, credentials, outputs, previews, errors/retries, and secret redaction.
3. Parsed source and user adapter configurations that preserve every existing server and contain no credential value.
4. One authorized `quality=low`, `1024x1024`, `n=1` live generation after all deterministic gates pass.
5. Visual inspection showing that the saved smoke image opens and materially follows its prompt.
6. Honest separation of mocked, live API, visual, source-registration, and actual per-host activation evidence.

## Non-Goals

No Responses API conversations, partial streaming, remote MCP deployment, URL inputs, transparent output, arbitrary model fallback, batch-job system, marketplace publication, automatic overwrite, or implicit background generation.

## Sources

- OpenAI image generation guide: https://developers.openai.com/api/docs/guides/image-generation
- Generate endpoint: https://api.openai.com/v1/images/generations
- Edit endpoint: https://api.openai.com/v1/images/edits
- Codex image generation: https://learn.chatgpt.com/docs/image-generation

Current source and approved task artifacts remain authoritative over this concise PRD if wording ever drifts.
