# Task Plan: GPT Image 2 Skill And Tool

## Status

Approved for execution on 2026-08-02 under the user's explicit autonomous
authorization ("Implement everything pending ... no need to ask me, just do
it"). Authority: `spec/requirements.md`, `spec/design.md`,
`steering/constitution.md`, ADR 0015.

Scope guards that hold for every task below:

- No commit, push, merge, or broad staging (`git add -A`) unless separately
  requested.
- No edit to any file outside this task's surface; unrelated worktree changes
  are preserved.
- Exactly one paid API call is authorized, in Task 14, and only after Task 13
  is green.
- No credential value enters source, config, logs, results, fixtures, evidence,
  or memory at any point.

## Phase 4a Discovery Record

Re-ran after Design to map every design component to a concrete file:

- `find skills/gpt-image-2 -type f` -> `SKILL.md` (placeholder scaffold) and
  `agents/openai.yaml` (already real). No `references/`, no `scripts/`.
- No `gpt_image_2/`, no `run_gpt_image_2_server.py`, no `tests/gpt_image_2/`
  exists. `tests/` at the repository root exists and holds unrelated suites, so
  the new package nests under it without disturbing them.
- `mnemo/requirements.txt` establishes the per-subsystem requirements-file
  convention with inline rationale comments; the image server gets its own.
- `docs/architecture/adr/` holds 0003..0015; 0015 is this task's, at `proposed`.
- `README.md` has a "Repository layout" list and per-subsystem sections; the new
  capability appends a section and one layout bullet.
- `CHANGELOG.md` is reverse-chronological by date with a `## 2026-08-02` head
  section already open — the entry appends there.
- `.batman/create-gpt-image-2-skill-and-tool/evidence/` does not exist yet and is
  created by Task 15.

## Execution order

Tasks are ordered so that every gate that can fail cheaply runs before any gate
that costs money or touches a user-wide file.

### Task 1 — Freeze the constants and the error taxonomy

Create `gpt_image_2/__init__.py`, `gpt_image_2/constants.py`,
`gpt_image_2/errors.py`.

- Every value from the Design "API constants" and "Timing and bounds" tables,
  each with the source of its authority in a comment.
- `ImageToolError` with `code`, safe `message`, `request_id`, scalar-only
  `details`, and `to_payload()`; the 16 closed codes; `redact()` implementing
  exact-value replacement, `sk-`/`Authorization` pattern scrub, and truncation.
- Traces: IMG-REQ-003, IMG-REQ-008. Verify: import + `python -m compileall`.

### Task 2 — Credential resolution behind a non-rendering wrapper

Create `gpt_image_2/credentials.py`.

- `Secret` with `__repr__` / `__str__` / `__format__` returning `<Secret ***>`
  and a `reveal()` accessor.
- `resolve_api_key(env=..., windows_lookup=...)`: process env wins, Windows
  `HKCU\Environment` via `winreg` second (expanding `REG_EXPAND_SZ`), otherwise
  `missing_credential`. Blank/whitespace counts as absent at both layers.
- Traces: IMG-REQ-005. Verify: covered by Task 9.

### Task 3 — Local image inspection, decode, and atomic publication

Create `gpt_image_2/images.py`.

- `inspect_local_image`, `validate_mask`, `sanitize_basename`,
  `resolve_output_dir`, `decode_image_payload`, `publish_atomic` exactly as
  Design specifies, including size-check-before-open, the meaningful-alpha rule,
  reserved-Windows-name rejection, containment re-check, and the
  mkstemp + fsync + `os.link` / `O_EXCL` fallback with `finally` cleanup.
- Traces: IMG-REQ-004, IMG-REQ-006. Verify: covered by Task 10.

### Task 4 — Validated request models

Create `gpt_image_2/models.py`.

- Frozen `GenerateRequest` / `EditRequest`; `validate_generate` /
  `validate_edit` running the twelve ordered checks; `moderation` present on
  generate only; `transparent` background rejected as `unsupported_option`.
- Traces: IMG-REQ-002, IMG-REQ-003, IMG-REQ-004, IMG-REQ-006.
  Verify: covered by Task 9.

### Task 5 — OpenAI boundary with bounded retry and deadline

Create `gpt_image_2/api.py`.

- `build_client` with `max_retries=0` and the attempt timeout; `omit`-style body
  construction so `input_fidelity` is never sent; `with_raw_response` for
  `x-request-id` on success; the monotonic 180 s budget; the at-most-one retry
  restricted to explicit `429/5xx` responses with `Retry-After` support and the
  `RETRY_MIN_REMAINING_S` guard; injected `sleep`/`monotonic`/`random`; the
  total closed exception-to-code map.
- Traces: IMG-REQ-002, IMG-REQ-008. Verify: covered by Task 11.

### Task 6 — MCP server edge

Create `gpt_image_2/server.py` and `run_gpt_image_2_server.py`.

- `FastMCP("gpt-image-2")`, stderr-only logging, no `print` anywhere.
- Exactly `generate_image` and `edit_image` with the Design argument sets, the
  four `ToolAnnotations`, honest "paid / writes files / external" descriptions.
- Result assembly: full metadata for every image, `failed_images`, the bounded
  single preview with its `reason`, `attempts`, `duration_ms`.
- Failures raise `ToolError(json.dumps(payload))`.
- Entrypoint resolves the repository root from `__file__` and runs `main()`.
- Traces: IMG-REQ-001, IMG-REQ-002, IMG-REQ-007, IMG-REQ-008.
  Verify: covered by Tasks 12 and 13.

### Task 7 — Dependency manifest

Create `gpt_image_2/requirements.txt` with `mcp`, `openai`, and `pillow` floors
chosen to match the verified installed versions, each with a one-line reason.

- Traces: IMG-REQ-012. Verify: parse + install-dry check.

### Task 8 — Write the real skill body

Replace the placeholder `skills/gpt-image-2/SKILL.md` and confirm
`agents/openai.yaml`.

- Frontmatter limited to `name` + `description` (the validator's allowed set),
  hyphen-case name, no angle brackets, under 1024 description characters, with
  explicit positive and negative triggers.
- Body: operation choice, the mandatory pre-edit reference inspection, the
  "first reference is the mask target" rule, cost/moderation/~2-minute latency
  disclosure, defaults, the post-call inspect-and-compare loop, targeted-only
  iteration, and the vector/SVG deferral.
- Traces: IMG-REQ-001, IMG-REQ-012. Verify: Task 13's `quick_validate.py`.

### Task 9 — Credential and validation tests

Create `tests/gpt_image_2/conftest.py`, `test_credentials.py`,
`test_validation.py`.

- Table-driven valid and invalid matrices; every invalid case asserts the fake
  client recorded **zero** calls and the credential resolver was **never**
  invoked.
- Traces: IMG-AC-004, IMG-AC-005.

### Task 10 — Image and output tests

Create `tests/gpt_image_2/test_images.py`.

- Rejections for missing/dir/oversize/foreign-format/corrupt inputs; the three
  mask rules; basename sanitization and containment; decode format mismatch;
  collision suffix sequence; atomic publish; a pre-existing file's hash is
  unchanged after a colliding write; `.part` cleanup after an induced failure.
- Traces: IMG-AC-006.

### Task 11 — API contract, retry, and error-map tests

Create `tests/gpt_image_2/test_api.py`.

- Exact request bodies for generate and a multi-reference masked edit, asserting
  `model=gpt-image-2` and the absence of `input_fidelity`; `max_retries=0`; one
  retry on 429 and on 503; no retry on timeout, connection error, or 400;
  deadline exhaustion; `Retry-After`; request-id capture on success and failure;
  every branch of the exception map.
- Traces: IMG-AC-003, IMG-AC-008.

### Task 12 — Server surface, preview, and redaction tests

Create `tests/gpt_image_2/test_server.py`, `test_redaction.py`.

- Exact tool names and argument sets; assert `model`, `api_key`, `headers`,
  `endpoint`, `url`, `file_id`, `overwrite`, `input_fidelity` are absent from
  both schemas; annotations; metadata shape; preview included, `too_large`, and
  `multiple_images`; `ToolError` payload shape.
- A canary secret placed in the environment, in a simulated provider error body,
  and in an unexpected exception must not appear in any log record, result, or
  error payload.
- Traces: IMG-AC-002, IMG-AC-007, IMG-AC-005.

### Task 13 — Deterministic gate run

Create `tests/gpt_image_2/fake_backend.py` and `tests/gpt_image_2/mcp_smoke.py`,
then run every offline gate in order:

1. `pytest tests/gpt_image_2`
2. `python -m compileall gpt_image_2 run_gpt_image_2_server.py`
3. `python tests/gpt_image_2/mcp_smoke.py`
4. `quick_validate.py skills/gpt-image-2`
5. JSON / TOML parse of all six registrations (after Task 16) 
6. secret scan over changed files
7. `git diff --check`

- Traces: IMG-AC-009, IMG-AC-011.

### Task 14 — One authorized live generation

Create `tests/gpt_image_2/live_smoke.py` (opt-in, never pytest-collected) and
run it exactly once: `quality=low`, `size=1024x1024`, `n=1`.

- Record only model, request ID, timing, output metadata and path, pass/fail.
- Traces: IMG-REQ-011, IMG-AC-012.

### Task 15 — Visual inspection

Open the saved smoke image, confirm it decodes and materially follows the smoke
prompt, and record the finding. HTTP success alone does not pass this gate.

- Traces: IMG-AC-012.

### Task 16 — Repository registrations

Add `gpt-image-2` to `.mcp.json`, `.codex/config.toml`, `.vscode/mcp.json`,
preserving the existing `mnemo` entries byte-for-byte.

- Traces: IMG-REQ-009, IMG-AC-010.

### Task 17 — User-scope registrations

Add equivalent thin entries to `~/.claude.json`, `~/.codex/config.toml`, and
`%APPDATA%/Code/User/mcp.json`, targeting the canonical checkout.

- Read-parse-modify-write; every pre-existing server preserved; the VS Code
  JSONC file edited textually so its comments survive; no credential value
  anywhere; a before/after server-name diff recorded for each file.
- Traces: IMG-REQ-009, IMG-AC-010, IMG-AC-014.

### Task 18 — Adversarial review and fixes

Independent review of the full diff against the constitution, the requirements,
and `instructions/code-review.instructions.md`. Fix every confirmed finding and
re-run Task 13's gates.

- Traces: IMG-AC-014.

### Task 19 — Documentation

README section and layout bullet, `CHANGELOG.md` entry, ADR 0015 moved to
`accepted`, and `.batman/create-gpt-image-2-skill-and-tool/evidence/` holding the
gate results with mocked / live / visual / source-registration / per-host
activation kept strictly separate.

- Traces: IMG-REQ-012, IMG-AC-013.

## Traceability

| Requirement | Tasks |
| --- | --- |
| IMG-REQ-001 | 6, 8 |
| IMG-REQ-002 | 4, 5, 6, 11, 12 |
| IMG-REQ-003 | 1, 4, 9 |
| IMG-REQ-004 | 3, 4, 10 |
| IMG-REQ-005 | 2, 9, 12, 16, 17 |
| IMG-REQ-006 | 3, 4, 10 |
| IMG-REQ-007 | 6, 12 |
| IMG-REQ-008 | 1, 5, 11 |
| IMG-REQ-009 | 16, 17 |
| IMG-REQ-010 | 9, 10, 11, 12, 13 |
| IMG-REQ-011 | 14, 15 |
| IMG-REQ-012 | 7, 8, 19 |

| Acceptance | Tasks |
| --- | --- |
| IMG-AC-001 | 8, 13 |
| IMG-AC-002 | 6, 12 |
| IMG-AC-003 | 5, 11 |
| IMG-AC-004 | 4, 9 |
| IMG-AC-005 | 2, 9, 12 |
| IMG-AC-006 | 3, 10 |
| IMG-AC-007 | 6, 12 |
| IMG-AC-008 | 5, 11 |
| IMG-AC-009 | 13 |
| IMG-AC-010 | 16, 17 |
| IMG-AC-011 | 13 |
| IMG-AC-012 | 14, 15 |
| IMG-AC-013 | 19 |
| IMG-AC-014 | 17, 18 |
