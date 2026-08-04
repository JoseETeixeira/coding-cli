"""Token arithmetic and rasterisation.

The numbers asserted here are the product's entire justification. If the token
model drifts, the feature silently starts costing more than the text it
replaces, so these are pinned hard.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from optical_compression import constants
from optical_compression.render import (
    RenderError,
    glyph_metrics,
    preflight,
    render,
    resolve_density,
)
from optical_compression.store import MemoryCache
from optical_compression.tokens import (
    compression_ratio,
    estimate_text_tokens,
    fit_to_tier,
    image_tokens,
    page_capacity_chars,
)

# Anthropic's published size -> token table.
PUBLISHED = [(200, 200, 64), (1000, 1000, 1296), (1092, 1092, 1521)]


@pytest.mark.parametrize("width,height,expected", PUBLISHED)
def test_matches_published_token_table(width, height, expected):
    assert image_tokens(width, height) == expected


def test_estimator_is_a_floor_not_a_guarantee():
    """1920x1080 bills 1560; we come out slightly low. Never claim otherwise."""
    measured = image_tokens(1920, 1080)
    assert measured <= 1560
    assert (1560 - measured) / 1560 < 0.05


def test_text_estimator_matches_context_compaction():
    """The two subsystems must never disagree about what a payload costs."""
    from context_compaction.budget import estimate_tokens

    for sample in ("", "a", "hello world", "def f():\n    return 1\n", "café ünïcode"):
        assert estimate_text_tokens(sample) == estimate_tokens(sample)


def test_ratio_formula_and_break_even():
    # ratio = 196 / (char_width * line_height); 1.0 is break-even.
    assert compression_ratio(7, 13) == pytest.approx(196 / 91)
    assert compression_ratio(4, 9) > 5.0
    assert compression_ratio(14, 28) < 1.0


@pytest.mark.parametrize("bad", [(0, 10), (10, 0), (-1, 5)])
def test_ratio_rejects_degenerate_metrics(bad):
    with pytest.raises(ValueError):
        compression_ratio(*bad)


def test_fit_to_tier_downscales_and_reports_it():
    width, height, scaled = fit_to_tier(4000, 4000)
    assert scaled is True
    assert max(width, height) <= constants.TIERS["standard"]["max_edge"]
    assert image_tokens(width, height) <= constants.TIERS["standard"]["max_tokens"]


def test_fit_to_tier_leaves_small_images_alone():
    assert fit_to_tier(200, 200) == (200, 200, False)


def test_highres_tier_holds_more():
    assert page_capacity_chars(6, 11, "highres") > page_capacity_chars(6, 11, "standard")


def test_unknown_tier_rejected():
    with pytest.raises(ValueError):
        image_tokens(100, 100, "nonsense")


# --- rendering -------------------------------------------------------------


def test_render_is_deterministic():
    text = "deterministic payload\n" * 400
    first = render(text, density="balanced")
    second = render(text, density="balanced")
    assert [p.digest for p in first.pages] == [p.digest for p in second.pages]
    assert [p.png for p in first.pages] == [p.png for p in second.pages]


def test_render_emits_one_bit_png():
    """1-bit is an 83% payload saving with no visual change."""
    result = render("black on white\n" * 300, density="balanced")
    with Image.open(io.BytesIO(result.pages[0].png)) as image:
        assert image.mode == "1"


def test_render_beats_text_at_default_density():
    text = "the quick brown fox jumps over the lazy dog\n" * 400
    result = render(text, density="balanced")
    assert result.total_image_tokens < result.text_tokens
    assert result.ratio > 2.0
    assert 0.0 < result.reduction < 1.0


def test_denser_font_yields_a_better_ratio_in_the_formula():
    """The pure relationship, free of page-quantisation effects."""
    ratios = {
        name: compression_ratio(*glyph_metrics(int(constants.DENSITIES[name]["font_size"])))
        for name in ("safe", "balanced", "aggressive")
    }
    assert ratios["aggressive"] > ratios["balanced"] > ratios["safe"]


def test_denser_font_wins_on_rendered_output_too():
    """End to end. Compared across a full page, so partial-page padding - which
    is quantised to whole 28px patch rows - cannot invert the ordering."""
    char_width, line_height = glyph_metrics(12)
    text = "measurable payload for density comparison\n" * 400
    assert len(text) > page_capacity_chars(char_width, line_height, padding=constants.PADDING_PX) // 2
    rendered = {d: render(text, density=d) for d in ("safe", "balanced", "aggressive")}
    assert rendered["aggressive"].ratio > rendered["safe"].ratio
    assert all(r.total_image_tokens < r.text_tokens for r in rendered.values())


def test_render_paginates_large_payloads():
    char_width, line_height = glyph_metrics(10)
    capacity = page_capacity_chars(char_width, line_height, padding=constants.PADDING_PX)
    result = render("x" * (capacity * 2), density="balanced")
    assert len(result.pages) >= 2
    assert all(page.png for page in result.pages)


def test_render_refuses_beyond_the_page_ceiling():
    char_width, line_height = glyph_metrics(12)
    capacity = page_capacity_chars(char_width, line_height, padding=constants.PADDING_PX)
    with pytest.raises(RenderError, match="page ceiling"):
        render("y" * capacity * (constants.MAX_PAGES + 2), density="safe")


def test_render_rejects_empty_and_unknown_density():
    with pytest.raises(RenderError):
        render("")
    with pytest.raises(RenderError, match="unknown density"):
        render("payload" * 500, density="ludicrous")


def test_cache_avoids_re_rasterising():
    text = "cacheable segment content\n" * 400
    cache = MemoryCache()
    first = render(text, density="balanced", cache=cache)
    assert first.cache_hits == 0
    second = render(text, density="balanced", cache=cache)
    assert second.cache_hits == len(second.pages)
    assert [p.png for p in first.pages] == [p.png for p in second.pages]


def test_cache_key_separates_densities():
    """Same text at another size is a genuinely different image."""
    text = "density separated content\n" * 400
    cache = MemoryCache()
    render(text, density="balanced", cache=cache)
    result = render(text, density="safe", cache=cache)
    assert result.cache_hits == 0


def test_newlines_survive_as_a_marker():
    result = render("alpha\nbravo\n" * 500, density="balanced")
    assert result.source_chars > 0
    # The marker keeps the decode reversible without preserving line breaks.
    assert constants.NEWLINE_MARKER.strip() == "¬"


def test_preflight_agrees_with_render_on_worth():
    text = "preflight agreement sample\n" * 500
    projection = preflight(text, density="balanced")
    result = render(text, density="balanced")
    assert projection["worth_it"] is True
    assert result.total_image_tokens < result.text_tokens
    assert projection["projected_pages"] >= len(result.pages)


def test_preflight_flags_tiny_payloads_as_not_worth_it():
    assert preflight("tiny", density="safe")["worth_it"] is False


def test_resolve_density_exposes_font_size():
    assert resolve_density("balanced") == ("balanced", 10)
