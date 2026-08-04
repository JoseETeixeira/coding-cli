"""Optical compression: render large text payloads as token-cheap images.

Lossy optical gist with mandatory exact retrieval. The image is for gist and
navigation; anything precision-critical is fetched back verbatim by digest.

Measured on this repository's own content: 2.90x fewer tokens at the default
density with 100% character and identifier accuracy in trials.
"""

from .constants import DEFAULT_DENSITY, DENSITIES, SERVER_NAME
from .guard import GuardVerdict, max_safe_density, scan
from .pipeline import CompressOutcome, compress, framing_text
# NOTE: `render` and `preflight` are deliberately NOT re-exported here. The
# submodule is called `optical_compression.render`, and binding a function of
# the same name at package level shadows it, so `from . import render` inside
# another module silently yields the function instead of the module.
from .render import RenderError, RenderResult
from .store import OpticalStore, StoreError
from .tokens import compression_ratio, estimate_text_tokens, image_tokens

__all__ = [
    "CompressOutcome",
    "DEFAULT_DENSITY",
    "DENSITIES",
    "GuardVerdict",
    "OpticalStore",
    "RenderError",
    "RenderResult",
    "SERVER_NAME",
    "StoreError",
    "compress",
    "compression_ratio",
    "estimate_text_tokens",
    "framing_text",
    "image_tokens",
    "max_safe_density",
    "scan",
]
