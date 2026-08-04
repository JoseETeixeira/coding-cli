"""Deterministic render lab for the agentic image-compression feasibility study.

Produces two experiment families:
  glyph  - legible monospace text rasterised at varying densities (Glyph-style
           visual-token compression). Model-side decode is plausible.
  cipher - letter-to-colour palette encoding, optionally two letters per pixel
           via channel packing. Model-side decode is the open question.

No network. No randomness. Same inputs always produce identical PNGs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import textwrap
from dataclasses import dataclass, asdict
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Claude vision bills whole 28x28-pixel patches: tokens = ceil(w/28) * ceil(h/28).
# Two tiers, each with a hard token ceiling that forces an aspect-preserving
# downscale when exceeded. Verified against Anthropic's published size->token
# table (1000x1000 -> 1296, 1092x1092 -> 1521, 1920x1080 -> 1560).
CLAUDE_PATCH = 28
CLAUDE_TIERS = {
    "standard": {"max_edge": 1568, "max_tokens": 1568},
    "highres": {"max_edge": 2576, "max_tokens": 4784},  # Claude 4.7+
}

MONO_FONT_CANDIDATES = (
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)


def estimate_text_tokens(text: str) -> int:
    """Match context_compaction.budget.estimate_tokens: ceil(ascii_run/4)."""
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


def fit_to_tier(width: int, height: int, tier: str = "standard") -> tuple[int, int, bool]:
    """Apply Anthropic's downscale rule; return (w, h, was_downscaled).

    A downscale is not free: it shrinks the rendered glyphs too, so effective
    font size drops and decode accuracy degrades. Callers should render inside
    the budget rather than relying on this.
    """
    limits = CLAUDE_TIERS[tier]
    max_edge, max_tokens = limits["max_edge"], limits["max_tokens"]
    scaled = False

    long_edge = max(width, height)
    if long_edge > max_edge:
        scale = max_edge / long_edge
        width, height = int(width * scale), int(height * scale)
        scaled = True

    while ceil(width / CLAUDE_PATCH) * ceil(height / CLAUDE_PATCH) > max_tokens:
        width, height = int(width * 0.98), int(height * 0.98)
        scaled = True
    return width, height, scaled


def image_tokens(width: int, height: int, tier: str = "standard") -> int:
    width, height, _ = fit_to_tier(width, height, tier)
    return ceil(width / CLAUDE_PATCH) * ceil(height / CLAUDE_PATCH)


def load_mono_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in MONO_FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    raise SystemExit("no monospace font found")


@dataclass(frozen=True)
class GlyphResult:
    name: str
    font_size: int
    width: int
    height: int
    chars: int
    lines: int
    cols: int
    text_tokens: int
    img_tokens: int
    ratio: float
    png_bytes: int
    sha256: str
    path: str


def render_glyph(
    text: str,
    out_path: Path,
    *,
    name: str,
    font_size: int,
    max_width: int = 1536,
    padding: int = 8,
    line_spacing: int = 0,
    tight: bool = True,
) -> GlyphResult:
    """Rasterise text as legible monospace.

    tight=True hard-wraps at the column count and shrinks the canvas to the
    content, so no token is spent on blank margin. Line structure is not
    preserved, which makes the ground truth unambiguous for decode scoring.
    """
    font = load_mono_font(font_size)
    # Monospace: measure one char to derive the column count.
    char_w = font.getlength("M")
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + line_spacing
    cols = max(1, int((max_width - 2 * padding) // char_w))

    if tight:
        # Hard-wrap the whole stream; newlines become a visible marker so the
        # decode is reversible without preserving physical line breaks.
        stream = text.replace("\n", " ¬ ")
        lines = [stream[i : i + cols] for i in range(0, len(stream), cols)] or [""]
    else:
        lines = []
        for raw_line in text.split("\n"):
            if not raw_line:
                lines.append("")
                continue
            lines.extend(
                textwrap.wrap(raw_line, width=cols, drop_whitespace=False) or [""]
            )

    longest = max((len(line) for line in lines), default=0)
    width = int(2 * padding + longest * char_w) if tight else max_width
    height = int(2 * padding + len(lines) * line_h)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((padding, padding + index * line_h), line, font=font, fill="black")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG", optimize=True)
    payload = out_path.read_bytes()

    text_tok = estimate_text_tokens(text)
    img_tok = image_tokens(width, height)
    return GlyphResult(
        name=name,
        font_size=font_size,
        width=width,
        height=height,
        chars=len(text),
        lines=len(lines),
        cols=cols,
        text_tokens=text_tok,
        img_tokens=img_tok,
        ratio=round(text_tok / img_tok, 3) if img_tok else 0.0,
        png_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest()[:16],
        path=str(out_path),
    )


# --- cipher family -----------------------------------------------------------

# 16-symbol alphabet mapped to maximally separated hues, 4 bits per symbol.
CIPHER_ALPHABET = "abcdefghijklmnop"
BASIC_COLORS = [
    (0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 255, 255),
    (128, 0, 0), (0, 128, 0), (0, 0, 128), (128, 128, 0),
    (128, 0, 128), (0, 128, 128), (128, 128, 128), (255, 128, 0),
]


def render_cipher(
    text: str,
    out_path: Path,
    *,
    name: str,
    cell: int = 16,
    cols: int = 32,
    pack_two: bool = False,
) -> dict:
    """Encode text as coloured cells. pack_two packs 2 symbols per cell via
    additive channel mixing (e.g. green + blue -> cyan), the user's proposal."""
    symbols = [c for c in text.lower() if c in CIPHER_ALPHABET]
    if pack_two:
        units = []
        for index in range(0, len(symbols) - 1, 2):
            first = BASIC_COLORS[CIPHER_ALPHABET.index(symbols[index])]
            second = BASIC_COLORS[CIPHER_ALPHABET.index(symbols[index + 1])]
            units.append(tuple(min(255, a + b) for a, b in zip(first, second)))
    else:
        units = [BASIC_COLORS[CIPHER_ALPHABET.index(s)] for s in symbols]

    rows = ceil(len(units) / cols) or 1
    width, height = cols * cell, rows * cell
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(units):
        x, y = (index % cols) * cell, (index // cols) * cell
        draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=color)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG", optimize=True)
    payload = out_path.read_bytes()
    ground_truth = "".join(symbols[: len(units) * (2 if pack_two else 1)])
    return {
        "name": name,
        "pack_two": pack_two,
        "width": width,
        "height": height,
        "cells": len(units),
        "symbols_encoded": len(ground_truth),
        "text_tokens": estimate_text_tokens(ground_truth),
        "img_tokens": image_tokens(width, height),
        "png_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()[:16],
        "path": str(out_path),
        "ground_truth": ground_truth,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()

    text = args.corpus.read_text(encoding="utf-8")
    outdir = args.outdir
    manifest: dict[str, object] = {
        "corpus_path": str(args.corpus),
        "corpus_chars": len(text),
        "corpus_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
        "corpus_text_tokens": estimate_text_tokens(text),
        "glyph": [],
        "cipher": [],
    }

    for font_size in (8, 10, 12, 14, 18):
        result = render_glyph(
            text,
            outdir / f"glyph_fs{font_size}.png",
            name=f"glyph_fs{font_size}",
            font_size=font_size,
        )
        manifest["glyph"].append(asdict(result))

    cipher_source = text[:512]
    manifest["cipher"].append(
        render_cipher(cipher_source, outdir / "cipher_1x.png", name="cipher_1x")
    )
    manifest["cipher"].append(
        render_cipher(
            cipher_source, outdir / "cipher_2x.png", name="cipher_2x", pack_two=True
        )
    )

    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2)[:4000])


if __name__ == "__main__":
    main()
