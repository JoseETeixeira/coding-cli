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
WORKSPACE_ROOT = pathlib.Path(os.getenv("WORKSPACE_ROOT", WORKDIR.parent.parent)).resolve()
INDEX_OUTPUT_DIR = pathlib.Path(
    os.getenv("CODEBASE_INDEX_DIR", WORKDIR / ".cocoindex" / "codebase-index")
)

CHUNK_SIZE = int(os.getenv("CODEBASE_CHUNK_SIZE", "1600"))
CHUNK_OVERLAP = int(os.getenv("CODEBASE_CHUNK_OVERLAP", "250"))
MAX_FILE_BYTES = int(os.getenv("CODEBASE_MAX_FILE_BYTES", "350000"))
MAX_INFLIGHT_COMPONENTS = int(os.getenv("COCOINDEX_MAX_INFLIGHT_COMPONENTS", "8"))

# Optional comma-separated allowlist of project directories to index. When unset,
# the indexer scans every top-level directory under WORKSPACE_ROOT except
# coding-cli itself (which hosts this MCP server and its own state).
PROJECTS_ENV = os.getenv("CODEBASE_PROJECTS", "").strip()
SKIP_PROJECT_NAMES = {"coding-cli"}

INDEX_ROOT = coco.ContextKey[pathlib.Path]("codebase_index_root")


def _discover_projects() -> list[tuple[str, pathlib.Path]]:
    if PROJECTS_ENV:
        names = [item.strip() for item in PROJECTS_ENV.split(",") if item.strip()]
    else:
        names = sorted(
            entry.name
            for entry in WORKSPACE_ROOT.iterdir()
            if entry.is_dir() and not entry.name.startswith(".") and entry.name not in SKIP_PROJECT_NAMES
        )

    projects: list[tuple[str, pathlib.Path]] = []
    for name in names:
        project_root = (WORKSPACE_ROOT / name).resolve()
        if project_root.is_dir():
            projects.append((name, project_root))
    return projects


PROJECT_LIST = _discover_projects()
PROJECT_KEYS = {
    name: coco.ContextKey[pathlib.Path](f"project_root_{name}")
    for name, _ in PROJECT_LIST
}

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
        "**/*.go",
        "**/*.java",
        "**/*.rs",
        "**/*.rb",
        "**/*.kt",
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
    for name, project_root in PROJECT_LIST:
        builder.provide(PROJECT_KEYS[name], project_root)
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
    for name, _ in PROJECT_LIST:
        await coco.mount(
            coco.component_subpath("project", name),
            index_project,
            name,
            PROJECT_KEYS[name],
            target_dir,
        )


app = coco.App(
    coco.AppConfig(
        name="WorkspaceCodebase",
        max_inflight_components=MAX_INFLIGHT_COMPONENTS,
    ),
    app_main,
)


async def update_index() -> None:
    async with coco.runtime():
        await coco.show_progress(app.update())


if __name__ == "__main__" and pathlib.Path(sys.argv[0]).stem != "cocoindex":
    asyncio.run(update_index())
