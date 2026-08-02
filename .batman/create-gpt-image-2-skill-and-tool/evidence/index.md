# Evidence: GPT Image 2 Skill And Tool

Recorded 2026-08-02. Gate categories are kept strictly separate, per constitution
principle 7 and IMG-REQ-012: passing one says nothing about the others.

## 1. Deterministic gates (no network, no spend)

| # | Gate | Command | Result |
| --- | --- | --- | --- |
| 1 | Unit + contract suite | `py -3.12 -m pytest tests/gpt_image_2 -q` | **737 passed**, 0 failed, **0 xfailed** |
| 2 | Compile | `py -3.12 -m compileall gpt_image_2 run_gpt_image_2_server.py tests/gpt_image_2` | pass |
| 3 | Stdio MCP smoke | `py -3.12 tests/gpt_image_2/mcp_smoke.py` | **PASS** (also run inside gate 1 via `test_contract_gates.py`) |
| 4 | Skill validation | `quick_validate.py skills/gpt-image-2` | `Skill is valid!`, 0 `[TODO` placeholders remaining |
| 5 | Registration parse | all six JSON/TOML files | all parse; `gpt-image-2` present in all six |
| 6 | Secret scan | 68 changed files | **CLEAN** — the real `OPENAI_API_KEY` value appears in none; no key-shaped literal |
| 7 | Whitespace | `git diff --check` | clean |

Scale: 2,492 lines of package + launcher, 8,091 lines of test. There are no
`xfail` markers anywhere in the suite — every defect found was fixed rather than
parked.

The suite is offline by construction: `tests/gpt_image_2/conftest.py` installs an
autouse fixture that raises if anything constructs a real `openai.AsyncOpenAI`.
A test cannot spend money even by mistake.

Stdio smoke detail:

```
INITIALIZE ok
TOOLS: ['edit_image', 'generate_image']
SCHEMA ok: no credential/model/url/overwrite argument
GENERATE ok: image.png PNG (64, 64) 184B
REJECT ok: unsupported_option
NO-SPILL ok: ['image.png']
MCP SMOKE: PASS
```

The exchange completing at all is itself the stdout-cleanliness proof: any stray
`print()` would have corrupted the JSON-RPC stream and failed the session.

## 2. Live API gate (one billed request)

Exactly one paid call was made, after gates 1-7 were green, as authorised by
IMG-REQ-011.

```
result:            PASS
model:             gpt-image-2
operation:         generate
requested:         quality=low, size=1024x1024, n=1, output_format=png
request_id:        req_94564c8d7c8b471ca4aa5ea687c8190e
attempts:          1
usage:             input_tokens=30, output_tokens=196, total_tokens=226
elapsed:           16.58 s
output:            evidence/live-smoke.png
output_bytes:      953,531
output_dimensions: 1024x1024
```

This proves the real integration: the model string `gpt-image-2` is accepted by
the live service despite not appearing in `openai` 2.8.1's `ImageModel` literal,
the base64 response decodes, and the file publishes.

**Timing disclosure.** This call was made after gates 1-7 went green, but
*before* the second (adversarial) review round landed its fixes. It was not
re-run afterwards, because IMG-REQ-011 authorises exactly one live generation
and re-spending would exceed that authorisation. What makes the evidence still
load-bearing: `api.build_generate_kwargs` — the function that determines the
entire request the service sees — is byte-identical to the version that made
this call. Every later change was on the local side of the boundary (logging
scope, output-path validation, decode limits, publish guarding, redaction of a
response field), and each is covered by the deterministic suite. A reader who
wants a post-fix live confirmation should run
`tests/gpt_image_2/live_smoke.py --i-understand-this-costs-money` and treat that
as a new, separately-authorised gate.

## 3. Visual gate (separate from the above)

Prompt: *"A single bright red ceramic coffee mug centered on a plain white studio
background, soft even lighting, photographed from slightly above."*

`evidence/live-smoke.png` was opened and inspected. It shows one bright red
glossy ceramic mug, centred, on a plain white background, with soft even
lighting and a slightly elevated camera angle, handle to the right. Every
element of the prompt is present and nothing extraneous was added.

**Verdict: PASS.** HTTP 200 alone did not decide this; the file was viewed.

## 4. Source registration gate (NOT activation)

Six registrations were added, each verified by a before/after server-name diff:

| File | Before | After | Lost |
| --- | --- | --- | --- |
| `.mcp.json` | mnemo | mnemo, gpt-image-2 | none |
| `.vscode/mcp.json` | mnemo | mnemo, gpt-image-2 | none |
| `.codex/config.toml` | mnemo | mnemo, gpt-image-2 | none |
| `~/.claude.json` | byond-rag, elevenlabs, godot-mcp-pro, mnemo | + gpt-image-2 | **none** |
| `%APPDATA%/Code/User/mcp.json` | Roblox_Studio, elevenlabs, github/github-mcp-server, mnemo, v0 | + gpt-image-2 | **none** |
| `~/.codex/config.toml` | byond-rag, elevenlabs, godot-mcp-pro, mnemo, openaiDeveloperDocs | + gpt-image-2 | **none** |

Every `gpt-image-2` entry was checked to contain no credential value and to
target the canonical checkout `C:/Users/josee/source/coding-cli`, never this
worktree. Backups were taken at `*.pre-gpt-image-2.bak` before any user-scope
edit.

Claude's user entry was added with the official `claude mcp add --scope user`
CLI rather than by hand, because `~/.claude.json` is actively written by the
running Claude Code process and a hand-rewrite would race the host.

## 5. Per-host activation gate — NOT RUN

This is the honest boundary IMG-REQ-009 demands.

The user-scope registrations point at `C:/Users/josee/source/coding-cli`, which
does **not yet contain this work** — it lives in the
`implement-everything-pending-on-create-gpt-image` worktree. Therefore:

- **Claude Code**: registered, **pending activation**. Requires merge/sync into
  the canonical checkout, then an MCP reload.
- **Codex**: registered, **pending activation**. Same precondition.
- **VS Code / Copilot**: registered, **pending activation**. Same precondition.

No claim is made that the tools are callable in any unrelated session today.
The repository-scoped `.mcp.json` does resolve inside this worktree, but source
presence is still not activation — a host reload is required either way.

Also unverified, and deliberately so:

- **VS Code runtime timeout gate.** VS Code exposes no documented per-server
  timeout field, so the design called for a real 180-second runtime check
  instead of a config claim. That check has not been run.
- **Live edit path.** `edit_image` is covered by mocked tests only. No paid edit
  was made, because IMG-REQ-011 leaves live edit optional pending a reviewed
  fixture. Mocked edit coverage is not evidence of live edit behaviour.
- **`n > 1` against the live service.** The `1..10` cap is a local policy bound;
  the service's real range is not publicly documented.
- **Organization/billing limits** beyond the single successful call.

## 6. Defects found and fixed during this task

The suite was written adversarially and found six real defects in the package,
all fixed and now covered by non-xfail regressions:

1. **`images.sanitize_basename`** compared the raw stem against the reserved
   Windows device names, so `CON .png` passed — Windows strips the trailing
   space and resolves it to the `CON` device. The stem is now stripped of spaces
   and dots first.
2. **`errors._safe_detail`** dropped the supplied secret, so a credential that
   matched none of the scrub patterns survived inside `details` and reached
   `to_payload()`. The secret is now threaded through.
3. **`server._fail`** used `log.exception()`, writing the raw traceback —
   including `str(exc)` — to stderr unscrubbed, against IMG-REQ-005. It now
   formats the traceback, redacts it, and logs the scrubbed text, keeping the
   detail without the secret.
4. **`api._provider_message`** relayed the SDK's composite `exc.message`, which
   is `"Error code: N - <decoded body>"` — pushing the whole response body
   through MCP, against constitution principle 1. It now reads only the
   structured `body["message"]` field.
5. **`images.resolve_output_dir` / `sanitize_basename`** called `.strip()`
   without a type guard, so a `Path` or `int` escaped as a raw `AttributeError`
   outside the closed taxonomy. Both now reject non-strings as
   `invalid_request`.
6. **`server._fail`'s documented contract** claimed the raised `ToolError`
   message is pure JSON an agent can parse directly. It is not:
   `mcp.server.fastmcp.tools.base.Tool.run` catches every exception and
   re-raises `ToolError(f"Error executing tool {name}: {e}")`. The prefix is
   FastMCP's and cannot be removed without bypassing the framework, so the
   docstring, the ADR, and the test now pin the *real* delivered shape — the
   payload is the JSON object starting at the first `{`.

Defect 6 is worth flagging to any future maintainer: it was originally parked as
an `xfail`, which would have let the claim ship unchallenged. It is now a
passing test that pins observed behaviour, so a FastMCP change that breaks
payload extraction fails here instead of silently reaching agents.

A second, adversarial review round (three independent reviewers with distinct
lenses: coverage, false-confidence, security/spend) found seven more, all fixed:

7. **Root-logger scope — the most serious.** `logging.basicConfig(level=...)`
   sets the level on the **root** logger, so `GPT_IMAGE_2_LOG_LEVEL=DEBUG`
   also enabled DEBUG for `openai`, whose `_base_client` logs full request
   options — the user's prompt, and for an edit the raw reference-image and mask
   bytes — to stderr. That is precisely what constitution principle 1 forbids.
   The level now applies to the `gpt_image_2` logger only, `propagate` is off so
   records cannot climb into a host handler that might be writing to stdout, and
   `openai`/`httpx`/`httpcore` are pinned at `WARNING` regardless of the setting.
   Verified: with `GPT_IMAGE_2_LOG_LEVEL=DEBUG`, `openai._base_client` and
   `httpx` both report `isEnabledFor(DEBUG) == False`.
8. **Startup crash on a lowercase log level.** `level="info"` raised
   `ValueError: Unknown level: 'info'` during import, killing the MCP server at
   startup. The value is normalised and an unknown one falls back to `WARNING`.
9. **`revised_prompt` relayed unscrubbed.** The only provider-controlled string
   that bypassed `errors.redact` — unbounded and unfiltered into the MCP
   channel. Now redacted and length-bounded like every other provider string.
10. **`output_dir` naming an existing file spent money first.** Only
    type/blank/absoluteness were checked, so the credential was read and a paid
    call was made before the write failed — a direct violation of constitution
    principle 3. Validation now walks to the nearest existing ancestor and
    rejects the path before any spend.
11. **Decompression bomb escaped the taxonomy.** A 68-byte PNG declaring
    60000x60000 raised PIL's `DecompressionBombError`, which derives from plain
    `Exception`, surfacing as `internal_error` with a traceback — after forcing
    a large allocation during pre-credential validation. Header dimensions are
    now checked against `MAX_DECODE_PIXELS` before `load()`, and PIL failures
    are caught broadly.
12. **Partial publish orphaned files.** A publish failure on image 2 of 3
    aborted the call: the file already written was orphaned and the error
    payload named none of the paths the caller had paid for, against
    IMG-REQ-006 and IMG-REQ-007. Each publish is now guarded, partial success is
    reported, and the call fails only when nothing landed.
13. **UNC paths caused caller-controlled network I/O.** `//server/share/x.png`
    was treated as a local path, and `Path.resolve()` made Windows perform a
    real SMB/DNS lookup — observed as a 22-second stall inside a paid
    operation's deadline. URLs and UNC paths are now refused before the
    filesystem is touched.

14. **The bomb fix was applied to only half the boundary.** Fix 11 broadened the
    catch in `inspect_local_image` (caller-supplied files) but not in
    `decode_image_payload` (provider responses), which still narrowed to
    `(UnidentifiedImageError, OSError, ValueError)`. PIL runs its own bomb check
    inside `Image.open()`, *before* `_describe` can apply `MAX_DECODE_PIXELS`,
    and `DecompressionBombError` derives from plain `Exception` — so a payload
    declaring 20000x20000 escaped the closed taxonomy, sailed past
    `_publish_all`'s `except ImageToolError`, and discarded the valid,
    already-paid-for images from the same response. Exactly the orphaning class
    defect 12 was meant to close, re-entering through the other door. Both sides
    of the boundary now catch broadly. Verified: a two-payload response
    (one valid, one bomb) now publishes the good image and reports index 1 as an
    indexed `output_error`.

Two further improvements came out of the same round: a short provider response
(fewer images than `n`) used to read as a clean success and now carries
`provider_returned` and `complete`; and `api.client_factory` was bound as a
keyword default, freezing `build_client` into `__kwdefaults__` so that
monkeypatching it silently did nothing — it is now resolved at call time, which
made the offline tripwire real rather than inert.

The reviewers also caught two classes of *test* that would have passed against
broken code: the `_link_or_create` no-clobber primitive (a check-then-write
rewrite passed every single-threaded test, so a real 16-thread contention test
now pins it) and ~25 vacuous `call_count == 0` assertions on a fixture that was
never installed on the path under test.

## 7. Not done, by scope

No commit, push, merge, or broad staging was performed. Marketplace/plugin
packaging, remote MCP deployment, Responses API conversations, URL/file-ID
inputs, and transparent-background output all remain out of scope per the
approved requirements and ADR 0015.
