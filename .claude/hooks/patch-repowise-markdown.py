#!/usr/bin/env python3
"""Idempotently patch the installed `repowise` tool so Markdown/AsciiDoc files
become eligible for the documentation (RAG-searchable) layer.

Why this exists
---------------
repowise already traverses `.md` files into its structural graph (they show up
as file nodes), but its page-generation selector documents only *code* files:
`selection/selector.py::_is_code_file` gates every page candidate on
`language in code_languages` (i.e. specs with `is_code=True`), and Markdown is
`is_code=False`. Result: `.md` content never gets a `wiki_page`, so it is
invisible to `search_codebase` / `get_answer` (the vector index is rebuilt from
wiki pages only).

Flipping the language spec to `is_code=True` does NOT work: `score_file` returns
0.0 for symbol-less files and Markdown has no AST symbols, so docs would still
never be selected — and it would pollute health/dead-code biomarkers. Instead we
route doc files into the *existing* `file_page` bucket with a size-based score.
`assemble_file_page` is null-safe for symbol-less / edge-less files and
`file_category()` already returns a "doc" voice for `.md`, so reusing the
file_page path needs no new page type and no persistence / cost-estimator / UI
changes.

Two precise gate edits:
  1. selection/selector.py  — `_build_file_candidates` also yields doc files,
     scored by size (capped low so big docs surface without crowding out code).
  2. page_generator/orchestrate.py — `code_files` includes doc languages so the
     level-2 file_page generator assembles + emits pages for selected docs.

This is a third-party tool patch, so it is wiped by `uv tool upgrade repowise`.
The FreightHero SessionStart hook re-runs this script every session, keeping the
patch applied. The script is idempotent (sentinel-guarded) and fail-soft: if an
anchor cannot be found (upstream refactor) it logs a clear warning and exits 0
without breaking the hook.

NOTE: this only makes docs *eligible*. Pages materialise on a full
`repowise update` (the SessionStart index refresh runs `--index-only`, which
skips LLM page generation by design). Run `repowise update --workspace` to
backfill `.md` pages once the patch is applied.
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

SENTINEL = "repowise-md-patch"


def _log(msg: str) -> None:
    print(f"[repowise-md-patch] {msg}")


def _resolve_pkg_dir() -> Path | None:
    """Locate the installed repowise package directory."""
    tool_python = Path.home() / ".local/share/uv/tools/repowise/bin/python"
    if tool_python.exists():
        try:
            out = subprocess.run(
                [str(tool_python), "-c", "import repowise, os; print(os.path.dirname(repowise.__file__))"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            cand = out.stdout.strip()
            if cand and Path(cand).is_dir():
                return Path(cand)
        except Exception as exc:  # noqa: BLE001
            _log(f"tool-python resolution failed: {exc}")
    # Fallback: glob the uv tool venv site-packages.
    for cand in glob.glob(str(Path.home() / ".local/share/uv/tools/repowise/lib/*/site-packages/repowise")):
        if Path(cand).is_dir():
            return Path(cand)
    return None


def _apply(path: Path, old: str, new: str, label: str) -> bool:
    """Replace `old` with `new` in `path`. Returns True on success/no-op."""
    if not path.exists():
        _log(f"WARN {label}: target file missing ({path}) — skipping")
        return False
    text = path.read_text(encoding="utf-8")
    if SENTINEL in text and new.strip() in text:
        return True  # already patched
    if old not in text:
        _log(f"WARN {label}: anchor not found (repowise upgraded? re-author the patch). Skipping.")
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    _log(f"applied {label}")
    return True


def patch_selector(pkg: Path) -> bool:
    f = pkg / "core/generation/selection/selector.py"
    ok = True

    # Edit 1a: doc helpers inserted right after `_is_code_file`.
    old_helper_anchor = (
        "def _is_code_file(parsed: Any) -> bool:\n"
        "    fi = parsed.file_info\n"
        "    return (\n"
        "        not fi.is_api_contract\n"
        "        and not _is_infra_file(parsed)\n"
        "        and fi.language in _CODE_LANGUAGES\n"
        "    )\n"
    )
    new_helper = old_helper_anchor + (
        "\n"
        f"# {SENTINEL}: route prose docs through the existing file_page path.\n"
        '_DOC_LANGUAGES = frozenset({"markdown", "asciidoc"})\n'
        "\n"
        "\n"
        "def _is_doc_file(parsed: Any) -> bool:\n"
        f"    # {SENTINEL}\n"
        "    return parsed.file_info.language in _DOC_LANGUAGES\n"
        "\n"
        "\n"
        "def _score_doc(parsed: Any) -> float:\n"
        f"    # {SENTINEL}: size-based score, capped low so big docs surface\n"
        "    # without crowding out code in the shared file_page budget.\n"
        "    size_kb = max(1, parsed.file_info.size_bytes // 1024)\n"
        "    return min(size_kb / 50.0, 1.0)\n"
    )
    ok &= _apply(f, old_helper_anchor, new_helper, "selector:doc-helpers")

    # Edit 1b: include doc files in `_build_file_candidates`.
    old_loop = (
        "    for p in inputs.parsed_files:\n"
        "        if not _is_code_file(p):\n"
        "            continue\n"
        "        path = p.file_info.path\n"
        '        is_hotspot = bool(git.get(path, {}).get("is_hotspot", False))\n'
    )
    new_loop = (
        "    for p in inputs.parsed_files:\n"
        "        if not _is_code_file(p):\n"
        f"            if _is_doc_file(p):  # {SENTINEL}\n"
        "                ds = _score_doc(p)\n"
        "                if ds > 0.0:\n"
        "                    scored.append((ds, p.file_info.path))\n"
        "            continue\n"
        "        path = p.file_info.path\n"
        '        is_hotspot = bool(git.get(path, {}).get("is_hotspot", False))\n'
    )
    ok &= _apply(f, old_loop, new_loop, "selector:file-candidates")
    return ok


def patch_orchestrate(pkg: Path) -> bool:
    f = pkg / "core/generation/page_generator/orchestrate.py"
    old = (
        "            if not p.file_info.is_api_contract\n"
        "            and not _is_infra_file(p)\n"
        "            and p.file_info.language in _CODE_LANGUAGES\n"
        "        ]\n"
    )
    new = (
        "            if not p.file_info.is_api_contract\n"
        "            and not _is_infra_file(p)\n"
        "            and (\n"
        "                p.file_info.language in _CODE_LANGUAGES\n"
        f'                or p.file_info.language in ("markdown", "asciidoc")  # {SENTINEL}\n'
        "            )\n"
        "        ]\n"
    )
    return _apply(f, old, new, "orchestrate:code-files")


def main() -> int:
    pkg = _resolve_pkg_dir()
    if pkg is None:
        _log("repowise package not found — nothing to patch (install with `uv tool install repowise`).")
        return 0
    a = patch_selector(pkg)
    b = patch_orchestrate(pkg)
    if a and b:
        _log("OK — Markdown/AsciiDoc are eligible for the doc layer. Run `repowise update --workspace` to backfill .md pages.")
    else:
        _log("PARTIAL/FAILED — see warnings above. The patch may need re-authoring for this repowise version.")
    return 0  # fail-soft: never break the SessionStart hook


if __name__ == "__main__":
    sys.exit(main())
