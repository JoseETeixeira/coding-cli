"""Optical-compression cross-host wiring and packaging gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SERVER_LAUNCHER = REPOSITORY_ROOT / "run_optical_compression_server.py"
HOOK_LAUNCHER = REPOSITORY_ROOT / "run_optical_compression_hook.py"


def _json(relative: str) -> dict:
    return json.loads((REPOSITORY_ROOT / relative).read_text(encoding="utf-8"))


def _text(relative: str) -> str:
    return (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")


def _imported_launcher_store(launcher: Path, tmp_path: Path, override: Path | None = None) -> Path:
    """Import a launcher from a foreign cwd and report its resolved store env."""

    fake_home = tmp_path / "home"
    foreign_cwd = tmp_path / "foreign"
    fake_home.mkdir(exist_ok=True)
    foreign_cwd.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["USERPROFILE"] = str(fake_home)
    if override is None:
        env.pop("OPTICAL_COMPRESSION_DIR", None)
    else:
        env["OPTICAL_COMPRESSION_DIR"] = str(override)

    code = (
        "import importlib.util, os; "
        f"p={str(launcher)!r}; "
        "s=importlib.util.spec_from_file_location('optical_launcher_contract', p); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "print(os.environ['OPTICAL_COMPRESSION_DIR'])"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=foreign_cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return Path(completed.stdout.strip()).resolve()


def test_repository_registrations_point_at_the_canonical_launcher() -> None:
    expected = str(SERVER_LAUNCHER).replace("\\", "/")

    claude = _json(".mcp.json")["mcpServers"]["optical-compression"]
    assert claude["args"] == [expected]
    assert claude["env"] == {"CLAUDECODE": "1"}

    codex = tomllib.loads(_text(".codex/config.toml"))["mcp_servers"]["optical-compression"]
    assert codex["args"] == [expected]
    assert codex["env"] == {"CODEX_SESSION": "1"}

    copilot = _json(".vscode/mcp.json")["servers"]["optical-compression"]
    assert copilot["args"] == [expected]


def test_generic_workflow_routes_large_payloads_to_the_skill() -> None:
    skill_path = REPOSITORY_ROOT / "skills" / "optical-compression" / "SKILL.md"
    assert skill_path.is_file()
    assert "skills/optical-compression/SKILL.md" in _text("AGENTS.md")
    assert "`optical-compression`" in _text("skills/generic-entry/SKILL.md")


def test_claude_plugin_manifest_wires_only_the_read_hook() -> None:
    manifest = _json("hooks/hooks.json")["hooks"]
    matches = [entry for entry in manifest["PostToolUse"] if entry.get("matcher") == "Read"]
    assert len(matches) == 1
    commands = [hook["command"] for hook in matches[0]["hooks"]]
    assert commands == ['python "${CLAUDE_PLUGIN_ROOT}/run_optical_compression_hook.py"']


def test_dependency_contract_is_owned_by_the_optical_package() -> None:
    requirements = _text("optical_compression/requirements.txt").lower()
    assert "mcp>=1.10.0" in requirements
    assert "pillow>=10.0.0" in requirements


def test_launchers_share_a_home_scoped_default_and_preserve_override(tmp_path: Path) -> None:
    expected = (tmp_path / "home" / ".optical-compression").resolve()
    override = (tmp_path / "operator-store").resolve()

    for launcher in (SERVER_LAUNCHER, HOOK_LAUNCHER):
        assert _imported_launcher_store(launcher, tmp_path) == expected
        assert _imported_launcher_store(launcher, tmp_path, override) == override


def test_docs_expose_install_store_activation_and_validation_contracts() -> None:
    readme = _text("README.md")
    skill = _text("skills/optical-compression/SKILL.md")
    installation = _text("docs/optical-compression-installation.md")
    install = "py -3.12 -m pip install -r optical_compression/requirements.txt"

    assert install in readme
    assert install in skill
    assert install in installation
    assert "~/.optical-compression" in readme
    assert "~/.optical-compression" in skill
    assert "~/.optical-compression" in installation
    assert "tests/optical_compression/mcp_smoke.py" in readme
    assert "claude mcp add" in installation
    assert "codex mcp add" in installation
    assert "USER_SKILLS_DIR" in installation
    assert "Do not enable both paths simultaneously" in installation
    assert "Do not enable both paths simultaneously" in skill
