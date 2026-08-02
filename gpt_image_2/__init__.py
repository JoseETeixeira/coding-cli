"""Standalone GPT Image 2 MCP subsystem.

Canonical implementation of the `gpt-image-2` capability: one stdio MCP server
exposing `generate_image` and `edit_image`, backed by OpenAI's direct Image API.

Deliberately independent of `mnemo` (ADR 0015): a paid, credential-bearing,
large-binary side effect must not be able to make the shared-memory preflight
unavailable.

Import order inside this package is strictly one-directional::

    constants, errors  ->  credentials, images  ->  models  ->  api  ->  server

Only `server` imports `mcp`. Only `api` imports `openai`. Everything else is
pure enough to test without stdio and without a network.
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
