"""Refuse to optically compress payloads whose exact characters matter.

This is the mitigation for the one measured failure mode. In the feasibility
trials the aggressive density scored 99.4% character accuracy while corrupting
25% of the identifiers in the sample: a UUID lost one hex digit
(`3c197fdfa164` -> `3c197fdfe164`) and an access-key-shaped string was mangled.
A character-accuracy headline hides exactly the errors that matter most.

So the guard does not ask "is this readable". It asks "if a character flipped
here, would anyone notice". Content that would silently degrade is passed
through as text rather than rendered.

The guard never inspects a secret's value beyond classifying its shape, and it
never logs, stores, or returns the matched text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Patterns are shape classifiers, not validators. A false positive costs a
# missed compression opportunity; a false negative costs silent corruption.
# The asymmetry is deliberate and the thresholds are tuned toward refusing.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("uuid", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
    ("hash", re.compile(r"\b[0-9a-fA-F]{16,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA)"
                                  r"[0-9A-Z]{12,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
                       r"[A-Za-z0-9_-]{8,}\b")),
    ("bearer_token", re.compile(r"(?i)\b(?:bearer|authorization)\s*[:=]\s*\S{12,}")),
    ("secret_assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|"
        r"passwd|secret|token)\b\s*[:=]\s*['\"]?\S{8,}")),
    ("base64_blob", re.compile(r"\b[A-Za-z0-9+/]{60,}={0,2}\b")),
    ("git_sha", re.compile(r"\b[0-9a-f]{7,40}\b(?=\s|$|[),.;:])")),
)

# Above this share of identifier-ish characters, even a "clean" payload is
# treated as precision-critical: dense config, lockfiles, checksum manifests.
_DENSITY_CEILING = 0.18

_IDENTIFIER_TOKEN = re.compile(r"[A-Za-z0-9_./:+-]*\d[A-Za-z0-9_./:+-]*")


@dataclass(frozen=True)
class GuardVerdict:
    """Whether a payload may be rendered, and why not when it may not."""

    safe_for_auto: bool
    reasons: tuple[str, ...] = ()
    identifier_density: float = 0.0
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "safe_for_auto": self.safe_for_auto,
            "reasons": list(self.reasons),
            "identifier_density": round(self.identifier_density, 4),
            # Counts only. The matched text never leaves this module.
            "counts": dict(self.counts),
        }


def scan(text: str) -> GuardVerdict:
    """Classify a payload's tolerance for lossy optical rendering."""
    counts: dict[str, int] = {}
    reasons: list[str] = []

    for name, pattern in _PATTERNS:
        found = len(pattern.findall(text))
        if found:
            counts[name] = found
            reasons.append(name)

    density = identifier_density(text)
    if density > _DENSITY_CEILING:
        reasons.append("high_identifier_density")

    return GuardVerdict(
        safe_for_auto=not reasons,
        reasons=tuple(reasons),
        identifier_density=density,
        counts=counts,
    )


def identifier_density(text: str) -> float:
    """Share of characters sitting inside identifier-shaped tokens."""
    if not text:
        return 0.0
    covered = sum(len(match) for match in _IDENTIFIER_TOKEN.findall(text))
    return min(1.0, covered / len(text))


def max_safe_density(text: str) -> str:
    """The most aggressive density this payload tolerates.

    `aggressive` is only ever offered for payloads with no identifier signal at
    all, because that is the only regime where its measured 95.8% critical-token
    accuracy cannot bite.
    """
    verdict = scan(text)
    if not verdict.safe_for_auto:
        return "safe"
    if verdict.identifier_density < 0.02:
        return "aggressive"
    return "balanced"
