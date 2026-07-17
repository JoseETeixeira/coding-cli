"""mnemo — self-hosted agentic shared-memory engine.

Append-only event log (source of truth) + Qdrant vector projection, exposed as an
MCP server so multiple agents (Claude Code, Codex, Copilot) share one memory
substrate. Replaces the retired repowise governed-memory role on generic hosts.
"""

__version__ = "0.1.0"
