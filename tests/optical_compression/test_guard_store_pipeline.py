"""Safety, persistence, and policy.

The guard and the store together are what make a lossy transform acceptable:
the guard keeps precision-critical content out of the renderer, and the store
guarantees the exact bytes are always recoverable.
"""

from __future__ import annotations

import json

import pytest

from optical_compression import constants, guard, pipeline
from optical_compression.store import MemoryCache, OpticalStore, StoreError, validate_digest

BULK = "harmless narrative filler for padding the payload to a usable size. "


def _payload(body: str = "", size: int = constants.MIN_PAYLOAD_CHARS + 2_000) -> str:
    return (body + BULK * ((size // len(BULK)) + 1))[:size]


# --- guard -----------------------------------------------------------------


@pytest.mark.parametrize(
    "sample,reason",
    [
        ("memory_id=25980152-3285-42c6-8305-3c197fdfa164", "uuid"),
        ("sha256=30b7e9ba6b5b7642c92af44eddf7b4f6", "hash"),
        ("token=AKIAI44QH8DHBEXAMPLE", "aws_access_key"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private_key"),
        ('api_key: "s0mesecretvalue"', "secret_assignment"),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVP", "jwt"),
    ],
)
def test_guard_refuses_precision_critical_shapes(sample, reason):
    verdict = guard.scan(sample)
    assert verdict.safe_for_auto is False
    assert reason in verdict.reasons


@pytest.mark.parametrize(
    "sample",
    [
        "The conversation is a disposable hot cache, not a source of truth.",
        "starting the build and waiting for the compiler to finish",
        "we reviewed the proposal and agreed to postpone the migration",
    ],
)
def test_guard_allows_ordinary_prose(sample):
    assert guard.scan(sample).safe_for_auto is True


def test_guard_never_leaks_matched_text():
    """Counts and category names only - never the secret itself."""
    secret = "AKIAI44QH8DHBEXAMPLE"
    payload = json.dumps(guard.scan(f"token={secret}").to_dict())
    assert secret not in payload
    assert "aws_access_key" in payload


def test_max_safe_density_downgrades_risky_content():
    assert guard.max_safe_density("sha256=30b7e9ba6b5b7642c92af44eddf7b4f6") == "safe"
    assert guard.max_safe_density("plain english sentences with no identifiers") == "aggressive"


def test_identifier_density_is_bounded():
    assert 0.0 <= guard.identifier_density("") <= 1.0
    assert guard.identifier_density("abc123 def456 ghi789") > 0.5


# --- store -----------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["../escape", "a/b", "a\\b", "..", "", "NOTHEX!", "x" * 65, "a\x00b", "abc def"],
)
def test_digest_validation_blocks_traversal(bad):
    with pytest.raises(StoreError):
        validate_digest(bad)


def test_digest_validation_normalises_case():
    assert validate_digest("  ABCDEF01  ") == "abcdef01"


def test_store_roundtrip_is_exact(tmp_path):
    store = OpticalStore(tmp_path)
    text = "exact bytes: sha256=30b7e9ba ünïcode ¬ tabs\there\n" * 50
    digest = store.put_original(text)
    assert store.get_original(digest).text == text


def test_store_rejects_content_that_no_longer_matches_its_digest(tmp_path):
    store = OpticalStore(tmp_path)
    original = "authoritative source text"
    digest = store.put_original(original)
    target = store.originals_dir / f"{digest}.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["text"] = "tampered source text"
    payload["chars"] = len(payload["text"])
    target.write_text(json.dumps(payload), encoding="utf-8")

    assert store.get_original(digest) is None
    assert store.slice_original(digest) is None

    # A subsequent write of the authoritative content repairs the invalid
    # cache entry instead of returning a digest that cannot be retrieved.
    assert store.put_original(original) == digest
    assert store.get_original(digest).text == original


def test_store_put_is_idempotent(tmp_path):
    store = OpticalStore(tmp_path)
    assert store.put_original("same content") == store.put_original("same content")
    assert store.stats()["originals"] == 1


def test_store_slice_returns_exact_span(tmp_path):
    store = OpticalStore(tmp_path)
    digest = store.put_original("0123456789abcdef")
    assert store.slice_original(digest, start=4, length=6) == "456789"
    assert store.slice_original(digest, start=10) == "abcdef"


def test_store_slice_rejects_negative_start(tmp_path):
    store = OpticalStore(tmp_path)
    digest = store.put_original("payload")
    with pytest.raises(StoreError):
        store.slice_original(digest, start=-1)


def test_store_slice_rejects_negative_length(tmp_path):
    store = OpticalStore(tmp_path)
    digest = store.put_original("payload")
    with pytest.raises(StoreError):
        store.slice_original(digest, length=-1)


def test_store_misses_are_none_not_errors(tmp_path):
    store = OpticalStore(tmp_path)
    assert store.get_original("abcdef0123456789") is None
    assert store.get("abcdef0123456789") is None
    assert store.get("../../etc/passwd") is None


def test_segment_cache_roundtrip(tmp_path):
    store = OpticalStore(tmp_path)
    store.put("abc123def456", b"\x89PNG-ish")
    assert store.get("abc123def456") == b"\x89PNG-ish"


def test_prune_respects_retention(tmp_path):
    store = OpticalStore(tmp_path)
    store.put_original("keep me around")
    assert store.prune(older_than_days=30)["originals"] == 0
    assert store.prune(older_than_days=0)["originals"] == 1


def test_prune_rejects_negative_retention(tmp_path):
    with pytest.raises(StoreError):
        OpticalStore(tmp_path).prune(older_than_days=-1)


# --- pipeline --------------------------------------------------------------


def test_pipeline_declines_small_payloads(tmp_path):
    outcome = pipeline.compress("too small", store=OpticalStore(tmp_path))
    assert outcome.accepted is False
    assert outcome.reason == "below_minimum"


def test_pipeline_declines_empty(tmp_path):
    assert pipeline.compress("", store=OpticalStore(tmp_path)).reason == "empty_payload"


def test_pipeline_accepts_a_large_clean_payload(tmp_path):
    outcome = pipeline.compress(_payload(), store=OpticalStore(tmp_path))
    assert outcome.accepted is True
    assert outcome.result.total_image_tokens < outcome.result.text_tokens
    assert outcome.digest


def test_pipeline_stores_the_exact_original(tmp_path):
    store = OpticalStore(tmp_path)
    text = _payload("sentinel-value-9f3a ")
    outcome = pipeline.compress(text, store=store)
    assert store.get_original(outcome.digest).text == text


def test_enforcing_guard_refuses_identifier_payloads(tmp_path):
    text = _payload("sha256=30b7e9ba6b5b7642c92af44eddf7b4f6 ")
    outcome = pipeline.compress(text, store=OpticalStore(tmp_path), enforce_guard=True)
    assert outcome.accepted is False
    assert outcome.reason == "guard_refused"


def test_deliberate_call_may_render_identifiers_but_downgrades_density(tmp_path):
    """An explicit request is allowed; aggressive density is not."""
    text = _payload("sha256=30b7e9ba6b5b7642c92af44eddf7b4f6 ")
    outcome = pipeline.compress(
        text, store=OpticalStore(tmp_path), density="aggressive", enforce_guard=False
    )
    assert outcome.accepted is True
    assert outcome.result.density == "safe"


def test_framing_text_names_the_transform_and_the_escape_hatch(tmp_path):
    outcome = pipeline.compress(_payload(), store=OpticalStore(tmp_path), source="big.log")
    framing = pipeline.framing_text(outcome, source="big.log")
    assert "optical-compression" in framing
    assert "lossy optical rendering" in framing
    assert "only for gist and navigation" in framing
    assert "system-side transformation" in framing
    assert "not model-generated" in framing
    assert f'optical_retrieve(digest="{outcome.digest}")' in framing
    assert "big.log" in framing


def test_framing_warns_when_identifiers_are_present(tmp_path):
    text = _payload("sha256=30b7e9ba6b5b7642c92af44eddf7b4f6 ")
    outcome = pipeline.compress(text, store=OpticalStore(tmp_path))
    assert "CAUTION" in pipeline.framing_text(outcome)


def test_declined_framing_says_nothing_changed(tmp_path):
    outcome = pipeline.compress("tiny", store=OpticalStore(tmp_path))
    assert "declined" in pipeline.framing_text(outcome)


def test_outcome_serialises_without_the_source_text(tmp_path):
    text = _payload("sentinel-do-not-leak ")
    payload = json.dumps(pipeline.compress(text, store=OpticalStore(tmp_path)).to_dict())
    assert "sentinel-do-not-leak" not in payload


def test_pipeline_uses_the_segment_cache(tmp_path):
    cache = MemoryCache()
    text = _payload()
    pipeline.compress(text, store=OpticalStore(tmp_path))
    from optical_compression.render import render

    render(text, density="balanced", cache=cache)
    assert render(text, density="balanced", cache=cache).cache_hits > 0


def test_prune_zero_days_removes_just_written_entries(tmp_path):
    """Regression: a cutoff of `now` raced filesystem timestamp granularity and
    left just-written entries behind non-deterministically."""
    store = OpticalStore(tmp_path)
    for index in range(5):
        store.put_original(f"entry number {index}")
    assert store.stats()["originals"] == 5
    assert store.prune(older_than_days=0)["originals"] == 5
    assert store.stats()["originals"] == 0


def test_explicit_store_root_beats_the_environment(tmp_path, monkeypatch):
    """Explicit > ambient. The reverse silently redirected a caller's writes."""
    monkeypatch.setenv("OPTICAL_COMPRESSION_DIR", str(tmp_path / "ambient"))
    store = OpticalStore(tmp_path / "explicit")
    digest = store.put_original("routed by the explicit root")
    assert (tmp_path / "explicit").exists()
    assert not (tmp_path / "ambient").exists()
    assert store.get_original(digest).text == "routed by the explicit root"


def test_ambient_store_root_applies_when_no_root_is_given(tmp_path, monkeypatch):
    monkeypatch.setenv("OPTICAL_COMPRESSION_DIR", str(tmp_path / "ambient"))
    OpticalStore().put_original("routed by the environment")
    assert (tmp_path / "ambient").exists()
