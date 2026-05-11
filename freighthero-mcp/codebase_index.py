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

AI_WATCHTOWER_ROOT = coco.ContextKey[pathlib.Path]("freighthero_ai_watchtower_root")
BACKEND_ROOT = coco.ContextKey[pathlib.Path]("freighthero_backend_root")
FRONTEND_ROOT = coco.ContextKey[pathlib.Path]("freighthero_frontend_root")
INDEX_ROOT = coco.ContextKey[pathlib.Path]("freighthero_codebase_index_root")

PROJECT_ROOTS = [
    ("ai_watchtower", AI_WATCHTOWER_ROOT),
    ("backend", BACKEND_ROOT),
    ("frontend", FRONTEND_ROOT),
]

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
    builder.provide(AI_WATCHTOWER_ROOT, REPO_ROOT / "ai_watchtower")
    builder.provide(BACKEND_ROOT, REPO_ROOT / "backend")
    builder.provide(FRONTEND_ROOT, REPO_ROOT / "frontend")
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
