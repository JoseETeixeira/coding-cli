"""Engine tests against a real Qdrant on port 1337, using a deterministic fake
embedder (no network / no OpenAI cost). Each test run uses a throwaway collection
that is deleted on teardown.

Run:  py -3.12 -m pytest mnemo/tests -q
Skips automatically if Qdrant is unreachable.
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mnemo.config import Config  # noqa: E402
from mnemo.engine import MemoryEngine, parse_ttl, redact  # noqa: E402

QDRANT_URL = os.environ.get("MNEMO_QDRANT_URL", "http://127.0.0.1:1337")
DIM = 64


class FakeEmbedder:
    """Deterministic hash-based embedding — same text -> same vector, no network."""

    dim = DIM

    def embed(self, texts):
        return [self.embed_one(t) for t in texts]

    def embed_one(self, text):
        vec = [0.0] * DIM
        for token in text.lower().split():
            h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
            vec[h % DIM] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


def _qdrant_up() -> bool:
    try:
        import urllib.request

        urllib.request.urlopen(QDRANT_URL + "/readyz", timeout=2).read()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_up(), reason="Qdrant not reachable on 1337")


@pytest.fixture()
def engine(tmp_path):
    cfg = Config()
    cfg.collection = f"mnemo_test_{uuid.uuid4().hex[:8]}"
    cfg.qdrant_url = QDRANT_URL
    cfg.agent_id = "agent-A"
    cfg.data_dir = tmp_path  # keep event logs out of the real ~/.mnemo
    eng = MemoryEngine(cfg, embedder=FakeEmbedder())
    yield eng
    try:
        eng.client.delete_collection(cfg.collection)
    except Exception:
        pass


def test_write_then_search_roundtrip(engine):
    res = engine.write("retry middleware duplicates POST capture on timeout", namespace="repo:payments")
    assert res["memory_id"]
    hits = engine.search("why are payment captures duplicated", namespace="repo:payments", reader="agent-A")
    assert hits, "expected the written memory to be retrievable"
    assert hits[0]["memory_id"] == res["memory_id"]
    assert "duplicate" in hits[0]["text"] or "duplicates" in hits[0]["text"]


def test_forget_excludes_from_search(engine):
    res = engine.write("temporary note about flaky test", namespace="repo:payments")
    mid = res["memory_id"]
    assert engine.search("flaky test note", namespace="repo:payments", reader="agent-A")
    out = engine.forget(mid, reason="obsolete")
    assert out["ok"] is True
    hits = engine.search("flaky test note", namespace="repo:payments", reader="agent-A")
    assert all(h["memory_id"] != mid for h in hits), "revoked item must not appear in search"


def test_namespace_isolation(engine):
    engine.write("alpha secret sauce recipe", namespace="repo:alpha")
    hits = engine.search("alpha secret sauce recipe", namespace="repo:beta", reader="agent-A")
    assert hits == [], "namespace B must not see namespace A's memory"


def test_reader_acl_private_item_hidden(engine):
    engine.write("private plan for agent-A only", namespace="team", allowed_readers=["agent-A"])
    assert engine.search("private plan", namespace="team", reader="agent-A"), "owner can read"
    other = engine.search("private plan", namespace="team", reader="agent-B")
    assert other == [], "non-listed reader must not see a private item"


def test_public_item_visible_to_any_reader(engine):
    engine.write("public shared fact about the build", namespace="team")
    assert engine.search("public shared fact", namespace="team", reader="agent-B"), "public item visible to any agent"


def test_cross_agent_sharing(engine):
    """Two engines (different agent ids) over the same collection = shared substrate."""
    writer_cfg = engine.cfg
    from mnemo.config import Config as C

    cfg_b = C()
    cfg_b.collection = writer_cfg.collection
    cfg_b.qdrant_url = writer_cfg.qdrant_url
    cfg_b.data_dir = writer_cfg.data_dir
    cfg_b.agent_id = "agent-B"
    engine_b = MemoryEngine(cfg_b, embedder=FakeEmbedder())

    engine.write("shared architecture decision: use event log as source of truth", namespace="global")
    hits = engine_b.search("architecture decision event log", namespace="global", reader="agent-B")
    assert hits, "agent-B must read what agent-A wrote (shared memory)"


def test_ttl_and_redaction_units():
    assert parse_ttl("90d") == 90 * 86400
    assert parse_ttl("24h") == 24 * 3600
    assert parse_ttl("30m") == 1800
    assert parse_ttl("") is None
    red, n = redact("email me at test@example.com with key sk-ABCDEFGHIJKLMNOPQRSTUVWX")
    assert "[redacted:email]" in red and n >= 2
