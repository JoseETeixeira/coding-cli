"""Offline TDD contract for bounded task-context previews and exact retrieval."""

from __future__ import annotations

import json
import os
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mnemo.config import Config  # noqa: E402
from mnemo.engine import MemoryEngine, build_task_context_response  # noqa: E402

MEMORY_ID = "11111111-1111-4111-8111-111111111111"


def _config(**overrides):
    values = {
        "task_context_max_text_chars": 20,
        "task_context_item_preview_chars": 8,
        "task_context_response_max_chars": 2_400,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _items():
    return [
        {"memory_id": "m1", "text": "abcdefghijk", "score": 0.9, "tags": ["first"]},
        {"memory_id": "m2", "text": "1234567890", "score": 0.8, "tags": ["second"]},
        {"memory_id": "m3", "text": "tail", "score": 0.7, "tags": ["third"]},
    ]


def test_preview_budget_preserves_order_ids_and_legacy_memory_field():
    response = build_task_context_response(
        namespace="repo:coding-cli",
        task="bounded recall",
        items=_items(),
        config=_config(),
    )

    assert response["contract_version"] == 2
    assert "items" not in response
    assert [item["memory_id"] for item in response["memory"]] == ["m1", "m2", "m3"]
    assert [item["text"] for item in response["memory"]] == ["abcdefgh", "12345678", "tail"]
    assert response["matched_count"] == 3
    assert response["count"] == 3
    assert response["budget_chars"] == 20
    assert response["used_chars"] == 20
    assert response["truncated_item_count"] == 2
    assert response["truncated"] is True
    assert response["memory"][0]["text_chars"] == 11
    assert response["memory"][0]["returned_text_chars"] == 8
    assert response["memory"][0]["memory_get_required"] is True


def test_hard_envelope_omits_lower_ranked_metadata_and_reports_it():
    response = build_task_context_response(
        namespace="repo:coding-cli",
        task="x" * 300,
        items=_items() * 8,
        config=_config(task_context_response_max_chars=1_024),
    )

    encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
    pretty = json.dumps(response, ensure_ascii=False, indent=2)
    assert len(encoded) <= 1_024
    assert len(pretty) <= 1_024
    assert response["matched_count"] == 24
    assert response["count"] < response["matched_count"]
    assert response["omitted_count"] == response["matched_count"] - response["count"]
    assert response["truncated"] is True


def test_task_context_config_rejects_invalid_or_inverted_budgets(monkeypatch, tmp_path):
    monkeypatch.setenv("MNEMO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MNEMO_TASK_CONTEXT_MAX_TEXT_CHARS", "100")
    monkeypatch.setenv("MNEMO_TASK_CONTEXT_ITEM_PREVIEW_CHARS", "101")
    with pytest.raises(ValueError, match="preview"):
        Config()


class _Client:
    def __init__(self, payload):
        self.payload = payload

    def retrieve(self, **_kwargs):
        return [SimpleNamespace(payload=self.payload)]


def _engine(payload):
    engine = object.__new__(MemoryEngine)
    engine.cfg = SimpleNamespace(collection="test", agent_id="agent-A")
    engine.client = _Client(payload)
    return engine


def _payload(**overrides):
    payload = {
        "memory_id": MEMORY_ID,
        "namespace": "repo:coding-cli",
        "text": "authorized exact body",
        "type": "spec",
        "trust_class": "summarized",
        "sensitivity": "internal",
        "confidence": 0.8,
        "tags": [],
        "writer": "agent-A",
        "allowed_readers": ["agent-A"],
        "is_public": False,
        "timestamp": "2026-08-01T00:00:00Z",
        "source_event_id": "event-1",
        "expires_ts": time.time() + 60,
        "expires_at": None,
        "revoked": False,
    }
    payload.update(overrides)
    return payload


def test_memory_get_returns_full_authorized_record():
    item = _engine(_payload()).get(MEMORY_ID, reader="agent-A")
    assert item["text"] == "authorized exact body"


@pytest.mark.parametrize(
    "payload,reader",
    [
        (_payload(), "agent-B"),
        (_payload(revoked=True), "agent-A"),
        (_payload(expires_ts=time.time() - 1), "agent-A"),
        (_payload(revoked=0), "agent-A"),
        (_payload(is_public=1), "agent-A"),
        (_payload(allowed_readers="agent-A"), "agent-A"),
    ],
)
def test_memory_get_hides_unauthorized_revoked_and_expired(payload, reader):
    assert _engine(payload).get(MEMORY_ID, reader=reader) is None


def test_memory_get_allows_public_record_for_any_reader():
    item = _engine(_payload(is_public=True, allowed_readers=[])).get(
        MEMORY_ID, reader="agent-B"
    )
    assert item["memory_id"] == MEMORY_ID


def test_memory_get_without_reader_uses_configured_agent_acl():
    assert _engine(_payload(allowed_readers=["agent-B"])).get(MEMORY_ID) is None
    assert _engine(_payload()).get(MEMORY_ID)["memory_id"] == MEMORY_ID


def test_memory_get_rejects_invalid_identity_without_querying_backend():
    engine = _engine(_payload())
    engine.client.retrieve = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("backend must not be queried")
    )
    assert engine.get("not-a-memory-id", reader="agent-A") is None


def test_memory_forget_hides_unauthorized_identity_and_content():
    result = _engine(_payload()).forget(
        MEMORY_ID,
        reason="should not be visible",
        actor="agent-B",
    )
    assert result == {"ok": False, "error": "memory_not_found"}
