from __future__ import annotations

import asyncio
import hashlib
import json
import os
import pathlib
import sys
from collections.abc import AsyncIterator

import cocoindex as coco
from cocoindex.connectors import localfs
from cocoindex.ops.text import RecursiveSplitter, detect_code_language
from cocoindex.resources.chunk import Chunk
from cocoindex.resources.file import FileLike, PatternFilePathMatcher

WORKDIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = pathlib.Path(os.getenv("FREIGHTHERO_REPO_ROOT", WORKDIR.parent.parent)).resolve()
INDEX_OUTPUT_DIR = pathlib.Path(
    os.getenv("CODEBASE_INDEX_DIR", WORKDIR / ".cocoindex" / "codebase-index")
)

CHUNK_SIZE = int(os.getenv("CODEBASE_CHUNK_SIZE", "1600"))
CHUNK_OVERLAP = int(os.getenv("CODEBASE_CHUNK_OVERLAP", "250"))
MAX_FILE_BYTES = int(os.getenv("CODEBASE_MAX_FILE_BYTES", "350000"))
MAX_INFLIGHT_COMPONENTS = int(os.getenv("COCOINDEX_MAX_INFLIGHT_COMPONENTS", "8"))

INDEX_ROOT = coco.ContextKey[pathlib.Path]("freighthero_codebase_index_root")

# Project discovery has three modes, in priority order. Mirrors the
# implementation in JoseETeixeira/coding-cli so `freighthero run indexing`
# can scope the index to the cwd (Windows users typically open VS Code at the
# project they're working on rather than the monorepo root):
#
#   1. CODEBASE_PROJECT_PATHS — explicit ``name=/abs/path`` entries, joined
#      by commas. Used when the cwd is outside the workspace, so the project
#      can live anywhere on disk.
#   2. CODEBASE_PROJECTS      — comma-separated names resolved under
#      REPO_ROOT. Used when the cwd is inside the workspace and we want to
#      scope to a single sibling project.
#   3. Auto-discover          — the historical hardcoded FreightHero set
#      (ai_watchtower, backend, frontend) when neither env var is set, so
#      legacy callers keep working unchanged.
PROJECTS_ENV = os.getenv("CODEBASE_PROJECTS", "").strip()
PROJECT_PATHS_ENV = os.getenv("CODEBASE_PROJECT_PATHS", "").strip()
DEFAULT_PROJECT_NAMES = ("ai_watchtower", "backend", "frontend")


def _parse_project_paths(raw: str) -> list[tuple[str, pathlib.Path]]:
    entries: list[tuple[str, pathlib.Path]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, _, path_str = item.partition("=")
        name = name.strip()
        path_str = path_str.strip()
        if not name or not path_str:
            continue
        candidate = pathlib.Path(path_str).expanduser().resolve()
        if candidate.is_dir():
            entries.append((name, candidate))
    return entries


def _discover_projects() -> list[tuple[str, pathlib.Path]]:
    if PROJECT_PATHS_ENV:
        return _parse_project_paths(PROJECT_PATHS_ENV)
    if PROJECTS_ENV:
        names = [item.strip() for item in PROJECTS_ENV.split(",") if item.strip()]
    else:
        names = list(DEFAULT_PROJECT_NAMES)
    projects: list[tuple[str, pathlib.Path]] = []
    for name in names:
        project_root = (REPO_ROOT / name).resolve()
        if project_root.is_dir():
            projects.append((name, project_root))
    return projects


# Resolved at import time so the rest of the pipeline can build ContextKeys
# and provide(...) calls deterministically.
PROJECT_LIST: list[tuple[str, pathlib.Path]] = _discover_projects()

# One ContextKey per discovered project, keyed by name so callers can fetch
# the right one without juggling a separate map. The key namespace mirrors
# the legacy ``freighthero_<name>_root`` shape for backwards compatibility
# with anything that introspects the index.
PROJECT_ROOT_KEYS: dict[str, "coco.ContextKey[pathlib.Path]"] = {
    name: coco.ContextKey[pathlib.Path](f"freighthero_{name}_root")
    for name, _ in PROJECT_LIST
}

# Legacy aliases for callers that imported the named constants directly.
# When the corresponding project is not in the current scope these names
# are intentionally absent from globals so ``from codebase_index import
# AI_WATCHTOWER_ROOT`` fails loudly rather than silently importing None.
for _name, _key in PROJECT_ROOT_KEYS.items():
    globals()[f"{_name.upper()}_ROOT"] = _key
del _name, _key

PROJECT_ROOTS = [(name, PROJECT_ROOT_KEYS[name]) for name, _ in PROJECT_LIST]

SOURCE_MATCHER = PatternFilePathMatcher(
    included_patterns=[
        "**/*.py",
        "**/*.ts",
        "**/*.tsx",
        "**/*.js",
        "**/*.jsx",
        "**/*.mjs",
        "**/*.cjs",
        "**/*.json",
        "**/*.md",
        "**/*.mdx",
        "**/*.yaml",
        "**/*.yml",
        "**/*.toml",
        "**/*.tf",
        "**/*.sql",
        "**/*.html",
        "**/*.css",
        "**/*.scss",
        "**/*.sh",
        "**/*.tex",
        "**/*.graphql",
        "**/*.proto",
        "**/Dockerfile",
        "**/Makefile",
    ],
    excluded_patterns=[
        "**/.git/**",
        "**/.venv/**",
        "**/venv/**",
        "**/node_modules/**",
        "**/__pycache__/**",
        "**/.pytest_cache/**",
        "**/.mypy_cache/**",
        "**/.ruff_cache/**",
        "**/.next/**",
        "**/.turbo/**",
        "**/dist/**",
        "**/build/**",
        "**/coverage/**",
        "**/target/**",
        "**/*.env",
        "**/.env",
        "**/local.env",
        "**/*.local.env",
        "**/*lock.json",
        "**/pnpm-lock.yaml",
        "**/yarn.lock",
        "**/package-lock.json",
        "**/*.pem",
        "**/*.key",
        "**/*.crt",
        "**/*.png",
        "**/*.jpg",
        "**/*.jpeg",
        "**/*.gif",
        "**/*.webp",
        "**/*.pdf",
        "**/*.zip",
    ],
)

_splitter = RecursiveSplitter()


@coco.lifespan
async def coco_lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    cocoindex_db = pathlib.Path(
        os.getenv("COCOINDEX_DB", str(WORKDIR / ".cocoindex" / "cocoindex.db"))
    )
    cocoindex_db.parent.mkdir(parents=True, exist_ok=True)
    INDEX_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    builder.settings.db_path = cocoindex_db
    # Provide every discovered project's resolved path against its ContextKey.
    # When PROJECT_PATHS_ENV was used the path may live outside REPO_ROOT; we
    # already resolved that in :func:`_discover_projects` so we pass it through
    # verbatim here rather than re-deriving from REPO_ROOT.
    for _name, _source_root in PROJECT_LIST:
        builder.provide(PROJECT_ROOT_KEYS[_name], _source_root)
    builder.provide(INDEX_ROOT, INDEX_OUTPUT_DIR)
    yield


def _chunk_id(project: str, file_path: pathlib.PurePath, chunk: Chunk) -> str:
    return hashlib.sha1(
        (
            f"{project}:{file_path.as_posix()}:"
            f"{chunk.start.char_offset}:{chunk.end.char_offset}:{chunk.text}"
        ).encode("utf-8")
    ).hexdigest()


def _display_path(project: str, file_path: pathlib.PurePath) -> str:
    return pathlib.PurePosixPath(project, file_path.as_posix()).as_posix()


def _language_for(file_path: pathlib.PurePath) -> str | None:
    detected = detect_code_language(filename=file_path.name)
    if detected:
        return detected
    if file_path.suffix in {".md", ".mdx", ".tex"}:
        return "markdown"
    return None


def _index_filename(project: str, file_path: pathlib.PurePath, chunk_id: str) -> str:
    flattened_path = "__".join(file_path.parts)
    safe_path = flattened_path.replace("/", "__") or "root"
    return f"{project}/{safe_path}__{chunk_id}.json"


@coco.fn
async def process_chunk(
    chunk: Chunk,
    project: str,
    file_path: pathlib.PurePath,
    target: localfs.DirTarget,
) -> None:
    chunk_id = _chunk_id(project, file_path, chunk)
    target.declare_file(
        _index_filename(project, file_path, chunk_id),
        json.dumps(
            {
                "id": chunk_id,
                "project": project,
                "filePath": _display_path(project, file_path),
                "lineStart": chunk.start.line,
                "lineEnd": chunk.end.line,
                "chunkStart": chunk.start.char_offset,
                "chunkEnd": chunk.end.char_offset,
                "content": chunk.text,
            },
            ensure_ascii=False,
        ),
        create_parent_dirs=True,
    )


@coco.fn(memo=True)
async def process_file(
    file: FileLike,
    project: str,
    target: localfs.DirTarget,
) -> None:
    if await file.size() > MAX_FILE_BYTES:
        return

    text = await file.read_text(errors="replace")
    if not text.strip():
        return

    file_path = file.file_path.path
    chunks = _splitter.split(
        text,
        chunk_size=CHUNK_SIZE,
        min_chunk_size=min(300, CHUNK_SIZE),
        chunk_overlap=CHUNK_OVERLAP,
        language=_language_for(file_path),
    )
    await coco.map(process_chunk, chunks, project, file_path, target)


@coco.fn
async def index_project(
    project: str,
    source_root: coco.ContextKey[pathlib.Path],
    target: localfs.DirTarget,
) -> None:
    files = localfs.walk_dir(
        source_root,
        recursive=True,
        path_matcher=SOURCE_MATCHER,
        live=True,
    )
    await coco.mount_each(process_file, files.items(), project, target)


@coco.fn
async def app_main() -> None:
    target_dir = await localfs.mount_dir_target(INDEX_ROOT)
    if not PROJECT_ROOTS:
        # No projects matched the current scope. Skip the mount loop instead
        # of registering an empty pipeline — cocoindex would otherwise log a
        # confusing "no components" warning. Print so the operator sees why.
        print(
            f"codebase_index: no projects to index "
            f"(CODEBASE_PROJECT_PATHS={PROJECT_PATHS_ENV!r} CODEBASE_PROJECTS={PROJECTS_ENV!r} "
            f"REPO_ROOT={REPO_ROOT})",
            file=sys.stderr,
        )
        return
    for project, source_root in PROJECT_ROOTS:
        await coco.mount(
            coco.component_subpath("project", project),
            index_project,
            project,
            source_root,
            target_dir,
        )


app = coco.App(
    coco.AppConfig(
        name="FreightHeroCodebase",
        max_inflight_components=MAX_INFLIGHT_COMPONENTS,
    ),
    app_main,
)


async def update_index() -> None:
    async with coco.runtime():
        await coco.show_progress(app.update())


if __name__ == "__main__" and pathlib.Path(sys.argv[0]).stem != "cocoindex":
    asyncio.run(update_index())
