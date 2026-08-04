"""Rasterise text into billed-token-efficient pages.

Two rules do most of the work:

1. **Pack tight.** The first draft of this renderer wrapped to a fixed 1536px
   canvas and left the right-hand side blank on short lines. That wasted 3.6x
   the token budget — a font size that should have compressed 1.56x measured
   0.44x, i.e. the image cost more than twice the text. The canvas is now sized
   to the content.
2. **Render 1-bit.** The page is pure black on white, so the RGB channels carry
   nothing. Re-encoding to a 1-bit palette measured 507 KB -> 85 KB, an 83%
   saving with zero visual change.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import constants
from .tokens import estimate_text_tokens, image_tokens, page_box


class RenderError(RuntimeError):
    """Raised when a payload cannot be rendered at all."""


@dataclass(frozen=True)
class Page:
    index: int
    png: bytes
    width: int
    height: int
    chars: int
    lines: int
    cols: int
    image_tokens: int
    digest: str


@dataclass(frozen=True)
class RenderResult:
    pages: tuple[Page, ...]
    density: str
    font_size: int
    source_chars: int
    text_tokens: int
    total_image_tokens: int
    cache_hits: int

    @property
    def ratio(self) -> float:
        if not self.total_image_tokens:
            return 0.0
        return self.text_tokens / self.total_image_tokens

    @property
    def reduction(self) -> float:
        if not self.text_tokens:
            return 0.0
        return 1.0 - (self.total_image_tokens / self.text_tokens)

    def to_dict(self) -> dict[str, object]:
        return {
            "density": self.density,
            "font_size": self.font_size,
            "pages": len(self.pages),
            "source_chars": self.source_chars,
            "text_tokens": self.text_tokens,
            "image_tokens": self.total_image_tokens,
            "ratio": round(self.ratio, 3),
            "reduction": round(self.reduction, 4),
            "cache_hits": self.cache_hits,
            "page_digests": [page.digest for page in self.pages],
        }


@lru_cache(maxsize=16)
def load_font(font_size: int) -> ImageFont.FreeTypeFont:
    for candidate in constants.MONO_FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, font_size)
            except OSError:  # pragma: no cover - unreadable font file
                continue
    raise RenderError(
        "no monospace font available; optical compression needs one of: "
        + ", ".join(constants.MONO_FONT_CANDIDATES)
    )


@lru_cache(maxsize=16)
def glyph_metrics(font_size: int) -> tuple[float, int]:
    """(char_width, line_height) for a monospace face at this size."""
    font = load_font(font_size)
    char_width = font.getlength("M")
    ascent, descent = font.getmetrics()
    if char_width <= 0:  # pragma: no cover - degenerate font
        raise RenderError("font reported a non-positive advance width")
    return char_width, ascent + descent


def resolve_density(density: str) -> tuple[str, int]:
    if density not in constants.DENSITIES:
        raise RenderError(
            f"unknown density {density!r}; expected one of "
            + ", ".join(sorted(constants.DENSITIES))
        )
    return density, int(constants.DENSITIES[density]["font_size"])


def render(
    text: str,
    *,
    density: str = constants.DEFAULT_DENSITY,
    tier: str = constants.DEFAULT_TIER,
    cache: "object | None" = None,
) -> RenderResult:
    """Render `text` into one or more pages at the given density."""
    if not text:
        raise RenderError("nothing to render")

    density, font_size = resolve_density(density)
    char_width, line_height = glyph_metrics(font_size)

    usable = page_box(tier) - 2 * constants.PADDING_PX
    cols = max(1, int(usable // char_width))
    rows = max(1, int(usable // line_height))
    per_page = cols * rows

    stream = text.replace("\n", constants.NEWLINE_MARKER)
    chunks = [stream[i : i + per_page] for i in range(0, len(stream), per_page)]
    if len(chunks) > constants.MAX_PAGES:
        raise RenderError(
            f"payload needs {len(chunks)} pages at density {density!r}, "
            f"over the {constants.MAX_PAGES}-page ceiling; split it or use a "
            "more aggressive density"
        )

    pages: list[Page] = []
    hits = 0
    for index, chunk in enumerate(chunks):
        digest = _digest(chunk, font_size)
        png: bytes | None = None
        if cache is not None:
            png = cache.get(digest)
            if png is not None:
                hits += 1
        if png is None:
            png = _rasterise(chunk, font_size, char_width, line_height, cols)
            if cache is not None:
                cache.put(digest, png)

        width, height = _dimensions(png)
        pages.append(
            Page(
                index=index,
                png=png,
                width=width,
                height=height,
                chars=len(chunk),
                lines=(len(chunk) + cols - 1) // cols,
                cols=cols,
                image_tokens=image_tokens(width, height, tier),
                digest=digest,
            )
        )

    total_bytes = sum(len(page.png) for page in pages)
    if total_bytes > constants.MAX_TOTAL_IMAGE_BYTES:
        raise RenderError(
            f"rendered payload is {total_bytes} bytes, over the "
            f"{constants.MAX_TOTAL_IMAGE_BYTES}-byte ceiling"
        )

    return RenderResult(
        pages=tuple(pages),
        density=density,
        font_size=font_size,
        source_chars=len(text),
        text_tokens=estimate_text_tokens(text),
        total_image_tokens=sum(page.image_tokens for page in pages),
        cache_hits=hits,
    )


def preflight(
    text: str, *, density: str = constants.DEFAULT_DENSITY, tier: str = constants.DEFAULT_TIER
) -> dict[str, object]:
    """Predict the outcome without rasterising anything.

    Lets a caller decide whether rendering is worth it before paying for it.
    """
    density, font_size = resolve_density(density)
    char_width, line_height = glyph_metrics(font_size)
    side = page_box(tier)
    usable = side - 2 * constants.PADDING_PX
    per_page = max(1, int(usable // char_width)) * max(1, int(usable // line_height))

    stream_len = len(text) + text.count("\n") * (len(constants.NEWLINE_MARKER) - 1)
    pages = max(1, (stream_len + per_page - 1) // per_page)
    text_tokens = estimate_text_tokens(text)
    # Full pages cost a full box; a single partial page costs only what it fills.
    projected = pages * image_tokens(side, side, tier)
    if pages == 1:
        lines = max(1, -(-stream_len // max(1, int(usable // char_width))))
        height = int(2 * constants.PADDING_PX + lines * line_height)
        projected = image_tokens(side, min(side, height), tier)

    return {
        "density": density,
        "font_size": font_size,
        "projected_pages": pages,
        "text_tokens": text_tokens,
        "projected_image_tokens": projected,
        "projected_ratio": round(text_tokens / projected, 3) if projected else 0.0,
        "worth_it": text_tokens > projected,
    }


def _rasterise(
    chunk: str, font_size: int, char_width: float, line_height: int, cols: int
) -> bytes:
    font = load_font(font_size)
    lines = [chunk[i : i + cols] for i in range(0, len(chunk), cols)] or [""]
    longest = max((len(line) for line in lines), default=0)

    width = max(1, int(2 * constants.PADDING_PX + longest * char_width))
    height = max(1, int(2 * constants.PADDING_PX + len(lines) * line_height))

    canvas = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        draw.text(
            (constants.PADDING_PX, constants.PADDING_PX + index * line_height),
            line,
            font=font,
            fill=0,
        )

    # 1-bit: the render is pure black on white, so the extra channels and levels
    # are pure payload with no information in them.
    buffer = io.BytesIO()
    canvas.convert(constants.RENDER_MODE).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _dimensions(png: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(png)) as image:
        return image.size


def _digest(chunk: str, font_size: int) -> str:
    """Cache key: content plus the glyph size it was rendered at.

    Font size is part of the key because the same text at a different density is
    a genuinely different image. Nothing time-varying is included, so the key is
    stable across runs and across machines.
    """
    payload = f"{font_size}\x00{chunk}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[: constants.DIGEST_CHARS]
