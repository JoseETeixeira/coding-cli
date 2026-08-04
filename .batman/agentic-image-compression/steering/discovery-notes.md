# Recovered discovery notes

## package

## 1. `storage.py` — what it actually provides (and what it does *not*)

`C:\Users\josee\source\coding-cli\context_compaction\storage.py` (403 lines) is **not** a content-addressed blob store. It is a *single-slot* JSON state file plus a bounded, deduped event ring, living in a private per-repo directory.

Public surface:
- `resolve_state_directory(repository_root: str|PathLike, *, fallback_base: str|PathLike|None = None) -> Path` — lines 61-107. Primary path comes from `git -C <root> rev-parse --path-format=absolute --git-path coding-cli-context-pilot`, i.e. **inside `.git/`**, so writes never dirty `git status` (asserted at `tests/context_compaction/test_storage.py:52-61`). Fallback when not a git repo: `%LOCALAPPDATA%\coding-cli\context-compaction` on Windows, else `$XDG_STATE_HOME` / `~/.local/state/coding-cli/context-compaction`, with the leaf directory name = `sha256(os.path.normcase(str(root)).replace("\\","/"))` (lines 104-107). **This is the single most reusable piece for a "segment optical cache" root.**
- `class StateStore(repository_root, *, fallback_base=None, retention=200, max_bytes=1_048_576)` — lines 110-402. Methods: `write_current(Mapping)` (135), `read_current() -> dict|None` (142), `append_event(payload, *, dedupe_key) -> bool` (153), `read_events() -> list[dict]` (190), `purge()` (209).
- `StorageError(RuntimeError)` carrying `.reason: DegradedReason` — lines 55-58. `OWNER_ID = "coding-cli-context-compaction-pilot"` (20), `MAX_STATE_BYTES = 1_048_576` (21).

Reusable internals (currently private, duplicated elsewhere — worth extracting rather than re-implementing):
- `StateStore._atomic_write(target, encoded: bytes)` — lines 333-354: NamedTemporaryFile in the same dir, `chmod 0o600`, `flush` + `os.fsync`, `os.replace`, cleanup on failure. Near-identical twin at `context_compaction/activation.py:1223-1244` (text variant).
- `StateStore._process_lock(*, create=True)` — lines 359-402: cross-process one-byte OS file lock, `msvcrt.locking` on Windows / `fcntl.flock` elsewhere; lock file is a sibling `.{dirname}.context-pilot.lock` (357). Combined with an in-process `threading.RLock` registry keyed by normcased dir (51-52, 131-133).
- Ownership marker protocol: `_ensure_owned` (234-249) / `_assert_owner` (251-262) writes `owner.json = {"owner": OWNER_ID, "schema_version": 1}` and refuses to adopt a non-empty foreign directory (`DegradedReason.OWNED_FILE_DRIFT`).

**Hard blockers against backing an image/segment cache with `StateStore` itself:**
- `_encode` (264-278) requires a `Mapping` with `schema_version == SCHEMA_VERSION` and JSON-serializable content only; hard 1 MiB cap.
- `_validate_value` (297-331) rejects the key `"binary"` outright (`_FORBIDDEN_KEYS`, lines 22-40), rejects any key containing `credential`/`password`/`secret`, rejects strings containing NUL, rejects strings matching the secret regex, rejects absolute paths under any key containing `"path"`, and caps lists at 10,000 elements. So base64 PNG tiles in `current.json` are both size-infeasible and semantically forbidden.
- `purge()` (209-232) whitelists exactly `{"owner.json","current.json","events.json"}` (line 214) and raises `OWNED_FILE_DRIFT` on anything else in the directory. **Dropping cache blobs into the pilot state dir will break purge.** A segment cache must use a *sibling* directory (e.g. a different `--git-path` leaf) or `resolve_state_directory` must be parameterized — the leaf name `coding-cli-context-pilot` is hardcoded at line 75.

Verdict: reuse `resolve_state_directory` (or a parameterized clone), the atomic-write helper, and the process lock. Do **not** reuse `StateStore` as the blob container.

## 2. `benchmark.py` — what it measures, and its fit for a compression/fidelity benchmark

`C:\Users\josee\source\coding-cli\context_compaction\benchmark.py` (929 lines). Four measurement axes plus a source-truth layer:

- Fidelity/preservation: `score_answers(manifest: BenchmarkManifest, answers: Mapping[str,str], validation: SourceValidation) -> PreservationScore` — lines 507-560. Per probe: AND-of-OR concept coverage (`required_concepts`), contradiction-term hits, "false exact code claims" (`_EXACT_CODE = r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b"`, line 42) minus `allowed_exact_codes`, plus a P14-only dirty-path check `_dirty_path_fidelity(answer)` (822-835). Matching is substring over `_normalize` = NFKC + casefold + whitespace collapse (879-880). Output `PreservationScore` (117-140): `critical_accuracy`, `overall_accuracy`, `false_exact_code_claims`, `stale_contradictions`, `dirty_path_fidelity`, `approval_retained`, `action_replay_safe`, passed/failed ids.
- Savings: `measure_savings(*, pre_total_tokens, post_total_tokens, fixed_prefix_tokens, reentry_tokens, measurement_source, pre_body_chars, post_body_chars, fixed_prefix_chars, reentry_chars) -> SavingsMeasurement` — 563-609. Three qualifications: `confirmed` (all four token values + `measurement_source` starting with `host_`), `qualified` (chars/4 proxy, source `qualified_local_character_proxy`), `unmeasured`. Percent computed in `_savings` (804-815).
- Latency: `measure_assembly(assembler: Callable[[], object], *, samples: int = 30) -> AssemblyMeasurement` (612-630; 3 warmups, nearest-rank p50/p95/max) and `measure_representative_states(assemblers: Mapping[str, Callable], *, samples=30)` (633-643, requires exactly the 8 `FaultCase` keys).
- Anti-thrash: `assess_thrashing(compaction_turns, *, continuation_turns=10, declared_oversized_turns=()) -> ThrashAssessment` (646-669).
- Matrix + driver: `build_scenario_matrix(configurations: Sequence[HostModelConfig]) -> tuple[ScenarioCase, ...]` (672-700) = hosts × 4 `ScenarioMode` × 8 `FaultCase` (64 cases for 2 hosts). `BenchmarkScenarioDriver(manifest, validation).run(case, executor: Callable[[ScenarioCase], ScenarioObservation]) -> ScenarioResult` (293-333). **The `executor` callback is the reusable seam** — a compression benchmark supplies its own executor returning a `ScenarioObservation` (246-262).
- Source truth: `load_manifest(path)` (336-369), `validate_manifest_source(manifest, repository) -> SourceValidation` (372-432) pins every authority via `git hash-object` blob OID + line span + anchor substrings + negative `git grep` match counts; `isolated_worktree(source_repository, commit=FROZEN_EDUCODE_COMMIT)` context manager (435-479) runs inside a disposable detached worktree and asserts the source checkout is unchanged afterwards.
- Artifact hygiene: `_validate_content_free_artifact` (838-861) rejects keys `answer/answers/expected_answer/question/source_body/summary/tool_output/diff/path/repository_root` anywhere in the result, plus absolute-path-looking strings; `MAX_BENCHMARK_ARTIFACT_BYTES = 32_768` (26).

**Can the harness score a compression/fidelity benchmark? The fidelity half, yes** — scoring is text-answer-based and codec-agnostic, so answers produced from an image-compressed context can be fed straight in. What must be parameterized or forked:
- `FROZEN_EDUCODE_COMMIT` (line 23) — `load_manifest` refuses any other `frozen_commit` (350-351).
- `_EXPECTED_PROBE_IDS` = exactly `P01..P14` and `_EXPECTED_CRITICAL` = a hardcoded 10-item set (29-41); `load_manifest` rejects any other id list or order (357-361), and `score_answers` demands answers covering exactly P01-P14 (518-519).
- P14 is hardwired to `CONTEXT.md` + `context-pilot-dirty/queued-change.ts` (822-835) and `prepare_p14_dirty_state` (481-504) hardcodes task slug `agentic-development-workbench`.
- No bytes/pixels axis exists — savings is tokens or chars/4 only. An optical codec needs a new measurement dataclass or must map onto `fixed_prefix_tokens` / `eligible_*_tokens`.
- `_validate_content_free_artifact` forbids the key `"path"` (and `"paths"` is fine but `"path"` is not) — a per-segment report cannot use `path` as a key.

**Shape of `benchmarks/context_compaction/educode-probes.v1.json`** (19.7 KB):
```
{"schema_version": 1,
 "workload": {"name": "educode-agentic-development-workbench",
              "frozen_commit": "0db30624dd32d814b937aa88b5ec84e18d4b130d"},
 "probes": [ 14 items, ids P01..P14 ]}
```
Each probe has **exactly** these keys (set equality enforced by `_require_keys`, 895-897): `id`, `critical`, `question`, `expected_answer`, `required_concepts` (list of non-empty alternative-lists), `allowed_exact_codes`, `contradiction_terms`, `authorities`, `negative_assertion`. Each authority has exactly `{path, blob_oid, start_line, end_line, anchors}`; `negative_assertion` (nullable) has exactly `{pattern, paths, expected_match_count}`. 10 probes are critical; P13 is the only negative-assertion probe (0 authorities); authority counts range 1-5. Adding a field to any object breaks loading.

## 3. `cli.py` — subcommand registration

`C:\Users\josee\source\coding-cli\context_compaction\cli.py` (431 lines).
- `build_parser() -> argparse.ArgumentParser` — lines 43-81. `parser = argparse.ArgumentParser(prog="context-pilot")`; `subparsers = parser.add_subparsers(dest="command", required=True)`. Registered: `plan`/`enable`/`run` (created in a `for name in (...)` loop sharing `_add_activation_paths`, 47-56), `status` (58-61), `validate` (63-66), `disable` (68-70), `purge-state` (72-74), `hook` (76-80).
- `main(argv: Sequence[str]|None = None) -> int` — 84-162. Dispatch is a plain `if arguments.command in {...}` / `elif` chain, all wrapped in a closed exception funnel (137-161) that prints `{"status":"error","code": <DegradedReason>}` and returns exit 2; success returns 0, policy-fail returns 2.
- Shared helpers: `_add_activation_paths(parser)` (302-307) adds `--source-root/--codex-home/--app-data/--host-executable/--python-executable`; `_print_json(value)` (423-427) is the only output path (`ensure_ascii=False, sort_keys=True, separators=(",",":")`).
- **To add a subcommand:** add a `sub = subparsers.add_parser("name"); sub.add_argument(...)` block in `build_parser`, then a branch in `main` returning an int and emitting via `_print_json`. There is no plugin registry, no `entry_points` (the repo has **no `pyproject.toml`/`setup.cfg`**).
- Precedent for a *separate* CLI module instead of growing `cli.py`: `context_compaction/gates.py:103-119` defines its own `build_parser()` with `prog="context-pilot-gates"` plus `main(argv)` and an `if __name__ == "__main__"` guard (196-197).
- Entry points in practice: `context_compaction/__main__.py` (`from .cli import main; raise SystemExit(main())`) and `context_compaction/hook_entry.py` (inserts the source root on `sys.path` first, for invocation from outside the checkout).

## 4. Test conventions in `tests/context_compaction/`

16 test modules, ~3,300 lines. No `conftest.py` in this directory (contrast: `tests/gpt_image_2/conftest.py` exists), no `pytest.ini`/`pyproject.toml` anywhere in the repo, so pytest must run from the repo root for `import context_compaction...` to resolve.
- One-line module docstring stating the contract under test; `from __future__ import annotations`; import public symbols directly from the module under test (never via `context_compaction/__init__`).
- Module-level `ROOT = Path(__file__).parents[2]` when repo assets are needed (`test_benchmark.py:34`, `test_gates.py:13`, `test_documentation.py:5`).
- Plain functions only — no test classes. Long behavioural names, e.g. `test_events_are_deduplicated_and_retained_newest_200`, `test_source_validated_scoring_is_content_free_and_detects_false_exact_claims`.
- Local underscore helpers at module top: `_git(repo, *args)`, `_repo(tmp_path)`, `_payload(...)`, `_task(...)`, `_educode()`.
- Real side effects rather than mocks: real `git init` repos under `tmp_path`, real `ThreadPoolExecutor`/`ProcessPoolExecutor` for concurrency (`test_storage.py:143-170`), real subprocess git calls.
- Failure assertions check the typed reason, not the message: `with pytest.raises(StorageError) as exc: ...; assert exc.value.reason is DegradedReason.STATE_OVERSIZED`.
- External-dependency gating: `os.environ.get("EDUCODE_BENCHMARK_REPO")` else `~/source/educode`, then `pytest.skip("frozen educode checkout is unavailable")` (`test_benchmark.py:39-44`, `test_gates.py:18-20`).
- Static fixtures are JSON files under `tests/context_compaction/fixtures/adapters/` (10 files: `claude_*`/`codex_*` hook payloads plus `malformed.json`).
- Privacy assertions are a first-class convention: serialize the artifact and assert forbidden content is absent — `assert "expected_answer" not in serialized`, `assert str(_educode()) not in artifact`, `assert len(artifact) <= 32_768`.
- `test_documentation.py:9-11` asserts the **exact** filename set of `docs/context-compaction/` = `{README.md, compatibility.md, troubleshooting.md, rollback.md}` and greps for required phrases — adding a doc file to that folder fails the suite.

## 5. Existing notions of segments / hashing / caching

- **Segments: none.** The only `segment` occurrences are PATH segments in `activation.py:385-388`. No content-segment, tile, or chunk abstraction exists (`repository.py:366` uses `chunk` only as a 64 KiB read buffer).
- **Hashing: pervasive, all SHA-256, all hex-lowercase.** `repository_fingerprint(root)` = sha256 of normcased root (`repository.py:102-105`); streaming `_hash_file` (`repository.py:363-368` and `activation.py:1282-1287`); `_sha256_text` / `_sha256_json` with canonical JSON (`activation.py:1290-1298`); tool-input fingerprints `_fingerprint_json` (`adapters.py:467-471`); compact-summary sha256 (`adapters.py:218`); plan hash over file target-fingerprints + content hashes (`activation.py:1247-1279`); manifest sha256 (`benchmark.py:368`); state-dir key (`storage.py:106`). Validators enforce the format: `models._require_sha256` / `_SHA256 = ^[0-9a-f]{64}$` (`models.py:11`, 514-516).
- **Cache-invalidation pattern already implemented (reusable design, not code):** `StatePointer{kind, stable_id, relative_path, anchor, captured_hash}` + `SourceRead{relative_path, current_hash, recovery_epoch}` (`models.py:312-361`) plus the revalidation loop in `LifecycleCore.validate` (`lifecycle.py:141-231`), which re-hashes each pointer via `RepositoryResolver.hash_relative_path` (`repository.py:143-147`) and downgrades to `SOURCE_CHANGED` / `ARTIFACT_MISSING` on mismatch. That is exactly the "hash-pinned entry, re-verify before trusting the cached render" contract a segment optical cache needs.
- **Caching: no implementation.** The only cache tokens are `RegistryFieldCategory.CACHE_STATE` (`models.py:83`) and its classifier at `claude_registry.py:306-307`, which merely categorize fields inside Claude's own `~/.claude.json`. There is no content-addressed blob store anywhere in the package.
- **Adjacent reusable accounting:** `budget.py` — `estimate_tokens(text)` (30-45, `ceil(ascii_run/4)` + 1 per non-ASCII char, deterministic, no tokenizer), `fits_budget`, `truncate_text` (binary search for the longest fitting Unicode prefix, 53-71), and `allocate_categories(categories, *, max_chars=8000, max_tokens=2000, separator="\n") -> BudgetResult` (115-169) with priority ordering and required-category truncation. `BudgetCategory.__post_init__` (83-92) rejects category names containing `secret/credential/token_value/raw_tool/tool_output/transcript/compact_summary/source_body/full_source/full_diff/binary` — note **`binary` is a forbidden category name**, so an image-payload category cannot be named that.

---

## hosts

## Answer to the CRITICAL question first

**Yes — an MCP tool in this setup can return an IMAGE content block, and `gpt_image_2/server.py` is a working precedent that is gated end-to-end over real stdio.**

The mechanism is three things together:

1. **Import the FastMCP `Image` helper** — `C:\Users\josee\source\coding-cli\gpt_image_2\server.py:29`
```python
from mcp.server.fastmcp.utilities.types import Image
```

2. **Declare the tool with `structured_output=False` and a bare `list` return annotation** — `gpt_image_2/server.py:282-306` (and the identical shape at `:356-382`):
```python
@mcp.tool(
    name="generate_image",
    description=(...),
    annotations=_ANNOTATIONS,
    structured_output=False,
)
async def generate_image(
    prompt: str,
    ...
) -> list:
```

3. **Return a list whose head is `Image(...)` blocks and whose tail is a plain metadata dict** — the preview builder at `gpt_image_2/server.py:176-192`:
```python
def _preview(kept: list[images.DecodedImage]) -> tuple[list[Image], dict[str, Any]]:
    """At most one inline image, at most 5 MiB decoded (constitution 6).
    ...
    """
    if not kept:  # pragma: no cover - _publish_all guarantees at least one
        return [], {"included": False, "reason": "no_images"}

    first = kept[0]
    if first.size_bytes > constants.MAX_INLINE_PREVIEW_BYTES:
        return [], {"included": False, "reason": "too_large"}

    blocks = [Image(data=first.data, format=first.format)]
    if len(kept) > constants.MAX_INLINE_PREVIEWS:
        return blocks, {"included": True, "reason": "first_of_n"}
    return blocks, {"included": True, "reason": None}
```
and the tool bodies at `gpt_image_2/server.py:334` / `:351` (generate) and `:410` / `:430` (edit):
```python
        blocks, preview = _preview(kept)
        ...
        return [*blocks, metadata]
```

### Why that works (verified against the installed SDK, `mcp` 1.26.0)

- `C:\Users\josee\AppData\Local\Programs\Python\Python312\Lib\site-packages\mcp\server\fastmcp\utilities\types.py:9-58` — `Image.__init__(path=None, data=None, format=None)`; `_get_mime_type()` returns `f"image/{format.lower()}"` when `format` is given, so `format="png"|"jpeg"|"webp"` maps to the right MIME; `to_image_content()` base64-encodes and returns `ImageContent(type="image", data=..., mimeType=...)`.
- `...\mcp\server\fastmcp\utilities\func_metadata.py:499-533` — `_convert_to_content` flattens lists recursively, converts any `Image` via `to_image_content()`, and JSON-serializes non-str leftovers (the metadata dict) into a `TextContent`. That list-flattening is exactly what `return [*blocks, metadata]` relies on, and it is why `gpt_image_2/requirements.txt:8` pins `mcp>=1.10.0`.
- `...\mcp\server\fastmcp\utilities\func_metadata.py` `FuncMetadata.convert_result` — when `output_schema is None` it returns the unstructured content list *only*. `structured_output=False` is what forces `output_schema=None`; without it FastMCP would try to build an output model from the `-> list` annotation and emit `structuredContent` alongside, which is not what this design wants.

So the wire result for a successful `generate_image` is `content = [ImageContent, TextContent(<metadata JSON>)]`.

### Precedent proven at the real protocol edge, not just in-process

`C:\Users\josee\source\coding-cli\tests\gpt_image_2\mcp_smoke.py:103-104` and `:228-231` drive the actual launcher over `mcp.client.stdio` and assert an image block arrives:
```python
def _image_blocks(result: Any) -> list[Any]:
    return [block for block in result.content if getattr(block, "type", None) == "image"]
...
            _require(
                len(_image_blocks(ok)) == constants.MAX_INLINE_PREVIEWS,
                "expected exactly one bounded inline preview block",
            )
```
And in-process at `tests/gpt_image_2/test_server.py:319-333`:
```python
    blocks = image_blocks(result)
    assert len(blocks) == 1
    assert result[0] is blocks[0]

    content = blocks[0].to_image_content()
    assert content.mimeType == constants.MIME_BY_FORMAT["png"]
    assert base64.b64decode(content.data) == base64.b64decode(payload)
```

### The one policy constraint on image blocks in this repo
`gpt_image_2/constants.py:205-207`:
```python
#: Constitution principle 6: at most one inline preview, at most 5 MiB decoded.
MAX_INLINE_PREVIEW_BYTES = 5 * 1024 * 1024
MAX_INLINE_PREVIEWS = 1
```
When the image exceeds the cap, `_preview` returns `[]` plus `{"included": False, "reason": "too_large"}` — the model gets the path, not the pixels, and is told why. `skills/gpt-image-2/SKILL.md:114-124` instructs the agent to open the file from disk in that case.

---

## How a new capability gets wired into BOTH hosts

### 1. MCP server registration — six files, one launcher

The repo registers each stdio server three times in-repo and three times at user scope. All six must name the **same** launcher filename.

Claude Code (repo scope) — `C:\Users\josee\source\coding-cli\.mcp.json:1-21`; the gpt-image-2 entry is `:13-19`:
```json
    "gpt-image-2": {
      "type": "stdio",
      "command": "C:/Users/josee/AppData/Local/Programs/Python/Python312/python.exe",
      "args": ["C:/Users/josee/source/coding-cli/run_gpt_image_2_server.py"],
      "timeout": 600000,
      "description": "..."
    }
```
Shape: `mcpServers.<name>` with `type: "stdio"`, absolute `command` (the Python 3.12 interpreter), `args` = one absolute `.py` launcher path, optional `env` map, optional per-server `timeout` in **milliseconds** (Claude Code v2.1.203+). Note the deliberate absence of an `env` block for the credential — Claude Code inherits the parent env.

Codex (repo scope) — `C:\Users\josee\source\coding-cli\.codex\config.toml:1-19`; gpt-image-2 is `:6-19`:
```toml
[mcp_servers.gpt-image-2]
command = "C:/Users/josee/AppData/Local/Programs/Python/Python312/python.exe"
args = ["C:/Users/josee/source/coding-cli/run_gpt_image_2_server.py"]
env_vars = ["OPENAI_API_KEY"]
startup_timeout_sec = 30
tool_timeout_sec = 600
```
Codex differences that matter: table key is `mcp_servers` (not `mcpServers`); it forwards secrets **by name** via `env_vars = [...]`, not by value; `startup_timeout_sec` defaults to 10 s (raised to 30 because `openai` + Pillow import slowly cold); `tool_timeout_sec` defaults to **60 s** and is load-bearing — without it Codex kills a normal generation.

VS Code / Copilot (third host) — `C:\Users\josee\source\coding-cli\.vscode\mcp.json:1-19`, key is `servers`, no timeout field exists.

User-scope equivalents (machine-specific, outside the repo, asserted-if-present by tests): `~/.claude.json` (`mcpServers`), `~/.codex/config.toml` (`mcp_servers`), `%APPDATA%/Code/User/mcp.json` (`servers`). Enumerated at `tests/gpt_image_2/test_contract_gates.py:590-603`.

There is **no** `.claude/settings.json` MCP wiring — that file is literally `{}` (`C:\Users\josee\source\coding-cli\.claude\settings.json:1`).

### 2. The launcher — one proven shape

`C:\Users\josee\source\coding-cli\run_gpt_image_2_server.py:1-22`. Sits at repo root, inserts `REPOSITORY_ROOT` into `sys.path`, imports `main` from the package's `server` module, calls it under `if __name__ == "__main__"`. It deliberately mirrors `C:\Users\josee\source\coding-cli\mnemo\run_server.py` ("one proven launcher shape for every stdio server in this repository"). The `sys.path` insert is load-bearing because the tool's default output dir is derived from the **caller's** cwd, not the server's.

### 3. Skill layer — how agents learn the tools exist

Skills live at `C:\Users\josee\source\coding-cli\skills\<name>\SKILL.md`. Format: YAML frontmatter with exactly `name` + a long trigger-rich `description`, then markdown body. See `skills\gpt-image-2\SKILL.md:1-4`:
```yaml
---
name: gpt-image-2
description: Generate or edit raster images with OpenAI gpt-image-2 through the local gpt-image-2 MCP server. Use when the user explicitly asks to create, generate, draw, render, revise, inpaint, restyle, or otherwise edit a photo, ... Do not use for SVG, vector art, charts, diagrams, CSS/HTML UI, or anything better produced as code.
---
```
The description carries both the "use when" and the "do NOT use for" clauses — that negative half is doing real routing work.

Skills reference tooling by **naming the MCP tools in prose** (`skills/gpt-image-2/SKILL.md:10-14, 45-48`), documenting every argument and default in a table (`:93-103`), and documenting the closed error-code vocabulary (`:131-141`). The "Setup" section (`:146-151`) points at `README.md` for registration/reload.

Optional Copilot-facing sidecar: `C:\Users\josee\source\coding-cli\skills\gpt-image-2\agents\openai.yaml` (4 lines, `interface.display_name` / `short_description` / `default_prompt`).

`C:\Users\josee\source\coding-cli\skills\generic-entry\SKILL.md:1-17` is the router skill — no tool references, just the eight-phase workflow, memory preflight, PRD/ADR policy, and customization-path resolution. A new capability skill does **not** need to register itself in `generic-entry`; discovery is by frontmatter description.

Skill discovery per host:
- Claude Code: `.claude-plugin/plugin.json:1-7` declares this repo as plugin `coding-cli-agent-assets`; top-level `skills/`, `agents/`, `prompts/`, `hooks/hooks.json` are the plugin's auto-discovered dirs.
- VS Code / Copilot: `.vscode/settings.json:1-8` maps `chat.agentSkillsLocations: {"./skills": true}` plus `./agents`, `./prompts`, `./instructions`.
- Codex: via `~/.codex/AGENTS.md` + the repo's `AGENTS.md:1-16`, which names skills by path (`skills/shared-memory/SKILL.md`, `skills/gamedev-workflow/SKILL.md`, …).

### 4. Hook wiring

Two locations, and only one is active:
- `C:\Users\josee\source\coding-cli\hooks\hooks.json:1-16` — the **plugin** hooks manifest. One `Stop` hook: `bash "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/auto-improvement-nudge.sh"`. `${CLAUDE_PLUGIN_ROOT}` is the plugin-root variable, so scripts are addressed relative to the plugin install.
- `C:\Users\josee\source\coding-cli\.claude\settings.json:1` — `{}`. Empty. No hooks, no permissions, no env. Nothing to merge with.
- `C:\Users\josee\source\coding-cli\.claude\hooks\` — four tracked scripts: `auto-improvement-nudge.sh` (1.3K), `batman-handoff-checkpoint.py` (8.6K), `batman-phase-checkpoint.py` (10.3K), `block-dangerous-git.sh` (826B). Only the first is referenced from `hooks/hooks.json`; the other three are present but not wired in this repo's manifest.

Hook script contract (`.claude/hooks/auto-improvement-nudge.sh`): reads the hook JSON payload from stdin, guards on `stop_hook_active is False`, and prints `{"decision":"block","reason":"..."}` on stdout. `set -euo pipefail`, exits 0 silently when it has nothing to say.

**Nothing about gpt-image-2 touches hooks.** A new MCP capability needs no hook changes.

### 5. Server module structure (the precedent to copy)

`C:\Users\josee\source\coding-cli\gpt_image_2\__init__.py:10-15` states the enforced layering:
```
constants, errors  ->  credentials, images  ->  models  ->  api  ->  server
```
"Only `server` imports `mcp`. Only `api` imports `openai`. Everything else is pure enough to test without stdio and without a network."

Files: `constants.py` (data only, every bound has one owner, split into "verified API rules" vs "local policy caps"), `errors.py` (closed code vocabulary at `:28-47`, `redact()` at `:102`, `ImageToolError` at `:153`, factory functions `:210-251`), `credentials.py` (`Secret` wrapper whose repr/str/format render `<Secret ***>`, `resolve_api_key` at `:97`), `images.py` (`inspect_local_image:154`, `validate_mask:237`, `sanitize_basename:279`, `resolve_output_dir:338`, `decode_image_payload:402`, `publish_atomic:484`), `models.py` (validation), `api.py` (`build_client:90` with `max_retries=0`, `Budget:45`, `ApiResult:77`, `call_generate:516`, `call_edit:536`), `server.py` (protocol edge only).

`server.py` structure in order:
- `_configure_logging()` at `:34-71` — attaches a stderr handler to the **package** logger only, sets `propagate=False`, and pins `openai`/`httpx`/`httpcore` at WARNING regardless of the operator's level. Never `basicConfig`. stdout is the JSON-RPC channel; `print()` is forbidden anywhere in the package (`:8-9`).
- `mcp = FastMCP(constants.SERVER_NAME)` at `:74`.
- `_PAID_NOTICE` at `:76-82` — a shared description fragment interpolated into both tool descriptions.
- `_ANNOTATIONS = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)` at `:84-89`, imported from `mcp.types` at `:30`.
- `_publish_all:97-173` → `_preview:176-192` → `_metadata:195-237` → `_fail:240-274`.
- Tools at `:282-353` and `:356-432`.
- `def main(): mcp.run()` at `:435-436`, plus a `__main__` guard.

Error contract: `_fail` at `:240-274` converts anything into a `ToolError` whose message is exactly one JSON object. The docstring at `:246-252` records the real-world wrinkle worth knowing before you build one:
```
`mcp.server.fastmcp.tools.base.Tool.run` catches every exception, including
this one, and re-raises `ToolError(f"Error executing tool {name}: {e}")`.
So over the wire the agent sees that prefix followed by our JSON, and
`json.loads` on the whole string fails — the payload is the JSON object
beginning at the first `{`.
```
(Confirmed present in the installed `mcp` 1.26.0 `Tool.run`.) Tests work around it by slicing from the first `{` — `mcp_smoke.py:107-124`.

Note the "absence is the enforcement" pattern (`server.py:11-16`): arguments are deliberately omitted from the schema and a test asserts the omission as a set intersection.

### 6. Test conventions (`tests/gpt_image_2/`)

No `pyproject.toml`, no `pytest.ini`, no root `conftest.py`, no `tests/__init__.py`. Pytest's default prepend import mode puts the test dir on `sys.path`, which is why tests do `from conftest import ...` (`test_server.py:34-41`). `tests/gpt_image_2/conftest.py:28-33` re-inserts the repo root into `sys.path`.

Files and their jobs:
- `conftest.py` (14.6K) — offline fixtures. Image factories `make_image_bytes/write_image/b64_image` at `:50-86` (real Pillow-encoded bytes, never mocks). `FakeOpenAI` scripted client `:182-213`. Real `openai` exception constructors `:237-273` so `isinstance` dispatch is exercised for real. `FakeClock`/`RecordingSleep` `:281-305` — no test ever sleeps. `PackageLogCapture` `:347-427` replaces `caplog` because `propagate=False` makes `caplog` see nothing and pass vacuously. **Autouse network guard** at `:429-443`:
```python
@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    ...
    monkeypatch.setattr(openai, "AsyncOpenAI", _explode)
```
- `test_server.py` (44.5K) — the MCP edge. `listed_tools` fixture at `:229-232` calls `asyncio.run(server.mcp.list_tools())`. Every coroutine is driven with `asyncio.run` (`:159-164`) because there is no pytest-asyncio plugin configured. Helpers `metadata_of:167-170`, `image_blocks:173-174`, `error_payload:177-180`.
- `test_contract_gates.py` (31.6K) — the cross-host gates. Runs `mcp_smoke.py` as a subprocess (`:129-153`), asserts the smoke really spawns the launcher (`:156-177`), asserts the launcher works from a foreign cwd with `PYTHONPATH` scrubbed (`:179-210`), pins SKILL.md/README.md numbers to `constants.py` (`:438-492`), and parses all six registrations (`:552-707`) plus the Codex (`:710-735`) and Claude (`:771-814`) timeout-ordering rules.
- `mcp_smoke.py` (12.5K) — standalone script, deliberately not pytest-collected (filename + no `test_*` functions, `:12-15`). Drives the real launcher over `mcp.client.stdio`.
- `fake_backend.py` (7.4K) — imported **inside** the spawned child; swaps `api.build_client` and `credentials.resolve_api_key`, and hard-fails `openai.AsyncOpenAI`. Its docstring at `:19-21` states the rule: "The production package deliberately has **no** environment-variable 'fake mode' switch, and must never grow one."
- `live_smoke.py` — the only script that spends money; refuses to run without `--i-understand-this-costs-money`.
- `test_api.py`, `test_images.py`, `test_credentials.py`, `test_redaction.py`, `test_validation.py` — per-module suites, 33-46K each.

Run command (from `README.md:144-149`): `py -3.12 -m pytest tests/gpt_image_2`.

### 7. Docs obligations that are test-enforced

A new capability that documents numbers has to keep them in sync — `test_contract_gates.py:438-462` parses `skills/<name>/SKILL.md` and the README's section against `constants.py`. Also expected: `docs/architecture/adr/NNNN-<slug>.md` (the repo convention is `docs/architecture/adr/`, not `docs/adr/`; 15 ADRs exist, latest `0015-standalone-gpt-image-2-mcp-server.md`), a `CHANGELOG.md` dated entry (see `:3-70` for the gpt-image-2 entries — long, reason-first prose), a `README.md` section, and `.batman/<task_slug>/{steering,spec,evidence}/` artifacts (the gpt-image-2 task has `understanding.md`, `constitution.md`, `product.md`, `structure.md`, `tech.md`, `requirements.md`, `design.md`, `tasks.md`, plus an `evidence/index.md`).

---

## Dependency / packaging situation

- **No `pyproject.toml`, no `setup.py`, no `setup.cfg`, no `package.json` anywhere in the repo.** `git ls-files` for dependency manifests returns only: `.codex/config.toml`, `gpt_image_2/requirements.txt`, `mnemo/requirements.txt` (plus unrelated `.batman/*/spec/requirements.md` and `prompts/requirements.prompt.md`).
- **Requirements files: two, one per subsystem, deliberately not merged.** `gpt_image_2/requirements.txt:1-4` says why: *"Kept separate from mnemo/requirements.txt on purpose (ADR 0015): a paid image subsystem must not be able to change what the shared-memory server installs."*
- **Pillow: yes, already a declared dependency — but only for `gpt_image_2`.** `C:\Users\josee\source\coding-cli\gpt_image_2\requirements.txt:17-20`:
```
# Local image validation, mask alpha inspection, and output verification.
# 10.0 is the floor for the modern `Image.getchannel` / `getextrema` behaviour
# used by the mask rules.
pillow>=10.0.0
```
  `mnemo/requirements.txt` does **not** list Pillow (it has `mcp>=1.2.0`, `qdrant-client>=1.9.0`, `openai>=1.40.0`, `tiktoken>=0.7.0`, `filelock>=3.12`).
- **Installed in the interpreter both hosts launch** (`C:/Users/josee/AppData/Local/Programs/Python/Python312/python.exe`): pillow 12.1.1, mcp 1.26.0, openai 2.8.1, qdrant-client 1.10.1, pytest 8.3.4, tiktoken 0.12.0, filelock 3.29.0. There is no venv in play — the MCP registrations point at the global Python 3.12. (`Lib/` and `Scripts/` exist at repo root but `Lib/site-packages/` is gitignored.)
- Install command documented at `README.md:72-73`: `py -3.12 -m pip install -r gpt_image_2/requirements.txt`.

---

## Checklist: what a new "capability" costs, concretely

1. `<pkg>/` Python package, layered `constants/errors → primitives → models → api → server`, only `server` importing `mcp`.
2. `<pkg>/requirements.txt` — its own file, not merged into an existing one.
3. `run_<pkg>_server.py` at repo root, mirroring `run_gpt_image_2_server.py:1-22`.
4. Register in `.mcp.json` (`mcpServers`), `.codex/config.toml` (`[mcp_servers.<name>]`), `.vscode/mcp.json` (`servers`) — plus the three user-scope files if activation is wanted outside the repo. Codex needs explicit `tool_timeout_sec` if any call can exceed 60 s; Claude needs per-server `timeout` in ms if any call can exceed the default.
5. `skills/<name>/SKILL.md` with `name` + trigger-and-anti-trigger `description` frontmatter; optional `agents/openai.yaml`.
6. `tests/<pkg>/` with `conftest.py` (autouse network/spend guard), per-module suites, an `mcp_smoke.py` stdio script, a `fake_backend.py` for the child process, and a `test_contract_gates.py` that runs the smoke and parses every registration.
7. `docs/architecture/adr/NNNN-*.md`, `CHANGELOG.md` entry, `README.md` section, `.batman/<slug>/` artifacts.
8. No hook changes needed.