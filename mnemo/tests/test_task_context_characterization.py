"""Characterization tests for the existing task-context response surface.

These tests intentionally avoid Qdrant. They capture compatibility fields and
rank order that bounded preview serialization must preserve.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mnemo.engine import MemoryEngine  # noqa: E402


class _FakeEngine:
    cfg = SimpleNamespace(
        default_namespace="global",
        task_context_max_text_chars=4000,
        task_context_item_preview_chars=500,
        task_context_response_max_chars=8000,
    )

    def search(self, query, namespace, top_k, reader):
        assert query == "implement pilot\nbounded recall"
        assert namespace == "repo:coding-cli"
        assert top_k == 2
        assert reader == "agent-A"
        return [
            {"memory_id": "first", "text": "short first", "score": 0.9},
            {"memory_id": "second", "text": "short second", "score": 0.8},
        ]


def test_task_context_preserves_public_fields_and_rank_order():
    result = MemoryEngine.task_context(
        _FakeEngine(),
        task="implement pilot",
        query="bounded recall",
        namespace="repo:coding-cli",
        top_k=2,
        reader="agent-A",
    )

    assert result["namespace"] == "repo:coding-cli"
    assert result["task"] == "implement pilot"
    assert result["count"] == 2
    assert [item["memory_id"] for item in result["memory"]] == ["first", "second"]
    assert [item["text"] for item in result["memory"]] == ["short first", "short second"]
    assert "not authority" in result["note"]


def test_to_item_preserves_existing_metadata_shape():
    item = MemoryEngine._to_item(
        {
            "memory_id": "m1",
            "namespace": "repo:coding-cli",
            "text": "fact",
            "type": "spec",
            "trust_class": "summarized",
            "sensitivity": "internal",
            "confidence": 0.8,
            "tags": ["active"],
            "writer": "agent-A",
            "timestamp": "2026-08-01T00:00:00Z",
            "source_event_id": "event-1",
            "expires_at": None,
        },
        score=0.87654,
    )

    assert item == {
        "memory_id": "m1",
        "namespace": "repo:coding-cli",
        "text": "fact",
        "type": "spec",
        "trust_class": "summarized",
        "sensitivity": "internal",
        "confidence": 0.8,
        "tags": ["active"],
        "writer": "agent-A",
        "timestamp": "2026-08-01T00:00:00Z",
        "source_event_id": "event-1",
        "expires_at": None,
        "score": 0.8765,
    }
