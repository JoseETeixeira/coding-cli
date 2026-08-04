"""Policy: decide whether to render, do it, and describe the result honestly.

Shared by the MCP tools and the Claude Code hook so both obey one set of rules.

The refusal paths matter more than the success path. Optical compression is
lossy, and three situations make it a bad trade:

- the payload is too small for the page padding to amortise (measured: a
  428-char sample scored 0.95x, i.e. worse than sending the text);
- the payload carries identifiers whose exact characters are load-bearing;
- the projected image tokens exceed the text tokens outright.

Each returns a decline with a reason rather than a degraded image.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import constants, guard, render as render_module
from .store import OpticalStore


@dataclass(frozen=True)
class CompressOutcome:
    accepted: bool
    reason: str
    digest: str | None = None
    result: render_module.RenderResult | None = None
    verdict: guard.GuardVerdict | None = None
    detail: dict | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "accepted": self.accepted,
            "reason": self.reason,
            "digest": self.digest,
        }
        if self.result is not None:
            payload.update(self.result.to_dict())
        if self.verdict is not None:
            payload["guard"] = self.verdict.to_dict()
        if self.detail:
            payload.update(self.detail)
        return payload


def compress(
    text: str,
    *,
    density: str = constants.DEFAULT_DENSITY,
    tier: str = constants.DEFAULT_TIER,
    store: OpticalStore | None = None,
    min_chars: int = constants.MIN_PAYLOAD_CHARS,
    enforce_guard: bool = False,
    source: str | None = None,
) -> CompressOutcome:
    """Render `text` if and only if doing so is a good trade.

    `enforce_guard` is the difference between a deliberate call and an automatic
    one. When an agent explicitly asks for compression it may render identifier
    content at a safe density having been warned; the hook, which compresses
    content nobody chose to compress, refuses outright.
    """
    if not text:
        return CompressOutcome(False, "empty_payload")

    if len(text) < min_chars:
        return CompressOutcome(
            False,
            "below_minimum",
            detail={
                "chars": len(text),
                "minimum_chars": min_chars,
                "explanation": (
                    "Too small to amortise page padding; rendering would cost "
                    "more tokens than the text it replaces."
                ),
            },
        )

    verdict = guard.scan(text)
    if enforce_guard and not verdict.safe_for_auto:
        return CompressOutcome(
            False,
            "guard_refused",
            verdict=verdict,
            detail={
                "explanation": (
                    "Payload contains identifier-shaped content whose exact "
                    "characters are load-bearing. Passing through as text."
                )
            },
        )

    if not verdict.safe_for_auto and density == "aggressive":
        density = "safe"

    projection = render_module.preflight(text, density=density, tier=tier)
    if not projection["worth_it"]:
        return CompressOutcome(
            False, "not_worth_it", verdict=verdict, detail=dict(projection)
        )

    store = store or OpticalStore()
    result = render_module.render(text, density=density, tier=tier, cache=store)
    digest = store.put_original(
        text, meta={"density": result.density, "source": source or "unspecified"}
    )

    if result.total_image_tokens >= result.text_tokens:
        # Projection said yes, reality said no. Decline rather than ship a
        # lossy result that also costs more.
        return CompressOutcome(
            False,
            "not_worth_it",
            digest=digest,
            result=result,
            verdict=verdict,
            detail={"explanation": "Rendered cost exceeded the text it replaces."},
        )

    return CompressOutcome(True, "ok", digest=digest, result=result, verdict=verdict)


def framing_text(outcome: CompressOutcome, *, source: str | None = None) -> str:
    """The text block that accompanies the rendered pages.

    This is load-bearing, not decoration. In runtime testing, models shown a
    substituted tool result spontaneously flagged it as fabricated or injected
    and said they would treat it as untrusted — even when a note explained the
    compression. So this block states plainly what transformed the content, that
    the transformation is lossy, and exactly how to get the exact bytes back.
    """
    if not outcome.accepted or outcome.result is None:
        return "Optical compression declined; original content is unchanged."

    result = outcome.result
    warned = ""
    if outcome.verdict is not None and not outcome.verdict.safe_for_auto:
        warned = (
            "\nCAUTION: this payload contains identifier-shaped content "
            f"({', '.join(outcome.verdict.reasons)}). Do not quote any hash, "
            "UUID, key, or numeric literal from the image — retrieve it."
        )

    origin = f" of {source}" if source else ""
    return (
        f"[optical-compression] The following {len(result.pages)} image(s) are a "
        f"lossy optical rendering{origin}, produced locally by the "
        f"optical-compression MCP server. This is a system-side transformation, "
        f"not model-generated content and not a summary. Every source character "
        f"was rendered, but the image is only for gist and navigation.\n"
        f"Original: {result.source_chars} chars, ~{result.text_tokens} text tokens. "
        f"Rendered: {result.total_image_tokens} image tokens at density "
        f"'{result.density}' ({result.ratio:.2f}x, {result.reduction:.1%} fewer tokens).\n"
        f"The exact original text is stored verbatim. Retrieve any span with "
        f"optical_retrieve(digest=\"{outcome.digest}\"). Retrieve before relying "
        f"on any exact value."
        f"{warned}"
    )
