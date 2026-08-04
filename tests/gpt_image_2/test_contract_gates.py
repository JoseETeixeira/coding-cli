"""The gates that used to live outside `pytest`, pulled into the default run.

Three things this subsystem promised were only ever checked by a human
remembering to check them, which means they were not checked:

* **IMG-AC-009** — `mcp_smoke.py` proves the stdio contract end to end, but it
  is a standalone script. Nothing in `pytest tests/gpt_image_2` ran it, so a
  broken launcher or a corrupted stdout framing shipped green.
* **IMG-AC-013** — the numbers in `skills/gpt-image-2/SKILL.md` and `README.md`
  are what the *agent* believes the tool enforces. Nothing tied them to
  `gpt_image_2/constants.py`, so changing a constant left the skill confidently
  telling agents a limit that no longer exists.
* **IMG-AC-010** — six host registrations name one launcher file. Nothing
  parsed them, so a typo'd path or a pasted credential was invisible until a
  host failed to start.

Everything here is offline and deterministic. The two subprocess tests spawn
`sys.executable`; the fake backend inside those children makes the OpenAI
boundary unreachable, exactly as `conftest._block_real_network` does in-process.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable, NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = Path(__file__).resolve().parent

# `conftest.py` puts the repository root on `sys.path`; this keeps `mcp_smoke`
# importable too, independently of pytest's import mode.
for _root in (str(REPO_ROOT), str(TESTS_DIR)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

SMOKE_SCRIPT = TESTS_DIR / "mcp_smoke.py"
LAUNCHER = REPO_ROOT / "run_gpt_image_2_server.py"
SKILL_MD = REPO_ROOT / "skills" / "gpt-image-2" / "SKILL.md"
README_MD = REPO_ROOT / "README.md"

#: The launcher filename every host registration must name. Written out rather
#: than derived from `LAUNCHER` so a rename has to be made twice, on purpose.
LAUNCHER_FILENAME = "run_gpt_image_2_server.py"

SERVER_KEY = "gpt-image-2"

#: Generous: the smoke spawns a grandchild that imports mcp, openai, and Pillow.
#: It finishes in about two seconds on a warm filesystem; this only has to be
#: large enough that a cold CI disk is not mistaken for a hang.
SMOKE_TIMEOUT_S = 300.0
IMPORT_TIMEOUT_S = 120.0

from gpt_image_2 import constants  # noqa: E402 - sys.path is prepared above


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _require_interpreter() -> str:
    """Skip, not fail, when there is no interpreter to spawn.

    A frozen or embedded runtime reports an empty or non-existent
    `sys.executable`. That is an environment limitation, not a defect in this
    subsystem, so it must not turn the suite red.
    """
    executable = sys.executable
    if not executable or not Path(executable).is_file():
        pytest.skip("sys.executable is not a spawnable interpreter on this runtime")
    return executable


def _child_env(**overrides: str) -> dict[str, str]:
    """The parent environment, minus anything that could mask a real defect."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env.update(overrides)
    return env


def _run(
    args: list[str],
    *,
    cwd: Path,
    timeout: float,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd),
            env=env if env is not None else _child_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as expired:
        pytest.fail(
            f"{args[-1]} did not finish within {timeout:g}s — the stdio server "
            f"most likely hung.\nstdout:\n{expired.stdout}\nstderr:\n{expired.stderr}"
        )


def _report(proc: subprocess.CompletedProcess[str], label: str) -> str:
    return (
        f"{label} exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# IMG-AC-009 — the stdio smoke is part of the default gate
# ---------------------------------------------------------------------------


def test_mcp_smoke_passes_as_part_of_the_default_suite(tmp_path: Path) -> None:
    """Run `mcp_smoke.py` for real, so IMG-AC-009 stops being opt-in.

    Catches: anything that breaks the stdio contract — a `print()` on stdout
    corrupting JSON-RPC framing, a tool disappearing from `tools/list`, a
    credential/model/overwrite argument creeping into the schema, a saved file
    that does not match its metadata, or the rejected call spilling a file. All
    of that was previously only checked by a human remembering to run a script.

    Also catches the launcher regression this file was written for: the smoke
    now spawns `run_gpt_image_2_server.py` itself, so a renamed `main`, a moved
    file, or a dropped `sys.path` insert fails here instead of failing in six
    host registrations at once.
    """
    executable = _require_interpreter()
    assert SMOKE_SCRIPT.is_file(), f"the stdio smoke is missing: {SMOKE_SCRIPT}"

    proc = _run(
        [executable, str(SMOKE_SCRIPT)],
        cwd=tmp_path,
        timeout=SMOKE_TIMEOUT_S,
    )

    assert proc.returncode == 0, _report(proc, "mcp_smoke.py")
    assert "MCP SMOKE: PASS" in proc.stdout, _report(proc, "mcp_smoke.py")


def test_mcp_smoke_spawns_the_real_launcher() -> None:
    """The smoke's bootstrap must execute the file the hosts execute.

    Catches: reverting the bootstrap to
    `from gpt_image_2.server import main; main()`. That re-implements the
    launcher instead of running it, so `run_gpt_image_2_server.py` would go back
    to being byte-compiled and never executed by any gate — and every host
    registration points at exactly that file.
    """
    # Load by path under a capability-specific module name. A bare
    # `import mcp_smoke` resolves whichever sibling test directory pytest put
    # first on sys.path once more than one MCP server ships a smoke script.
    spec = importlib.util.spec_from_file_location("gpt_image_2_mcp_smoke", SMOKE_SCRIPT)
    assert spec is not None and spec.loader is not None
    mcp_smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_smoke)

    assert mcp_smoke.LAUNCHER == LAUNCHER
    assert LAUNCHER_FILENAME in mcp_smoke.BOOTSTRAP, (
        "the stdio smoke no longer executes the real launcher; its bootstrap is "
        f"{mcp_smoke.BOOTSTRAP!r}"
    )
    assert "runpy" in mcp_smoke.BOOTSTRAP
    assert "import fake_backend" in mcp_smoke.BOOTSTRAP, (
        "the fake backend must be installed before the launcher runs, or the "
        "smoke would reach the real OpenAI client"
    )


def test_launcher_bootstraps_from_a_foreign_cwd_without_pythonpath(
    tmp_path: Path,
) -> None:
    """The launcher's whole job: make the package importable from anywhere.

    Catches: deleting or breaking `sys.path.insert(0, REPOSITORY_ROOT)`,
    renaming `main`, or moving the launcher. Verified with `PYTHONPATH` scrubbed
    and the cwd somewhere else entirely, which is exactly the situation a host
    starts it in. `run_name` is deliberately NOT `__main__`, so the module body
    and the import run but `main()` does not — no server, no stdio, no waiting.

    The stdout assertion is the second half: the launcher and everything it
    imports must stay silent on stdout, because in production that stream is the
    JSON-RPC channel (constitution principle 6).
    """
    executable = _require_interpreter()
    assert LAUNCHER.is_file(), f"the launcher every host registers is missing: {LAUNCHER}"

    program = (
        "import runpy\n"
        f"ns = runpy.run_path({str(LAUNCHER)!r}, run_name='__launcher_import_check__')\n"
        "assert callable(ns.get('main')), 'launcher exposes no callable main()'\n"
        "print('LAUNCHER OK')\n"
    )
    proc = _run(
        [executable, "-c", program],
        cwd=tmp_path,
        timeout=IMPORT_TIMEOUT_S,
    )

    assert proc.returncode == 0, _report(proc, "launcher import check")
    assert proc.stdout.strip() == "LAUNCHER OK", _report(proc, "launcher import check")


# ---------------------------------------------------------------------------
# IMG-AC-013 — the agent-facing docs state the constants the tool enforces
# ---------------------------------------------------------------------------


class Claim(NamedTuple):
    """One number or token a document states, and the constant it must match."""

    label: str
    #: Exactly one capturing group, holding the stated value.
    pattern: str
    expected: Any


def _skill_text() -> str:
    assert SKILL_MD.is_file(), f"the agent-facing skill is missing: {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


def _readme_section() -> str:
    """Just the `## Images: gpt-image-2` section, so unrelated prose cannot match."""
    assert README_MD.is_file(), f"README.md is missing: {README_MD}"
    text = README_MD.read_text(encoding="utf-8")
    match = re.search(
        r"^## Images: gpt-image-2\s*$(?P<body>.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "README.md no longer has an '## Images: gpt-image-2' section"
    body = match.group("body")
    assert body.strip(), "the README's gpt-image-2 section is empty"
    return body


def _mib(value: int) -> int:
    return value // (1024 * 1024)


#: A documented integer, comma-grouped or not, that cannot swallow the sentence
#: punctuation after it (`max edge 3840,` must capture `3840`, not `3840,`).
_NUM = r"[\d,]*\d"

#: Small counts read better as words in prose. Mapped back so the claim is
#: still pinned to the constant rather than to the wording.
_WORD_NUMBERS = {"no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


#: `SKILL.md` is what the agent reads before spending money. Every number here
#: is a promise the tool must actually keep.
SKILL_CLAIMS: tuple[Claim, ...] = (
    Claim("MODEL", r"(gpt-image-\d+)", constants.MODEL),
    Claim(
        "OPERATION_DEADLINE_S",
        r"(\d+) seconds end to end",
        constants.OPERATION_DEADLINE_S,
    ),
    Claim("MAX_PROMPT_CHARS", rf"under ({_NUM}) characters", constants.MAX_PROMPT_CHARS),
    Claim("SIZE_EDGE_MULTIPLE", r"multiples? of (\d+)", constants.SIZE_EDGE_MULTIPLE),
    Claim("MAX_EDGE_PX", rf"max edge ({_NUM})", constants.MAX_EDGE_PX),
    Claim("MAX_ASPECT_RATIO", r"aspect at most (\d+):1", constants.MAX_ASPECT_RATIO),
    Claim(
        "MIN_TOTAL_PIXELS",
        rf"total pixels ({_NUM}) to {_NUM}",
        constants.MIN_TOTAL_PIXELS,
    ),
    Claim(
        "MAX_TOTAL_PIXELS",
        rf"total pixels {_NUM} to ({_NUM})",
        constants.MAX_TOTAL_PIXELS,
    ),
    Claim("MAX_N", r"Up to (\d+)\.", constants.MAX_N),
    Claim("DEFAULT_N", r"\| `n` \| `(\d+)` \|", constants.DEFAULT_N),
    Claim("DEFAULT_SIZE", r"\| `size` \| `(\d+x\d+)` \|", constants.DEFAULT_SIZE),
    Claim("DEFAULT_QUALITY", r"\| `quality` \| `(\w+)` \|", constants.DEFAULT_QUALITY),
    Claim(
        "DEFAULT_OUTPUT_FORMAT",
        r"\| `output_format` \| `(\w+)` \|",
        constants.DEFAULT_OUTPUT_FORMAT,
    ),
    Claim(
        "DEFAULT_BACKGROUND",
        r"\| `background` \| `(\w+)` \|",
        constants.DEFAULT_BACKGROUND,
    ),
    Claim(
        "DEFAULT_MODERATION",
        r"\| `moderation` \| `(\w+)` \|",
        constants.DEFAULT_MODERATION,
    ),
    Claim(
        "DEFAULT_BASENAME",
        r"\| `basename` \| `([\w.-]+)` \|",
        constants.DEFAULT_BASENAME,
    ),
    Claim(
        "DEFAULT_OUTPUT_SUBDIR",
        r"<working-directory>/([\w-]+)/",
        constants.DEFAULT_OUTPUT_SUBDIR,
    ),
    Claim(
        "MIN_COMPRESSION",
        r"`(\d+)` to `\d+`, JPEG/WebP only",
        constants.MIN_COMPRESSION,
    ),
    Claim(
        "MAX_COMPRESSION",
        r"`\d+` to `(\d+)`, JPEG/WebP only",
        constants.MAX_COMPRESSION,
    ),
    Claim(
        "CREDENTIAL_ENV_VAR", r"(OPENAI_API_KEY)", constants.CREDENTIAL_ENV_VAR
    ),
)

#: The README's gpt-image-2 section is the operator-facing half of the same
#: contract, including the per-attempt and preview bounds the skill does not
#: state. The operation deadline is stated in both and is pinned in both.
README_CLAIMS: tuple[Claim, ...] = (
    Claim("MODEL", r"`(gpt-image-\d+)`", constants.MODEL),
    Claim("SIZE_EDGE_MULTIPLE", r"multiples? of (\d+)", constants.SIZE_EDGE_MULTIPLE),
    Claim("MAX_EDGE_PX", rf"max edge ({_NUM})", constants.MAX_EDGE_PX),
    Claim("MAX_ASPECT_RATIO", r"aspect at most (\d+):1", constants.MAX_ASPECT_RATIO),
    Claim(
        "MIN_TOTAL_PIXELS",
        rf"({_NUM})\s+to\s+{_NUM}\s+total pixels",
        constants.MIN_TOTAL_PIXELS,
    ),
    Claim(
        "MAX_TOTAL_PIXELS",
        rf"{_NUM}\s+to\s+({_NUM})\s+total pixels",
        constants.MAX_TOTAL_PIXELS,
    ),
    Claim("MIN_N", r"`n` \((\d+) to \d+\)", constants.MIN_N),
    Claim("MAX_N", r"`n` \(\d+ to (\d+)\)", constants.MAX_N),
    Claim(
        "DEFAULT_SIZE",
        r"`size` \(default `(\d+x\d+)`",
        constants.DEFAULT_SIZE,
    ),
    Claim(
        "DEFAULT_QUALITY",
        r"`quality` \(default `(\w+)`\)",
        constants.DEFAULT_QUALITY,
    ),
    Claim(
        "DEFAULT_OUTPUT_FORMAT",
        r"`output_format` \(`(\w+)`/",
        constants.DEFAULT_OUTPUT_FORMAT,
    ),
    Claim(
        "DEFAULT_BACKGROUND",
        r"`background`\s*\(`(\w+)`/",
        constants.DEFAULT_BACKGROUND,
    ),
    Claim(
        "DEFAULT_BASENAME",
        r"basename is the generic `([\w.-]+)`",
        constants.DEFAULT_BASENAME,
    ),
    Claim(
        "DEFAULT_OUTPUT_SUBDIR",
        r"<working-directory>/([\w-]+)/",
        constants.DEFAULT_OUTPUT_SUBDIR,
    ),
    Claim(
        "OPERATION_DEADLINE_S",
        r"(\d+) seconds end to end",
        constants.OPERATION_DEADLINE_S,
    ),
    Claim(
        "API_ATTEMPT_TIMEOUT_S",
        r"(\d+)-second per-attempt",
        constants.API_ATTEMPT_TIMEOUT_S,
    ),
    Claim(
        "MAX_INLINE_PREVIEW_BYTES (MiB)",
        r"at most (\d+) MiB",
        _mib(constants.MAX_INLINE_PREVIEW_BYTES),
    ),
    Claim(
        "CREDENTIAL_ENV_VAR", r"`(OPENAI_API_KEY)`", constants.CREDENTIAL_ENV_VAR
    ),
    Claim(
        "MAX_INLINE_PREVIEWS",
        r"\b(no|one|two|three) images? (?:is|are) attached inline",
        constants.MAX_INLINE_PREVIEWS,
    ),
)


def _coerce(raw: str, expected: Any) -> Any:
    """Read the documented token in the constant's own type.

    Comma grouping is a documentation convention (`8,294,400`), not a value, so
    it is stripped before the comparison.
    """
    if isinstance(expected, bool):  # pragma: no cover - no boolean claims today
        raise TypeError("boolean claims are not supported")
    cleaned = raw.replace(",", "")
    if isinstance(expected, (int, float)):
        if cleaned.lower() in _WORD_NUMBERS:
            cleaned = str(_WORD_NUMBERS[cleaned.lower()])
        return type(expected)(cleaned)
    return raw


def _assert_claims(text: str, claims: Iterable[Claim], doc: str) -> None:
    for claim in claims:
        match = re.search(claim.pattern, text)
        assert match, (
            f"{doc} no longer states {claim.label}. The pattern "
            f"{claim.pattern!r} found nothing, so either the wording changed or "
            f"the limit was dropped from the agent-facing documentation. "
            f"gpt_image_2.constants says {claim.expected!r}."
        )
        stated = _coerce(match.group(1), claim.expected)
        assert stated == claim.expected, (
            f"{doc} says {claim.label} is {match.group(1)!r} but "
            f"gpt_image_2.constants says {claim.expected!r}. A constant was "
            f"changed without updating the documentation agents read, which "
            f"leaves the skill promising a limit the tool no longer enforces."
        )


@pytest.mark.parametrize(
    "claim", SKILL_CLAIMS, ids=[claim.label for claim in SKILL_CLAIMS]
)
def test_skill_md_agrees_with_constants(claim: Claim) -> None:
    """IMG-AC-013 for `skills/gpt-image-2/SKILL.md`.

    Catches: editing `gpt_image_2/constants.py` — MAX_PROMPT_CHARS, MAX_EDGE_PX,
    MIN/MAX_TOTAL_PIXELS, MAX_N, SIZE_EDGE_MULTIPLE, any default — without
    updating the skill. The skill is the only thing an agent reads before
    spending money, so a stale number there is a promise the tool will break.
    """
    _assert_claims(_skill_text(), [claim], "skills/gpt-image-2/SKILL.md")


@pytest.mark.parametrize(
    "claim", README_CLAIMS, ids=[claim.label for claim in README_CLAIMS]
)
def test_readme_gpt_image_section_agrees_with_constants(claim: Claim) -> None:
    """IMG-AC-013 for the `## Images: gpt-image-2` section of `README.md`.

    Catches: the same constant drift as the skill test, plus the operator-facing
    numbers the skill does not state — the 480 s per-attempt timeout and the
    5 MiB inline-preview ceiling. The 540 s operation deadline is stated in
    both documents, so both pin it.
    """
    _assert_claims(_readme_section(), [claim], "README.md (gpt-image-2 section)")


def test_docs_and_constants_agree_on_the_shared_numbers() -> None:
    """The two documents must not disagree with each other either.

    Both are compared to the constants above, so this is belt and braces — but
    it fails with one obvious message when a number is fixed in one file and
    forgotten in the other.
    """
    skill = _skill_text()
    readme = _readme_section()
    shared = {c.label for c in SKILL_CLAIMS} & {c.label for c in README_CLAIMS}
    assert shared, "the two claim tables no longer overlap; the cross-check is dead"

    by_label = {c.label: c for c in README_CLAIMS}
    for claim in SKILL_CLAIMS:
        if claim.label not in shared:
            continue
        other = by_label[claim.label]
        in_skill = re.search(claim.pattern, skill)
        in_readme = re.search(other.pattern, readme)
        assert in_skill and in_readme
        assert _coerce(in_skill.group(1), claim.expected) == _coerce(
            in_readme.group(1), other.expected
        ), (
            f"SKILL.md and README.md disagree about {claim.label}: "
            f"{in_skill.group(1)!r} vs {in_readme.group(1)!r}"
        )


# ---------------------------------------------------------------------------
# IMG-AC-010 — the six host registrations
# ---------------------------------------------------------------------------


def _strip_jsonc(text: str) -> str:
    """Remove `//` and `/* */` comments that are not inside a string.

    VS Code's `mcp.json` is JSONC. A naive `//` strip would also eat the `//` in
    `https://...`, which is why this tracks string state instead.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    in_string = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < length:
                out.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            index = length if end == -1 else end + 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _load_json_config(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSONC fallback. If this still fails the file really is malformed.
        return json.loads(_strip_jsonc(raw))


def _load_toml_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class Registration(NamedTuple):
    label: str
    path: Path
    kind: str  # "json" | "toml"
    servers_key: str


REPO_REGISTRATIONS: tuple[Registration, ...] = (
    Registration("repo/.mcp.json", REPO_ROOT / ".mcp.json", "json", "mcpServers"),
    Registration(
        "repo/.codex/config.toml",
        REPO_ROOT / ".codex" / "config.toml",
        "toml",
        "mcp_servers",
    ),
    Registration(
        "repo/.vscode/mcp.json", REPO_ROOT / ".vscode" / "mcp.json", "json", "servers"
    ),
)


def _vscode_user_mcp_json() -> Path:
    """The VS Code user `mcp.json`, per platform. Machine-specific by nature."""
    appdata = os.environ.get("APPDATA")
    candidates: list[Path] = []
    if appdata:
        candidates.append(Path(appdata) / "Code" / "User" / "mcp.json")
    candidates += [
        Path.home() / "AppData" / "Roaming" / "Code" / "User" / "mcp.json",
        Path.home() / "Library" / "Application Support" / "Code" / "User" / "mcp.json",
        Path.home() / ".config" / "Code" / "User" / "mcp.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _user_registrations() -> tuple[Registration, ...]:
    home = Path.home()
    return (
        Registration("user/~/.claude.json", home / ".claude.json", "json", "mcpServers"),
        Registration(
            "user/~/.codex/config.toml",
            home / ".codex" / "config.toml",
            "toml",
            "mcp_servers",
        ),
        Registration(
            "user/Code/User/mcp.json", _vscode_user_mcp_json(), "json", "servers"
        ),
    )


def _entry_of(registration: Registration) -> dict[str, Any]:
    loader = _load_json_config if registration.kind == "json" else _load_toml_config
    try:
        config = loader(registration.path)
    except Exception as exc:  # noqa: BLE001 - any parse failure is the finding
        pytest.fail(
            f"{registration.label} does not parse as {registration.kind}: "
            f"{type(exc).__name__}: {exc}. A host that cannot parse its own "
            f"configuration silently loses every server in it, not just this one."
        )

    servers = config.get(registration.servers_key)
    assert isinstance(servers, dict), (
        f"{registration.label} has no '{registration.servers_key}' object; every "
        f"previously registered server would be lost"
    )
    entry = servers.get(SERVER_KEY)
    assert isinstance(entry, dict), (
        f"{registration.label} has no '{SERVER_KEY}' entry (found "
        f"{sorted(servers)}), so the image tools never appear in that host"
    )
    return entry


#: A host may legitimately forward the credential *by name*. A literal value is
#: the thing that must never appear.
_INDIRECTION = re.compile(r"^(?:\$\{[^}]+\}|%[^%]+%|\$[A-Za-z_][A-Za-z0-9_]*)?$")


def _check_entry(entry: dict[str, Any], label: str) -> None:
    args = entry.get("args")
    assert isinstance(args, list) and args, f"{label}: '{SERVER_KEY}' has no args list"

    scripts = [str(arg) for arg in args if str(arg).lower().endswith(".py")]
    assert len(scripts) == 1, (
        f"{label}: '{SERVER_KEY}' should launch exactly one Python script; "
        f"args are {args!r}"
    )

    target = scripts[0].replace("\\", "/").rsplit("/", 1)[-1]
    assert target == LAUNCHER_FILENAME, (
        f"{label}: '{SERVER_KEY}' launches {target!r}, not {LAUNCHER_FILENAME!r}. "
        f"Every host registration must name the one canonical launcher, or the "
        f"host runs code no gate in this repository ever executes."
    )

    command = entry.get("command")
    assert isinstance(command, str) and command.strip(), (
        f"{label}: '{SERVER_KEY}' has no interpreter command"
    )

    # Constitution principle 1 and IMG-REQ-005: the credential is read from the
    # environment by the server, never written into a registration. Scoped to
    # this entry on purpose — unrelated servers in a user's file are not ours.
    serialized = json.dumps(entry, default=str)
    assert "sk-" not in serialized, (
        f"{label}: the '{SERVER_KEY}' entry contains an 'sk-' literal. A "
        f"credential must never appear in configuration."
    )

    configured = (entry.get("env") or {}).get(constants.CREDENTIAL_ENV_VAR)
    if configured is not None:
        assert _INDIRECTION.match(str(configured)), (
            f"{label}: the '{SERVER_KEY}' entry assigns a literal value to "
            f"{constants.CREDENTIAL_ENV_VAR}. Forwarding it by name is fine; "
            f"writing the value into configuration is not."
        )


@pytest.mark.parametrize(
    "registration", REPO_REGISTRATIONS, ids=[r.label for r in REPO_REGISTRATIONS]
)
def test_repo_registration_targets_the_canonical_launcher(
    registration: Registration,
) -> None:
    """IMG-AC-010 for the three in-repo adapters.

    Catches: a typo'd or renamed launcher path, a dropped `gpt-image-2` entry, a
    registration that no longer parses, and a credential pasted into config.
    These are repo-relative and versioned, so their absence is a defect.
    """
    assert registration.path.is_file(), (
        f"{registration.label} is missing from the repository: {registration.path}"
    )
    _check_entry(_entry_of(registration), registration.label)


@pytest.mark.parametrize("index", range(3), ids=["claude", "codex", "vscode"])
def test_user_registration_targets_the_canonical_launcher(index: int) -> None:
    """IMG-AC-010 for the three user-scope registries.

    These live outside the repository and differ per machine, so an absent file
    is a skip, not a failure. When one *is* present it has to be correct: the
    same launcher, and no credential value.
    """
    registration = _user_registrations()[index]
    if not registration.path.is_file():
        pytest.skip(
            f"{registration.label} is not present on this machine "
            f"({registration.path}); user-scope registrations are machine-specific"
        )
    _check_entry(_entry_of(registration), registration.label)


def test_codex_registrations_keep_the_host_timeout_above_the_operation_deadline() -> None:
    """Codex's 60 s default tool timeout would cut a normal generation off.

    Catches: dropping or lowering `tool_timeout_sec` in the Codex adapters. The
    server owns a 540 s deadline and returns a structured error at the end of
    it; a host timeout below that replaces our error with the host's, which is
    the failure mode the README specifically documents.
    """
    checked = 0
    for path in (REPO_ROOT / ".codex" / "config.toml", Path.home() / ".codex" / "config.toml"):
        if not path.is_file():
            continue
        entry = _load_toml_config(path).get("mcp_servers", {}).get(SERVER_KEY)
        if entry is None:
            continue
        timeout = entry.get("tool_timeout_sec")
        assert isinstance(timeout, (int, float)), (
            f"{path}: '{SERVER_KEY}' sets no tool_timeout_sec, so Codex applies "
            f"its 60s default and aborts normal high-quality generations"
        )
        assert timeout > constants.OPERATION_DEADLINE_S, (
            f"{path}: tool_timeout_sec={timeout} is not above the server's "
            f"{constants.OPERATION_DEADLINE_S:g}s operation deadline"
        )
        checked += 1
    assert checked, "no Codex registration was found to check"


def test_retry_floor_is_a_usable_fraction_of_an_attempt() -> None:
    """A retry admitted below this floor can only time out — after being billed.

    `_call_with_retry` admits the retry on remaining budget and then clamps that
    attempt to `min(API_ATTEMPT_TIMEOUT_S, remaining)`, so
    `RETRY_MIN_REMAINING_S` is not merely an admission threshold: it is the
    floor on the *second* attempt's timeout. At its original 20 s it admitted
    retries with a 20-second window against a multi-minute generation. That
    retry could only produce `api_timeout` — the one failure this subsystem
    never retries because the request may already have been billed — and it
    destroyed the actionable `service_error` it replaced.

    No unit test can catch this: the relation `retried timeout >= floor` holds
    for *any* floor, and the fake clock never puts a scripted retry near the
    boundary. So the value itself is pinned here, from both sides — high enough
    that an admitted retry can plausibly finish, low enough that the retry path
    does not become dead code.
    """
    assert constants.RETRY_MIN_REMAINING_S >= constants.API_ATTEMPT_TIMEOUT_S / 2, (
        f"RETRY_MIN_REMAINING_S={constants.RETRY_MIN_REMAINING_S:g} is under half "
        f"of API_ATTEMPT_TIMEOUT_S={constants.API_ATTEMPT_TIMEOUT_S:g}, so a "
        f"retry can be admitted with a window too short to finish in"
    )
    assert (
        constants.RETRY_MIN_REMAINING_S
        < constants.OPERATION_DEADLINE_S - constants.MAX_RETRY_AFTER_S
    ), (
        f"RETRY_MIN_REMAINING_S={constants.RETRY_MIN_REMAINING_S:g} leaves no "
        f"admit window under a {constants.OPERATION_DEADLINE_S:g}s deadline with a "
        f"{constants.MAX_RETRY_AFTER_S:g}s Retry-After cap: the retry path is dead"
    )


def test_claude_registrations_keep_the_host_timeout_above_the_operation_deadline() -> None:
    """The Claude half of the same ordering rule, which Codex's gate does not cover.

    Claude Code's `MCP_TOOL_TIMEOUT` default is roughly 28 hours, so before a
    per-server `timeout` existed this host could not cut a generation off and
    needed no gate. Setting `"timeout"` (milliseconds) on the registry entry
    makes it a real ceiling — and therefore a real way to violate
    `attempt < operation deadline < host tool timeout`.

    Catches: raising `OPERATION_DEADLINE_S` past a Claude registration's
    `timeout`, which the Codex gate cannot see. The field is optional by
    design: absent means the ~28-hour default, which is above any plausible
    deadline, so only a present-but-too-low value is a finding.
    """
    checked = 0
    for registration in (
        Registration("repo/.mcp.json", REPO_ROOT / ".mcp.json", "json", "mcpServers"),
        Registration(
            "user/~/.claude.json", Path.home() / ".claude.json", "json", "mcpServers"
        ),
    ):
        if not registration.path.is_file():
            continue
        entry = (
            _load_json_config(registration.path)
            .get(registration.servers_key, {})
            .get(SERVER_KEY)
        )
        if entry is None:
            continue
        timeout_ms = entry.get("timeout")
        if timeout_ms is None:
            continue  # falls through to the ~28h MCP_TOOL_TIMEOUT default
        assert isinstance(timeout_ms, (int, float)), (
            f"{registration.label}: 'timeout' must be a number of milliseconds, "
            f"got {timeout_ms!r}"
        )
        assert timeout_ms / 1000 > constants.OPERATION_DEADLINE_S, (
            f"{registration.label}: timeout={timeout_ms}ms is not above the "
            f"server's {constants.OPERATION_DEADLINE_S:g}s operation deadline, so "
            f"Claude Code replaces our structured error with its own"
        )
        checked += 1
    assert checked, "no Claude registration with a per-server timeout was found to check"
