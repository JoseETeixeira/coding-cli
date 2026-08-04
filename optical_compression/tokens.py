"""Token arithmetic for text and for rendered images.

Deterministic and offline: no tokenizer, no network. The text estimator matches
`context_compaction.budget.estimate_tokens` so the two subsystems never disagree
about what a payload costs.
"""

from __future__ import annotations

from math import ceil

from .constants import CLAUDE_PATCH, DEFAULT_TIER, TIERS


def estimate_text_tokens(text: str) -> int:
    """Estimate conservatively: each ASCII run costs ceil(chars/4), non-ASCII 1.

    Identical to `context_compaction.budget.estimate_tokens`. Duplicated rather
    than imported so this package stays independently installable, and pinned by
    a test that asserts the two agree.
    """
    tokens = 0
    ascii_run = 0
    for char in text:
        if ord(char) < 128:
            ascii_run += 1
            continue
        if ascii_run:
            tokens += ceil(ascii_run / 4)
            ascii_run = 0
        tokens += 1
    if ascii_run:
        tokens += ceil(ascii_run / 4)
    return tokens


def fit_to_tier(
    width: int, height: int, tier: str = DEFAULT_TIER
) -> tuple[int, int, bool]:
    """Apply the vendor downscale rule; return (width, height, was_downscaled).

    A downscale is never free: it shrinks the rendered glyphs too, so effective
    font size drops and decode accuracy degrades with it. Callers should render
    inside the budget rather than relying on this to rescue an oversized page.
    """
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier}")
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")

    limits = TIERS[tier]
    max_edge, max_tokens = limits["max_edge"], limits["max_tokens"]
    scaled = False

    long_edge = max(width, height)
    if long_edge > max_edge:
        factor = max_edge / long_edge
        width = max(1, int(width * factor))
        height = max(1, int(height * factor))
        scaled = True

    # Anthropic searches for the largest aspect-preserving size inside the token
    # ceiling. Stepping down is close enough for a budget guard and never
    # over-reports the fit.
    while _patches(width, height) > max_tokens and min(width, height) > 1:
        width = max(1, int(width * 0.98))
        height = max(1, int(height * 0.98))
        scaled = True

    return width, height, scaled


def image_tokens(width: int, height: int, tier: str = DEFAULT_TIER) -> int:
    """Billed visual tokens for an image of this size.

    This is a FLOOR, not a guarantee. Validated exactly on three published
    reference sizes; on 1920x1080 it comes out ~3% low because the real
    downscale search is finer than the step-down above. Treat budgets built on
    it as lower bounds and leave headroom.
    """
    width, height, _ = fit_to_tier(width, height, tier)
    return _patches(width, height)


def page_box(tier: str = DEFAULT_TIER) -> int:
    """Largest square page side that fits the token budget WITHOUT a downscale.

    This is deliberately smaller than the tier's edge limit. Rendering to the
    full 1568px edge would cost ceil(1568/28)^2 = 3136 patches against a 1568
    ceiling, so the vendor would halve the image — shrinking the glyphs with it
    and degrading decode accuracy exactly where it is already tightest. Sizing
    to the budget instead keeps every rendered page at its intended font size.
    """
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier}")
    limits = TIERS[tier]
    patches_per_side = int(limits["max_tokens"] ** 0.5)
    return min(limits["max_edge"], patches_per_side * CLAUDE_PATCH)


def page_capacity_chars(
    char_width: float, line_height: int, tier: str = DEFAULT_TIER, padding: int = 0
) -> int:
    """How many characters fit on one full page at this glyph size."""
    if char_width <= 0 or line_height <= 0:
        raise ValueError("glyph metrics must be positive")
    usable = page_box(tier) - 2 * padding
    if usable <= 0:
        return 0
    return max(0, int(usable // char_width) * int(usable // line_height))


def compression_ratio(char_width: float, line_height: int) -> float:
    """Text tokens saved per image token: 196 / (char_width * line_height).

    Falls out of 0.25 text tokens per character against one visual token per
    28x28 = 784 pixels. Break-even is 1.0; below that the image costs more than
    the text it replaces.
    """
    if char_width <= 0 or line_height <= 0:
        raise ValueError("glyph metrics must be positive")
    return 196.0 / (char_width * line_height)


def _patches(width: int, height: int) -> int:
    return ceil(width / CLAUDE_PATCH) * ceil(height / CLAUDE_PATCH)
