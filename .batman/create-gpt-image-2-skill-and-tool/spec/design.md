# Design: GPT Image 2 Skill And Tool

## Status

Approved for implementation on 2026-08-02 under the user's explicit autonomous
authorization ("Implement everything pending ... no need to ask me, just do
it"), which consumes the Phase 3 and Phase 4 approval gates for this task only.
Authority order is unchanged: current source, the approved
`spec/requirements.md`, `steering/constitution.md`, and ADR 0015 outrank this
document wherever wording drifts.

Governing artifacts:

- Requirements: `.batman/create-gpt-image-2-skill-and-tool/spec/requirements.md`
- Constitution: `.batman/create-gpt-image-2-skill-and-tool/steering/constitution.md`
- Technology / structure foundations: adjacent `steering/tech.md`, `steering/structure.md`
- PRD: `docs/prd/create-gpt-image-2-skill-and-tool.md`
- Decision: `docs/architecture/adr/0015-standalone-gpt-image-2-mcp-server.md`

## Phase 3a Discovery Record

Discovery ran before this draft and was read-only except for copying the
task's own untracked Phase 1/2 artifacts forward from the sibling planning
worktree into the implementation worktree.

Queries and reads performed:

- `git worktree list`, `git status --short`, `git branch -a` located the task's
  Phase 1/2 artifacts as untracked files in
  `coding-cli.worktrees/create-a-gpt-image-2-skill-and-tool`. `design.md`
  (170 B) and `tasks.md` (167 B) were explicit "not drafted" stubs;
  `skills/gpt-image-2/SKILL.md` (4,035 B) was an unmodified `init_skill.py`
  scaffold whose every section is a `[TODO: ...]` placeholder;
  `skills/gpt-image-2/agents/openai.yaml` (212 B) already held real interface
  metadata. ADR 0015 existed at status `proposed`.
- mnemo `task_context` / `memory_search` (namespace `repo:coding-cli`) returned
  the Phase 1 and Phase 2 approval checkpoints (`memory_id`
  `25980152-3285-42c6-8305-3c197fdfa164`, `b6549fc6-0c4f-42e9-80f9-ffd51289c4b3`)
  and no Phase 3/4 checkpoint, confirming Design was never drafted.
- `mnemo/run_server.py`, `mnemo/mnemo/server.py:1-80`, `mnemo/requirements.txt`,
  and `mnemo/tests/mcp_smoke.py` fixed the repository's stdio-server precedent:
  a `sys.path`-repairing root entrypoint, a FastMCP module with stderr-only
  `logging.basicConfig(stream=sys.stderr, ...)`, lazy resource construction so
  import and `tools/list` need no credential or network, and an
  `mcp.client.stdio` driven smoke script.
- `.mcp.json`, `.codex/config.toml`, `.vscode/mcp.json` confirmed the three
  repository adapter shapes (`mcpServers` / `mcp_servers` / `servers`), each
  currently holding only `mnemo`.
- User registries were inspected without printing values: `~/.claude.json`
  carries `mcpServers` = `godot-mcp-pro, byond-rag, mnemo, elevenlabs`;
  `~/.codex/config.toml` carries `[mcp_servers.byond-rag]`,
  `[mcp_servers.openaiDeveloperDocs]`, `[mcp_servers.godot-mcp-pro]`; the VS Code
  User `mcp.json` at `%APPDATA%/Code/User/mcp.json` exists and is JSONC
  (comments present — a plain `json.load` fails, so edits must preserve
  comments). `~/.codex/config.toml` also demonstrates the exact secret-free
  forwarding idiom this task needs: `env_vars = ["OPENAI_API_KEY"]` on
  `[mcp_servers.byond-rag]`.
- Runtime probes: CPython 3.12.10, `openai` 2.8.1, `mcp` 1.26.0, `Pillow` 12.1.1
  are installed at
  `C:/Users/josee/AppData/Local/Programs/Python/Python312/python.exe`.
- SDK introspection of `openai.resources.images.AsyncImages.generate` / `.edit`
  fixed the exact parameter surface, including that `moderation` and `style`
  exist only on `generate`, that `edit` additionally exposes `input_fidelity`
  and `mask`, and that `model` is typed `Union[str, ImageModel, None]` while the
  `ImageModel` literal in 2.8.1 still enumerates only
  `dall-e-2, dall-e-3, gpt-image-1, gpt-image-1-mini`.
- `mcp.server.fastmcp.utilities.func_metadata._convert_to_content` confirmed that
  a returned `list` is flattened element-wise, that an `Image` becomes
  `ImageContent`, and that a non-`str` element is JSON-serialized — so a single
  tool can return one bounded image block plus one JSON metadata block.
- `mcp.types.ToolAnnotations` exposes exactly
  `title, readOnlyHint, destructiveHint, idempotentHint, openWorldHint`.
- The `skill-creator` helpers resolve to
  `~/.codex/skills/.system/skill-creator/scripts/{init_skill,generate_openai_yaml,quick_validate}.py`.
  `quick_validate.py` was read: it allows only
  `name, description, license, allowed-tools, metadata` in frontmatter, requires
  hyphen-case `name` (<= 64 chars) and an angle-bracket-free `description`
  (<= 1024 chars).
- Live documentation check against
  `https://developers.openai.com/api/docs/guides/image-generation` confirmed the
  `gpt-image-2` constants recorded in "API constants" below.

Outcome: no existing image module, tool, or registration to extend; the design
adds one new Python subsystem, one skill body, six registrations, and a test
package, and reuses the mnemo entrypoint/logging/smoke precedents.

## API constants verified against current documentation

Recorded here because Requirements demand a single validated source and because
these values drive validation. Confirmed 2026-08-02 from the OpenAI image
generation guide; the implementation isolates them in one module so drift is a
one-file change.

| Control | Verified rule |
| --- | --- |
| Model | `gpt-image-2` exists and is the current GPT Image model |
| Size | `auto`, or width/height that are multiples of `16px` |
| Size — edge | maximum edge `<= 3840px` |
| Size — aspect | long edge : short edge `<= 3:1` |
| Size — total pixels | `>= 655,360` and `<= 8,294,400` |
| Quality | `low`, `medium`, `high`, `auto` |
| Output format | `png` (default), `jpeg`, `webp` |
| `output_compression` | `0..100`, JPEG/WebP only |
| Background | `opaque` or `auto`; **`gpt-image-2` does not support transparent** |
| Moderation | `auto` (default), `low` — `generate` only; the edit endpoint has no `moderation` parameter |
| `input_fidelity` | documentation states: for `gpt-image-2`, **omit** — the API does not allow changing it |
| Response | base64-encoded image data |

Undocumented publicly and therefore treated as local policy caps, not as
claims about the service: `n` range (Requirements fix `1..10`), maximum prompt
characters (Requirements fix `32,000`), edit input count (constitution fixes
`16`), and edit input size (Requirements fix `50 MB`). Each is enforced locally
and each failure message says the bound is a local policy limit.

Two drift hazards are designed for explicitly:

1. `ImageModel` in `openai` 2.8.1 does not list `gpt-image-2`. The literal is a
   type hint only; at runtime the SDK forwards `model` as a plain string. The
   implementation passes the constant through and does not pin itself to the
   SDK's enum.
2. `size` on both SDK methods is typed as a closed `Literal` that omits the
   larger `gpt-image-2` dimensions (`2048x2048`, `3840x2160`, ...). Again a hint
   only; the request body carries the string verbatim. Validation is ours, not
   the SDK's, which is exactly what Requirements IMG-REQ-003 asks for.

## Architecture

```text
skills/gpt-image-2/SKILL.md          agent-facing: when to call, how to inspect, how to iterate
        |  (decides)
        v
MCP stdio server  "gpt-image-2"      run_gpt_image_2_server.py -> gpt_image_2.server
        |
        +-- server.py        protocol edge: schemas, annotations, presentation, ToolError
        +-- models.py        pure validation -> frozen request objects        (no network, no MCP)
        +-- images.py        local image inspection, decode, atomic publish   (no network, no MCP)
        +-- credentials.py   process env -> Windows user store                (no MCP)
        +-- api.py           OpenAI boundary: client, retry, deadline, mapping
        +-- errors.py        closed safe error taxonomy + redaction
        +-- constants.py     every API/policy constant, single owner
```

Dependency direction is strictly inward-to-outward: `constants` and `errors`
depend on nothing local; `credentials`, `images` depend on those; `models`
depends on `constants`, `errors`, `images`; `api` depends on everything except
`server`; only `server.py` imports `mcp`. No module below `server.py` imports
MCP types, and no module except `api.py` imports `openai`. This is what makes
the whole validation and file-publication surface testable without stdio or a
network.

### Deviation from `steering/structure.md`

`structure.md` sketched six modules; this design uses seven by splitting
`constants.py` out of `models.py`. Recorded in Complexity Tracking below.

## Component design

### `constants.py` — single owner of every bound

Holds the model id, the verified API constants table above, the local policy
caps, and the timing/preview budget. Nothing else in the package hard-codes a
limit; `server.py` tool descriptions state limits in prose but the enforcement
constants live here only.

Timing and bounds (from the constitution):

| Constant | Value | Source |
| --- | --- | --- |
| `API_ATTEMPT_TIMEOUT_S` | `150.0` | constitution "Performance" |
| `OPERATION_DEADLINE_S` | `180.0` | constitution "Performance" |
| `MAX_API_ATTEMPTS` | `2` (one retry) | ADR 0015 |
| `RETRY_BASE_DELAY_S` / `RETRY_MAX_JITTER_S` | `2.0` / `1.0` | this design |
| `RETRY_MIN_REMAINING_S` | `20.0` | this design |
| `RETRYABLE_STATUS` | `429, 500, 502, 503, 504` | requirements IMG-REQ-008 |
| `MAX_INLINE_PREVIEW_BYTES` | `5 * 1024 * 1024` | constitution section 6 |
| `MAX_INLINE_PREVIEWS` | `1` (first image only) | constitution section 6 |
| `MAX_EDIT_IMAGES` / `MAX_EDIT_FILE_BYTES` | `16` / `50 MB` | constitution section 3 |
| `MAX_BASENAME_CHARS` / `MAX_COLLISION_SUFFIX` | `64` / `9999` | this design |

### `errors.py` — closed taxonomy, redaction at the boundary

One `ImageToolError` base carrying `code`, a safe `message`, optional
`request_id`, and a `details` mapping restricted to scalars. `to_payload()`
produces the exact JSON the MCP layer surfaces. Codes are a closed set:

`invalid_request`, `unsupported_option`, `invalid_input_file`, `invalid_mask`,
`missing_credential`, `moderation_blocked`, `user_error`, `authentication_error`,
`access_denied`, `rate_limited`, `service_error`, `api_timeout`,
`connection_error`, `deadline_exceeded`, `output_error`, `internal_error`.

Redaction is defence in depth, applied to every string that leaves the process:

1. exact-value replacement of the resolved credential when one was resolved;
2. a pattern scrub for `sk-`-style tokens and `Authorization:` headers, so a
   value that never reached us (an SDK echo, a proxy error page) is still
   removed;
3. a hard truncation so a raw HTML/JSON error body can never be relayed whole.

`internal_error` is the only code produced from an unexpected exception, and it
carries the exception *type name* only — never `str(exc)`.

### `credentials.py` — resolve late, never format

`Secret` is a thin wrapper whose `__repr__`, `__str__`, and `__format__` all
return `<Secret ***>`; the value is reachable only through `.reveal()`. This
turns the most likely leak (an f-string in a log line or a traceback frame
repr) into a no-op.

`resolve_api_key(env=..., windows_lookup=...)` implements IMG-REQ-005
precedence:

1. non-blank `OPENAI_API_KEY` in the process environment wins;
2. otherwise, on Windows only, read `OPENAI_API_KEY` from
   `HKEY_CURRENT_USER\Environment` via `winreg`, expanding `REG_EXPAND_SZ`;
3. otherwise raise `missing_credential` with an actionable message and no value.

Both seams are injected so tests cover precedence, the Windows fallback, and
the missing case on any platform. Resolution happens inside the tool call,
immediately before client construction and strictly after validation — so
`tools/list` and every rejected request touch no credential at all.

### `models.py` — validate everything knowable, before anything costly

Two frozen dataclasses, `GenerateRequest` and `EditRequest`, are constructible
only through `validate_generate(...)` / `validate_edit(...)`. Both raise
`ImageToolError` with an `invalid_request` / `unsupported_option` family code
and never partially apply. Validation order is fixed and tested:

1. `prompt` — non-blank after strip, `<= 32,000` characters.
2. `quality` in `auto|low|medium|high` (default `high`).
3. `output_format` in `png|jpeg|webp` (default `png`).
4. `output_compression` — `None` unless format is JPEG/WebP; `0..100`.
   PNG + compression is an explicit local failure.
5. `background` — `auto|opaque`. `transparent` returns `unsupported_option`
   naming `gpt-image-2` and is never silently rewritten.
6. `moderation` — `auto|low`, **generate only**. Supplying it to `edit_image`
   is a schema-level absence, not a silently dropped field.
7. `n` — integer `1..10` (default `1`).
8. `size` — `auto`, or `W x H` where both parse as integers, both are multiples
   of 16, both `>= 16`, `max(W,H) <= 3840`, `max/min <= 3.0`, and
   `655,360 <= W*H <= 8,294,400`. Default `1024x1024`.
9. `output_dir` — when supplied it must be absolute (`Path.is_absolute()` plus
   an explicit drive/UNC check on Windows so `\foo` is rejected); when omitted
   it resolves to `Path.cwd() / "generated-images"` **at call time**.
10. `basename` — when omitted, the generic `image`; otherwise sanitized.
11. edit only: `image_paths` — 1..16 entries, each an existing regular file,
    each `< 50 MB`, each decodable by Pillow as PNG/JPEG/WebP, order preserved.
12. edit only: `mask_path` — optional; must match reference #1's pixel
    dimensions and format, and must carry a meaningful alpha channel.

Every failure names the offending field or path and nothing else — no directory
listings, no neighbouring filenames, no image bytes.

### `images.py` — filesystem and pixel policy

- `inspect_local_image(path)` — `Path.is_file()` (rejects directories, devices,
  and missing paths), `stat().st_size` against the 50 MB cap **before** opening,
  then a single `PIL.Image.open` whose `.format` must be in the allowed set.
  Verification and dimension read happen from one decode of the file bytes held
  in memory, satisfying the "do not decode an input twice" NFR.
- `validate_mask(mask, first_reference)` — dimensions equal, format equal, and a
  *meaningful* alpha channel: the image must expose an `A` band whose extrema
  are not `(255, 255)`. A fully opaque alpha is rejected because it selects
  nothing and would produce a paid no-op.
- `sanitize_basename(raw)` — strip directory separators and drive letters, drop
  control characters and `<>:"/\|?*`, collapse whitespace, strip leading dots
  and trailing dots/spaces (Windows), reject reserved device names
  (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`, case-insensitively),
  truncate to 64 characters, and fail closed with `invalid_request` when
  nothing survives. The result is then re-checked for containment: the resolved
  join must still have the output directory as its parent.
- `decode_image_payload(b64, expected_format)` — strict base64 decode, then a
  Pillow decode whose reported format must equal what was requested. A mismatch
  or a decode failure is `output_error`, not a written file.
- `publish_atomic(data, dest_dir, basename, extension)` — the no-overwrite
  primitive:
  1. `mkdir(parents=True, exist_ok=True)` on the destination;
  2. write to `tempfile.mkstemp(dir=dest_dir, suffix=".part")`, then `flush` +
     `os.fsync` + close, so a crash cannot leave a short file under a real name;
  3. compute the candidate name (`image.png`, then `image-2.png`, ...);
  4. publish with `os.link(tmp, target)`, which fails with `FileExistsError`
     rather than clobbering; on success `os.unlink(tmp)`. If the filesystem
     rejects hard links, fall back to `os.open(target, O_CREAT|O_EXCL|O_WRONLY)`
     and copy — still no-overwrite, still atomic on the name;
  5. on `FileExistsError`, advance the suffix and retry up to `MAX_COLLISION_SUFFIX`;
  6. `finally`: remove the temporary file if it still exists, on every path
     including failure, so a partial run leaves no `.part` residue.

  Because step 4 is a create-exclusive operation, two concurrent servers racing
  for `image.png` cannot both win, and neither can damage a pre-existing file.

Multi-image responses decode **all** images before publishing **any**. If any
image in the batch fails to decode, the already-published files are reported
and the failed indices are reported, and nothing invalid is written — this is
IMG-REQ-006's "no invalid partial file".

### `api.py` — the only module that touches the network

- `build_client(secret)` returns
  `AsyncOpenAI(api_key=secret.reveal(), max_retries=0, timeout=API_ATTEMPT_TIMEOUT_S)`.
  `max_retries=0` is load-bearing: the SDK's own retry would silently double
  spend and is invisible to our deadline accounting.
- Requests are built field-by-field from the frozen request object with `omit`
  semantics — a field the caller did not set is simply absent from the body,
  so `input_fidelity` is never sent and the documented "omit for gpt-image-2"
  rule holds structurally rather than by convention.
- Calls go through `client.images.with_raw_response.<op>(...)` so the
  `x-request-id` response header is captured on success as well as on failure;
  `.parse()` then yields the typed `ImagesResponse`.
- Deadline: one `time.monotonic()` budget of 180 s covers validation-to-return.
  Each attempt's timeout is `min(API_ATTEMPT_TIMEOUT_S, remaining)`. When
  `remaining <= 0` the operation fails `deadline_exceeded` without a call.
- Retry policy, exactly as ADR 0015 fixes it:
  - retry at most once, and only after an *explicit HTTP response* whose status
    is in `429, 500, 502, 503, 504`;
  - never retry `APITimeoutError` or `APIConnectionError` — a request that may
    have completed server-side must not be re-billed;
  - never retry a `4xx` other than `429`, and never a moderation block;
  - back off `RETRY_BASE_DELAY_S + uniform(0, RETRY_MAX_JITTER_S)`, honouring
    `Retry-After` when the response supplies a sane one, and only when
    `remaining - delay >= RETRY_MIN_REMAINING_S`;
  - `sleep`, `monotonic`, and `random` are injected, so retry/deadline tests are
    deterministic and instant.
- Exception mapping is total and closed:

  | Raised | Code |
  | --- | --- |
  | `BadRequestError` with a moderation/content-policy marker | `moderation_blocked` |
  | other `BadRequestError` / `UnprocessableEntityError` | `user_error` |
  | `AuthenticationError` (401) | `authentication_error` |
  | `PermissionDeniedError` (403) | `access_denied` (organization verification/billing) |
  | `RateLimitError` (429) after retry budget | `rate_limited` |
  | `InternalServerError` / other 5xx | `service_error` |
  | `APITimeoutError` | `api_timeout` |
  | `APIConnectionError` | `connection_error` |
  | anything else | `internal_error` (type name only) |

  Each carries `request_id` when the response provided one, and a coarse
  provider message only when it is short and already safe.

### `server.py` — thin protocol edge

`FastMCP("gpt-image-2")`, stderr-only logging via
`logging.basicConfig(stream=sys.stderr, ...)` mirroring `mnemo/mnemo/server.py`,
and a module-level comment restating that `print()` is forbidden because stdout
is the JSON-RPC channel.

Two tools, both annotated `readOnlyHint=False`, `destructiveHint=False`
(nothing is ever overwritten), `idempotentHint=False` (each call is a fresh paid
generation), `openWorldHint=True` (external service):

```
generate_image(prompt, size="1024x1024", quality="high", output_format="png",
               n=1, output_compression=None, background="auto",
               moderation="auto", output_dir=None, basename=None)

edit_image(prompt, image_paths[], mask_path=None, size="1024x1024",
           quality="high", output_format="png", n=1,
           output_compression=None, background="auto",
           output_dir=None, basename=None)
```

No `model`, `api_key`, `headers`, `endpoint`, `url`, `file_id`, `overwrite`, or
`input_fidelity` parameter exists on either tool — the absence is the
enforcement, and a test asserts the exact argument sets.

Return value is a `list` exploiting the verified `_convert_to_content`
flattening: `[Image(...)]` when a preview is allowed, followed by the metadata
mapping, which FastMCP JSON-serializes. Metadata shape:

```json
{
  "operation": "generate",
  "model": "gpt-image-2",
  "status": "ok",
  "images": [{"index": 0, "path": "<absolute>", "format": "png",
              "mime_type": "image/png", "bytes": 1234567,
              "width": 1024, "height": 1024}],
  "failed_images": [],
  "request_id": "req_...",
  "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
  "revised_prompt": null,
  "requested": {"size": "1024x1024", "quality": "high",
                "output_format": "png", "n": 1, "background": "auto"},
  "attempts": 1,
  "duration_ms": 41230,
  "preview": {"included": true, "reason": null}
}
```

`preview.reason` is one of `null`, `"too_large"`, `"multiple_images"` — the
agent always learns *why* it did not get pixels inline, and always gets every
path. `revised_prompt` and `usage` are emitted only when the provider supplied
them; nothing is invented.

Failures raise `ToolError(json.dumps(payload))` so the host marks the result
`isError` **and** the agent receives the same closed, redacted payload shape.
Prompts, input paths beyond the offending one, image bytes, and base64 never
appear.

### `run_gpt_image_2_server.py`

The mnemo entrypoint pattern: resolve the repository root from `__file__`,
insert it on `sys.path`, import `gpt_image_2.server.main`, run. This is what
makes every registration CWD-independent while still letting the tool default
its output to the *caller's* working directory.

## Data flow

```
tool call
  -> validate_*  (pure; no credential, no network, no filesystem writes)
  -> inspect edit inputs / mask       [edit only, read-only filesystem]
  -> resolve_api_key                  (first credential touch)
  -> build_client + attempt loop      (<=2 attempts, 180 s budget)
  -> decode + validate every image    (in memory)
  -> publish_atomic each image        (temp + fsync + link, no overwrite)
  -> assemble metadata + bounded preview
  -> return [Image?] + metadata
```

Every arrow before `resolve_api_key` can fail without a credential read or a
paid request. That single property is what IMG-AC-004 and IMG-AC-005 measure.

## Testing strategy

`tests/gpt_image_2/`, pytest, zero network by default.

| File | Covers |
| --- | --- |
| `conftest.py` | fake OpenAI client/response builders, PNG/JPEG/WebP fixture factories, temp-dir helpers, a canary secret fixture |
| `test_credentials.py` | process wins; Windows-store fallback; blank treated as absent; missing raises; `Secret` never renders its value through `repr`/`str`/`format`/f-string |
| `test_validation.py` | table-driven valid + invalid matrix across prompt, size, quality, count, format/compression, background, moderation, output_dir, basename — each invalid case asserts the fake client saw **zero** calls and the credential resolver was **never** invoked |
| `test_images.py` | inspection rejects missing/dir/oversize/foreign-format/corrupt; mask dimension/format/opaque-alpha rules; basename sanitization and containment; decode/format-mismatch; collision suffixes; atomic publish; no overwrite of a pre-existing file (hash compared before/after); temp cleanup after induced failure |
| `test_api.py` | exact request bodies for generate and multi-reference masked edit (`model=gpt-image-2`, `input_fidelity` absent); `max_retries=0`; one retry on 429/503; **no** retry on timeout/connection/400; deadline exhaustion; `Retry-After` honoured; request-id capture on success and failure; the full exception-to-code map |
| `test_server.py` | exact tool names and argument sets; forbidden parameters absent; annotations; metadata shape; preview included under threshold, omitted with `too_large` / `multiple_images`; `ToolError` payload is the closed shape |
| `test_redaction.py` | a canary secret injected into env, into a simulated provider error body, and into an unexpected exception never appears in any log record, result, or error payload |
| `mcp_smoke.py` | real stdio server over `mcp.client.stdio`: `initialize`, `tools/list` returns exactly the two tools, one fake-backed valid call, one invalid call; asserts stdout stayed valid JSON-RPC |
| `live_smoke.py` | opt-in, never collected by pytest; one `quality=low`, `1024x1024`, `n=1` generation |

The stdio smoke needs a fake backend inside a *separate process*, and the
design deliberately refuses to ship an env-var fake switch in production code —
a shipped bypass is exactly the kind of thing that later generates fake images
against a real user's expectation. Instead the smoke spawns
`python -c "import fake_backend; from gpt_image_2.server import main; main()"`
with `tests/gpt_image_2` on `PYTHONPATH`; `fake_backend.py` is a test-only module
that monkeypatches `gpt_image_2.api.build_client` before `main()` runs. The
production package therefore contains no test seam at all.

Gates, in order: `pytest tests/gpt_image_2`, `python -m compileall`,
`python mcp_smoke.py`, `quick_validate.py skills/gpt-image-2`, JSON/TOML parse
of all six registrations, secret scan of changed files, `git diff --check`.
Only then the single live generation, then visual inspection.

## Host registration design

Repository adapters — additive, existing `mnemo` entry untouched:

- `.mcp.json` -> `mcpServers["gpt-image-2"]`, `type: "stdio"`, the same absolute
  Python interpreter already used for mnemo, args
  `[<canonical>/run_gpt_image_2_server.py]`. **No `env` block**: Claude Code
  passes its own environment through, so `OPENAI_API_KEY` is inherited without
  ever being named with a value.
- `.codex/config.toml` -> `[mcp_servers.gpt-image-2]` with
  `env_vars = ["OPENAI_API_KEY"]`, the forwarding idiom already proven by the
  existing `byond-rag` entry, plus `startup_timeout_sec` and `tool_timeout_sec`
  sized for the 180 s deadline.
- `.vscode/mcp.json` -> `servers["gpt-image-2"]`, `type: "stdio"`.

User registries receive the equivalent thin entries and target the **canonical**
checkout `C:/Users/josee/source/coding-cli`, never this worktree. Each edit
preserves every existing server, verified by a before/after server-name diff.

Correction to the Phase 3a record: the VS Code User `mcp.json` was recorded as
JSONC. It is not — it is plain JSON. The earlier `json.load` failure was an
artifact of a naive comment-stripping regex that mangled the `//` inside the
`https://` URLs it contains. It is still edited textually, but for a different
and better reason: `~/.claude.json` is being actively written by the running
Claude Code process, so hand-rewriting it would race the host. Claude's entry is
therefore added with the official `claude mcp add --scope user` CLI, and the
other two are precise textual insertions that leave surrounding formatting
untouched.

Honest activation boundary, per IMG-REQ-009: user registrations pointing at the
canonical checkout are **pending activation** until this branch is merged there
and each host reloads MCP. The evidence will say exactly that rather than
claiming the tool works in unrelated sessions.

Host tool timeouts: Codex accepts a documented per-server `tool_timeout_sec`.
Claude Code's MCP tool timeout is a client-side setting (`MCP_TOOL_TIMEOUT` in
Claude's own environment), *not* a `.mcp.json` field — putting it in the
server's `env` block would configure the child, not the client, so the design
documents it in the README instead of pretending the registration sets it.
VS Code exposes no documented timeout field, so it gets a real runtime gate
instead of a config claim.

## Requirements traceability

| Requirement | Design owner |
| --- | --- |
| IMG-REQ-001 | `skills/gpt-image-2/SKILL.md` + `agents/openai.yaml` |
| IMG-REQ-002 | `server.py` tool definitions; `constants.MODEL` |
| IMG-REQ-003 | `constants.py` + `models.validate_*` |
| IMG-REQ-004 | `images.inspect_local_image` / `validate_mask`; `models.validate_edit` |
| IMG-REQ-005 | `credentials.py`; `errors.redact`; registrations without values |
| IMG-REQ-006 | `images.sanitize_basename` / `publish_atomic`; `models` output-dir rules |
| IMG-REQ-007 | `server.py` metadata + bounded preview policy |
| IMG-REQ-008 | `api.py` retry/deadline/mapping; `errors.py` taxonomy |
| IMG-REQ-009 | six registrations + pending-activation reporting |
| IMG-REQ-010 | `tests/gpt_image_2/*` incl. `mcp_smoke.py` |
| IMG-REQ-011 | `tests/gpt_image_2/live_smoke.py` + visual inspection evidence |
| IMG-REQ-012 | README, PRD, ADR 0015, CHANGELOG, evidence index |

## Complexity Tracking

| Deviation | Reason | Mitigation |
| --- | --- | --- |
| Seven modules where `structure.md` sketched six (`constants.py` split out) | Constitution 2 and 3 both require constants to have exactly one owner; leaving them in `models.py` would make `api.py` and `server.py` import a validation module purely for numbers, creating a cycle risk | `constants.py` has no local imports and no logic; it is data only |
| `tests/gpt_image_2/fake_backend.py` executes inside the smoke server process | A stdio contract test needs a fake in a *different* process, and the alternative is a production env-var bypass | The module lives only under `tests/`, is never imported by the package, and the smoke test asserts it patched the boundary before serving |
| Preview policy hard-limits to the **first** image even when several small images would fit under 5 MiB | Constitution 6 fixes "the first output at no more than 5 MiB decoded" | Every image's path and metadata is always returned; `preview.reason` reports `multiple_images` so the agent knows to open the files |
| `os.link` primary with an `O_EXCL` fallback rather than a single primitive | `os.replace` overwrites on POSIX; a bare `O_EXCL` create is not atomic with the content write | Both paths are create-exclusive; both are covered by the no-overwrite test, and the temp file is removed in a `finally` |

## Constitution compliance

| Principle | How this design satisfies it |
| --- | --- |
| 1 Secrets and content stay bounded | `Secret` wrapper, no credential tool argument, three-layer redaction, type-name-only internal errors, canary test |
| 2 Paid actions explicit and bounded | fixed `gpt-image-2`, `max_retries=0`, at most one explicit-response retry, no timeout retry, 180 s deadline, closed defaults |
| 3 Validate before network | full validation and edit-input inspection run before `resolve_api_key`; invalid-case tests assert zero credential reads and zero client calls |
| 4 Never overwrite; publish atomically | sanitized generic basename, numeric suffixes, decode-before-publish, temp+fsync+link-if-absent, `finally` cleanup, pre-existing-file hash test |
| 5 Canonical once, thin host adapters | one `skills/gpt-image-2/`, one `gpt_image_2/`, six registrations containing no source and no secret, canonical-path targets |
| 6 Protocol and binary results bounded | stderr-only logging, no `print`, one preview <= 5 MiB, paths always returned, stdio smoke parses JSON-RPC |
| 7 Mock first; report gates honestly | default suite is fake-backed and offline; live smoke is a separate opt-in script; evidence separates mocked / live / visual / source-registration / per-host activation |

## Open risks

1. `openai` 2.8.1 predates `gpt-image-2` in its type literals. Runtime is
   unaffected, but a future SDK could start validating `model` or `size`
   client-side. Mitigation: constants in one file, and a live smoke that would
   fail loudly rather than silently downgrade.
2. `n > 1` behaviour for `gpt-image-2` is not publicly documented. The local
   `1..10` cap may be looser than the service. Mitigation: a service rejection
   maps to `user_error` with the provider's own message, and the default is `1`.
3. User-scope registrations cannot be proven live from this worktree. Reported
   as pending activation, never as working.
