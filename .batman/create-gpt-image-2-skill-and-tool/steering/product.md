# Product Overview

## Product Purpose

`coding-cli` is the canonical customization source for Batman agents across Claude Code, Codex, and VS Code / Copilot. This task adds a reusable `gpt-image-2` skill and a local MCP server so agents can intentionally generate or edit raster images with OpenAI's current `gpt-image-2` model without learning the HTTP API or handling credentials directly.

## Target Users

- Developers and creators who ask an agent to produce or revise image assets.
- Agents that need one shared workflow for prompting, generating, editing, saving, inspecting, and iterating.
- Maintainers who need paid API use, binary outputs, secrets, and cross-host registration to remain visible and testable.

Their main pain points are inconsistent host capabilities, duplicated image prompting logic, unsafe credential handling, ambiguous output paths, large binary MCP responses, and API failures that are hard to diagnose.

## Key Features

1. **Discoverable image workflow**: one canonical skill routes explicit raster generation and editing requests.
2. **Focused MCP operations**: separate generate and edit tools expose the direct OpenAI Image API with `gpt-image-2` fixed as the model.
3. **Safe local outputs**: decoded images are written without overwriting existing files and returned with useful metadata plus bounded inline previews.
4. **Credential isolation**: the server reads `OPENAI_API_KEY` from process scope or the Windows current-user environment and never accepts or emits the value.
5. **Cross-host availability**: thin MCP registrations cover the user's current Claude Code, Codex, and VS Code / Copilot agents.

## Business Objectives

- Let agents create useful image files through one consistent contract.
- Reduce repeated API-specific implementation and prompt-engineering work.
- Make external cost, moderation, latency, and output effects explicit.
- Keep one canonical skill/server body while host adapters remain thin.

## Success Metrics

- The new skill passes the selected skill validator and is discoverable by its intended prompts.
- Mocked unit and stdio tests cover generation, edits, validation, output saving, retries, and secret redaction without spending credits.
- One low-quality live smoke request succeeds with `gpt-image-2`, saves a valid image, and is visually inspected.
- Claude Code, Codex, and VS Code / Copilot registrations resolve to the canonical server after merge/sync and restart.
- Secret scans find no API key value or credential-bearing logs in repository artifacts or test output.

## Product Principles

1. **Explicit paid action**: generate or edit only for an explicit user request or an explicitly approved live validation.
2. **Files are primary**: persist every successful result locally; inline image content is a bounded convenience.
3. **Validate before billing**: reject locally detectable bad inputs before an API request.
4. **Canonical once**: skill and server bodies live in `coding-cli`; host configurations only point to them.
5. **Inspect, then iterate**: a successful HTTP response is not visual acceptance.

## Monitoring & Visibility

- **Dashboard Type**: structured MCP results, local output files, command-line tests, and repository evidence; no web dashboard.
- **Real-time Updates**: not required in the first release; partial-image streaming is outside scope.
- **Key Metrics Displayed**: operation, model, output paths, MIME types, dimensions, count, request ID when available, and safe failure code.
- **Sharing Capabilities**: generated files may be attached or referenced by agents; secrets and raw request bodies are never shared.

## Future Vision

### Potential Enhancements

- Conversational multi-turn editing through the Responses API.
- Streaming partial previews for long generations.
- Relocatable plugin packaging or remote deployment after the local canonical integration is proven.
- Explicit support for future image models or transparent output when the selected model supports it.
