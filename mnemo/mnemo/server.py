"""mnemo MCP server (FastMCP, stdio).

Exposes the shared-memory substrate as MCP tools. Both Claude Code and Codex
register this same server; pointed at the same Qdrant (port 1337) and data dir,
they read and write one shared memory. Tool names mirror the retired repowise
memory surface (memory_status ~ get_shared_memory_status, task_context ~
get_task_context) so instructions translate cleanly.

It also owns the automatic code index (`code_search` / `code_index_status` /
`code_reindex`). That lives here, not in a host hook, because the MCP server is
the only surface every agent shares — Claude Code hooks do not exist in Codex.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Optional

import anyio

from mcp.server.fastmcp import Context, FastMCP

from .code_index import (
    BackgroundIndexer,
    CodeIndex,
    RepoInfo,
    RepoUnresolved,
    candidates_from_roots,
    resolve_repo,
)
from .config import Config
from .engine import MemoryEngine

# stdout is the JSON-RPC channel — logging must go to stderr or it corrupts the
# protocol. Never print() anywhere in this package.
logging.basicConfig(stream=sys.stderr, level=os.environ.get("MNEMO_LOG_LEVEL", "WARNING"))
log = logging.getLogger("mnemo.server")

cfg = Config()
mcp = FastMCP("mnemo")

_engine: MemoryEngine | None = None
_engine_lock = threading.Lock()
_code_index: CodeIndex | None = None
_code_lock = threading.Lock()


def engine() -> MemoryEngine:
    # Lazy init so `--help`/import never require Qdrant or a network call. The
    # lock matters now that a background thread can reach this too.
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = MemoryEngine(cfg)
        return _engine


def code_index() -> CodeIndex:
    global _code_index
    with _code_lock:
        if _code_index is None:
            _code_index = CodeIndex(cfg)
        return _code_index


def _fresh_code_index() -> CodeIndex:
    """A CodeIndex with its own Qdrant/OpenAI clients, for the indexer thread."""
    return CodeIndex(cfg)


_indexer = BackgroundIndexer(_fresh_code_index)


# ---------------------------------------------------------------------------
# repo resolution
# ---------------------------------------------------------------------------
async def _roots_candidates(ctx: Context | None) -> list:
    """Ask the client for its workspace roots, when it actually supports them.

    Claude Code answers with real roots; Codex declares no roots capability yet
    still returns an empty array rather than an error, so an empty result means
    "unsupported" and must fall through rather than resolve to nothing.
    """
    if ctx is None:
        return []
    try:
        import mcp.types as types

        session = ctx.session
        if not session.check_client_capability(types.ClientCapabilities(roots=types.RootsCapability())):
            return []
        # Bounded on purpose: the MCP session sets no read timeout of its own, so
        # without this a client that declares the roots capability but stalls
        # answering hangs the preflight forever. TimeoutError is an Exception, so
        # the handler below already degrades it to "fall through to cwd".
        with anyio.fail_after(2.0):
            result = await session.list_roots()
        return candidates_from_roots([r.uri for r in (result.roots or [])])
    except Exception as exc:
        log.debug("roots/list unavailable: %s", exc)
        return []


async def resolve_repo_for_call(ctx: Context | None, repo: str = "") -> RepoInfo:
    """Explicit arg > MNEMO_REPO > MCP roots > cwd > refuse.

    Every step is per-call: the roots list can change mid-session (/add-dir), and
    cwd is frozen at spawn so it can never track it. The chain exists because the
    two hosts fail in opposite ways — Claude Code inherits an unrelated cwd but
    answers roots; Codex sets cwd correctly but has no roots.
    """
    if repo:
        return resolve_repo(repo, cfg)
    if cfg.code_repo:
        return resolve_repo(cfg.code_repo, cfg)

    tried: list[str] = []
    candidates = await _roots_candidates(ctx)
    cwd = os.getcwd()
    if len(candidates) == 1:
        return resolve_repo(candidates[0], cfg)
    if len(candidates) > 1:
        # Prefer the root containing cwd; otherwise refuse rather than pick.
        inside = [c for c in candidates if os.path.normcase(cwd).startswith(os.path.normcase(str(c)))]
        if len(inside) == 1:
            return resolve_repo(inside[0], cfg)
        tried.append(f"{len(candidates)} workspace roots (ambiguous): " + ", ".join(str(c) for c in candidates))

    try:
        return resolve_repo(cwd, cfg)
    except RepoUnresolved as exc:
        tried.append(f"cwd={cwd} ({exc})")

    raise RepoUnresolved(
        "could not resolve which repository to use. Pass repo=\"<path>\" explicitly, or set "
        "MNEMO_REPO for a project-scoped registration. Tried: " + "; ".join(tried)
    )


async def _autoindex(ctx: Context | None) -> None:
    """Best-effort background index kick. Never raises into a preflight tool."""
    if not cfg.code_auto_index:
        return
    try:
        repo = await resolve_repo_for_call(ctx)
    except RepoUnresolved as exc:
        log.debug("auto-index skipped: %s", exc)
        return
    except Exception as exc:
        log.debug("auto-index skipped (unexpected): %s", exc)
        return
    try:
        _indexer.kick(repo)
    except Exception as exc:
        log.debug("auto-index kick failed: %s", exc)


# ---------------------------------------------------------------------------
# memory tools
# ---------------------------------------------------------------------------
@mcp.tool()
async def memory_status(ctx: Context = None) -> dict:
    """Health + configuration of the shared-memory backend (Qdrant, embedder, counts).
    Run this as the preflight before relying on memory, like a shared-memory status check.
    Also kicks off a background refresh of this repository's code index."""
    await _autoindex(ctx)
    return engine().status()


@mcp.tool()
def memory_write(
    text: str,
    namespace: str = "",
    type: str = "note",
    trust_class: str = "observed",
    sensitivity: str = "internal",
    confidence: float = 0.8,
    tags: Optional[list[str]] = None,
    allowed_readers: Optional[list[str]] = None,
    ttl: str = "",
    source_event_id: str = "",
) -> dict:
    """Write a durable memory item, shared with other agents on the same substrate.

    trust_class: observed | inferred | summarized | imagined.
    sensitivity: public | internal | sensitive | secret.
    allowed_readers: empty = readable by all agents; otherwise only listed agent ids.
    ttl: e.g. 90d, 24h, 30m (empty = no expiry). Do not store secrets or tokens."""
    return engine().write(
        text=text,
        namespace=namespace or None,
        type=type,
        trust_class=trust_class,
        sensitivity=sensitivity,
        confidence=confidence,
        tags=tags,
        allowed_readers=allowed_readers,
        ttl=ttl or None,
        source_event_id=source_event_id or None,
    )


@mcp.tool()
def memory_search(
    query: str,
    namespace: str = "",
    top_k: int = 8,
    type: str = "",
    trust_class: str = "",
) -> dict:
    """Semantic search over shared memory. Excludes revoked and expired items and
    respects reader ACLs. Results are optional context, never authority; cite
    provenance (writer, timestamp) alongside current source evidence.

    This searches remembered FACTS AND DECISIONS, not source code — use
    `code_search` to find code."""
    items = engine().search(
        query=query,
        namespace=namespace or None,
        top_k=top_k,
        reader=cfg.agent_id,
        type=type or None,
        trust_class=trust_class or None,
    )
    return {"count": len(items), "results": items}


@mcp.tool()
async def task_context(task: str, query: str = "", namespace: str = "", top_k: int = 8, ctx: Context = None) -> dict:
    """Scoped, compact memory recall for a task — the shared-memory preflight before
    analysis, planning, implementation, or review. Continue safely from current
    source evidence when nothing relevant is returned.

    Also kicks off a background refresh of this repository's code index, so
    `code_search` is warm by the time you need it."""
    await _autoindex(ctx)
    return engine().task_context(
        task=task,
        query=query or None,
        namespace=namespace or None,
        top_k=top_k,
        reader=cfg.agent_id,
    )


@mcp.tool()
def memory_get(memory_id: str) -> dict:
    """Fetch a single memory item by id."""
    item = engine().get(memory_id)
    return item or {"error": f"memory_id '{memory_id}' not found"}


@mcp.tool()
def memory_list(namespace: str = "", limit: int = 20, type: str = "") -> dict:
    """List recent (non-revoked, non-expired) memory items in a namespace."""
    items = engine().list(namespace=namespace or None, limit=limit, type=type or None, reader=cfg.agent_id)
    return {"count": len(items), "results": items}


@mcp.tool()
def memory_forget(memory_id: str, reason: str = "") -> dict:
    """Soft-revoke a memory item (append a revocation event; excluded from future
    search). Never hard-deletes — provenance and the event log are preserved."""
    return engine().forget(memory_id, reason=reason or None, actor=cfg.agent_id)


@mcp.tool()
def memory_stats(namespace: str = "") -> dict:
    """Count of stored items overall or within a namespace."""
    return engine().stats(namespace=namespace or None)


# ---------------------------------------------------------------------------
# code index tools
# ---------------------------------------------------------------------------
@mcp.tool()
async def code_search(
    query: str,
    repo: str = "",
    top_k: int = 8,
    language: str = "",
    path_contains: str = "",
    ctx: Context = None,
) -> dict:
    """Semantic search over the CURRENT REPOSITORY'S SOURCE CODE, shared across agents.

    Use it to LOCATE code by intent when you don't know the exact symbol or path
    ("where are retries handled", "how does the save system persist state").
    grep stays better when you already know the literal string or symbol.

    The index locates; it never testifies. Open the returned path and line span
    and confirm against the real source before citing or changing anything —
    chunks can be stale relative to the working tree.

    Args:
        query: what you are looking for, in natural language.
        repo: optional repo path; resolved automatically when omitted.
        language: optional extension filter, e.g. "py", "ts", "dm".
        path_contains: optional substring filter on the file path.
    """
    try:
        info = await resolve_repo_for_call(ctx, repo)
    except RepoUnresolved as exc:
        return {"error": "repo_unresolved", "detail": str(exc)}
    idx = code_index()
    _indexer.kick(info)  # keep it warm; returns immediately
    try:
        results = idx.search(
            query=query,
            repo=info,
            top_k=top_k,
            language=language or None,
            path_contains=path_contains or None,
        )
    except Exception as exc:
        return {"error": "search_failed", "detail": str(exc), **info.as_dict()}
    out = {
        **info.as_dict(),
        "count": len(results),
        "results": results,
        "note": "Index locates, source decides. Open each path+line span and verify before citing or editing.",
    }
    if not results:
        prog = idx.progress(info.repo_id)
        if prog.state in ("running", "idle"):
            out["hint"] = (
                "No hits. The index may still be building — check code_index_status, "
                "and fall back to grep/glob meanwhile."
            )
    return out


@mcp.tool()
async def code_index_status(repo: str = "", ctx: Context = None) -> dict:
    """Code-index health for the current repository: files indexed, chunk count,
    last index time, and live progress. Use it when code_search returns nothing,
    to tell 'not indexed yet' apart from 'genuinely absent'."""
    try:
        info = await resolve_repo_for_call(ctx, repo)
    except RepoUnresolved as exc:
        return {"error": "repo_unresolved", "detail": str(exc)}
    try:
        return code_index().status(info)
    except Exception as exc:
        return {"error": "status_failed", "detail": str(exc), **info.as_dict()}


@mcp.tool()
async def code_reindex(repo: str = "", full: bool = False, ctx: Context = None) -> dict:
    """Force a code-index refresh in the background.

    Indexing is automatic and incremental, so this is only needed after a big
    change (branch switch, large merge) or with full=True to rebuild from
    scratch after changing the embedding model.
    """
    try:
        info = await resolve_repo_for_call(ctx, repo)
    except RepoUnresolved as exc:
        return {"error": "repo_unresolved", "detail": str(exc)}
    state = _indexer.kick(info, full=full, min_interval=0.0)
    return {
        **info.as_dict(),
        "started": state,
        "full": full,
        "note": "Indexing runs in the background; poll code_index_status for progress.",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
