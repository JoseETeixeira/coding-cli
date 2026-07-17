"""Embedding backend for mnemo.

OpenAI only, by product decision: memory embeddings always go through the OpenAI
Embeddings API with no local fallback. Tests inject a deterministic fake embedder
so they never call the network.

Batching note: memory writes embed one text at a time, but the code index embeds
thousands of chunks per run, so `embed()` sub-batches on both a token budget and
an input count. Two correctness rules are load-bearing there:

  1. OpenAI's `data[].index` is REQUEST-relative. Vectors must be reassembled
     per sub-batch — a global sort across concatenated responses silently
     attaches vectors to the wrong texts (no exception, no log).
  2. Inputs are truncated by TOKENS, never characters. Minified JS and base64
     run near 1:1 token:char and would blow the model's 8192-token input cap.
"""

from __future__ import annotations

import logging
from typing import Protocol, Sequence

log = logging.getLogger("mnemo.embedders")

# text-embedding-3-* accept 8192 tokens per input; keep headroom for safety.
MAX_INPUT_TOKENS = 8100
# Sub-batch caps. The token cap binds first for code chunks (~300-1500 tokens
# each); the input-count cap is the backstop for many tiny texts.
BATCH_MAX_TOKENS = 100_000
BATCH_MAX_INPUTS = 128


class Embedder(Protocol):
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_one(self, text: str) -> list[float]: ...


class _Tokenizer:
    """tiktoken when available; a conservative char/3 estimate otherwise.

    `disallowed_special=()` is required: source code legitimately contains
    literal `<|endoftext|>`-shaped strings and tiktoken raises ValueError on
    those by default.
    """

    def __init__(self, model: str):
        self._enc = None
        try:
            import tiktoken

            try:
                self._enc = tiktoken.encoding_for_model(model)
            except KeyError:
                self._enc = tiktoken.get_encoding("cl100k_base")
        except Exception:  # pragma: no cover - tiktoken is a declared dep
            log.warning("tiktoken unavailable; falling back to a char-based token estimate")

    def count(self, text: str) -> int:
        if self._enc is None:
            return max(1, len(text) // 3)
        return len(self._enc.encode(text, disallowed_special=()))

    def truncate(self, text: str, max_tokens: int = MAX_INPUT_TOKENS) -> tuple[str, bool]:
        if self._enc is None:
            limit = max_tokens * 3
            if len(text) <= limit:
                return text, False
            return text[:limit], True
        toks = self._enc.encode(text, disallowed_special=())
        if len(toks) <= max_tokens:
            return text, False
        return self._enc.decode(toks[:max_tokens]), True


class OpenAIEmbedder:
    def __init__(self, model: str, api_key: str | None, dim: int, base_url: str | None = None):
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required — mnemo uses OpenAI embeddings with no local fallback."
            )
        from openai import OpenAI  # imported lazily so tests don't need the SDK

        # SDK default is 2 retries — too low for a multi-thousand-chunk index run.
        kwargs = {"api_key": api_key, "max_retries": 5}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self.model = model
        self.dim = dim
        self._tok = _Tokenizer(model)

    # ---- batching --------------------------------------------------------
    def _prepare(self, texts: Sequence[str]) -> list[str]:
        """Truncate to the model's input cap and guard empties (the API rejects
        empty strings)."""
        out: list[str] = []
        for i, t in enumerate(texts):
            t = t if (t and t.strip()) else "(empty)"
            t, was_truncated = self._tok.truncate(t)
            if was_truncated:
                # Hitting this usually means the chunker produced an oversized chunk.
                log.warning("embed input %d exceeded %d tokens and was truncated", i, MAX_INPUT_TOKENS)
            out.append(t)
        return out

    def _batches(self, texts: Sequence[str]) -> list[tuple[int, int]]:
        """Split into (start, end) spans honouring both the token and count caps."""
        spans: list[tuple[int, int]] = []
        start = 0
        tokens = 0
        for i, t in enumerate(texts):
            n = self._tok.count(t)
            if i > start and (tokens + n > BATCH_MAX_TOKENS or i - start >= BATCH_MAX_INPUTS):
                spans.append((start, i))
                start = i
                tokens = 0
            tokens += n
        if start < len(texts):
            spans.append((start, len(texts)))
        return spans

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.model, input=batch)
        # `index` is request-relative, so this sort is only valid WITHIN one
        # sub-batch. Never sort across concatenated responses.
        ordered = sorted(resp.data, key=lambda d: d.index)
        vectors = [d.embedding for d in ordered]
        if len(vectors) != len(batch):
            raise RuntimeError(
                f"embedding count mismatch: sent {len(batch)} inputs, got {len(vectors)} vectors"
            )
        return vectors

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        prepared = self._prepare(texts)
        out: list[list[float]] = []
        for start, end in self._batches(prepared):
            out.extend(self._embed_batch(prepared[start:end]))
        if len(out) != len(texts):  # pragma: no cover - defensive
            raise RuntimeError(f"embedding count mismatch: {len(texts)} texts -> {len(out)} vectors")
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


def make_embedder(cfg) -> Embedder:
    if cfg.embedder != "openai":
        raise ValueError(
            f"mnemo only supports the 'openai' embedder (no local fallback); got '{cfg.embedder}'."
        )
    return OpenAIEmbedder(
        model=cfg.embed_model,
        api_key=cfg.openai_api_key,
        dim=cfg.embed_dim,
        base_url=cfg.openai_base_url,
    )
