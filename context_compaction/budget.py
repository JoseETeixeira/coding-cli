"""Deterministic context budgeting with no tokenizer or network dependency."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

DEFAULT_REENTRY_CHARS = 8_000
DEFAULT_REENTRY_TOKENS = 2_000
DEFAULT_MEMORY_TEXT_CHARS = 4_000
DEFAULT_MEMORY_ITEM_CHARS = 500
DEFAULT_MEMORY_ENVELOPE_CHARS = 8_000

_FORBIDDEN_CATEGORY_PARTS = (
    "secret",
    "credential",
    "token_value",
    "raw_tool",
    "tool_output",
    "transcript",
    "compact_summary",
    "source_body",
    "full_source",
    "full_diff",
    "binary",
)


def estimate_tokens(text: str) -> int:
    """Estimate conservatively: each ASCII run costs ceil(chars/4), non-ASCII 1."""

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


def fits_budget(text: str, *, max_chars: int, max_tokens: int) -> bool:
    _validate_limits(max_chars, max_tokens)
    return len(text) <= max_chars and estimate_tokens(text) <= max_tokens


def truncate_text(text: str, *, max_chars: int, max_tokens: int) -> str:
    """Return the longest Unicode prefix fitting both deterministic limits."""

    _validate_limits(max_chars, max_tokens, allow_zero=True)
    if not text or max_chars == 0 or max_tokens == 0:
        return ""
    if fits_budget(text, max_chars=max_chars, max_tokens=max_tokens):
        return text

    low = 0
    high = min(len(text), max_chars)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = text[:middle]
        if estimate_tokens(candidate) <= max_tokens:
            low = middle
        else:
            high = middle - 1
    return text[:low]


@dataclass(frozen=True)
class BudgetCategory:
    """One model-visible category, ordered by priority then declaration order."""

    name: str
    text: str
    priority: int
    required: bool = False

    def __post_init__(self) -> None:
        normalized = self.name.strip().lower()
        if not normalized or normalized != self.name or len(normalized) > 64:
            raise ValueError("invalid budget category name")
        if any(part in normalized for part in _FORBIDDEN_CATEGORY_PARTS):
            raise ValueError(f"forbidden budget category: {self.name}")
        if not isinstance(self.text, str):
            raise TypeError("budget category text must be a string")
        if self.priority < 0:
            raise ValueError("budget category priority must be non-negative")


@dataclass(frozen=True)
class BudgetResult:
    text: str
    used_chars: int
    estimated_tokens: int
    included_categories: tuple[str, ...]
    omitted_categories: tuple[str, ...]
    truncated: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "used_chars": self.used_chars,
            "estimated_tokens": self.estimated_tokens,
            "included_categories": list(self.included_categories),
            "omitted_categories": list(self.omitted_categories),
            "truncated": self.truncated,
        }


def allocate_categories(
    categories: Iterable[BudgetCategory],
    *,
    max_chars: int = DEFAULT_REENTRY_CHARS,
    max_tokens: int = DEFAULT_REENTRY_TOKENS,
    separator: str = "\n",
) -> BudgetResult:
    """Allocate whole optional categories and bounded prefixes of required ones."""

    _validate_limits(max_chars, max_tokens)
    indexed = list(enumerate(categories))
    indexed.sort(key=lambda item: (item[1].priority, item[0]))

    parts: list[str] = []
    included: list[str] = []
    omitted: list[str] = []
    was_truncated = False

    for _, category in indexed:
        prefix = separator if parts else ""
        candidate = prefix + category.text
        current = "".join(parts)
        combined = current + candidate
        if fits_budget(combined, max_chars=max_chars, max_tokens=max_tokens):
            parts.append(candidate)
            included.append(category.name)
            continue

        was_truncated = True
        if not category.required:
            omitted.append(category.name)
            continue

        remaining_chars = max_chars - len(current) - len(prefix)
        remaining_tokens = max_tokens - estimate_tokens(current + prefix)
        bounded = truncate_text(
            category.text,
            max_chars=max(0, remaining_chars),
            max_tokens=max(0, remaining_tokens),
        )
        if bounded:
            parts.append(prefix + bounded)
            included.append(category.name)
        else:
            omitted.append(category.name)

    text = "".join(parts)
    return BudgetResult(
        text=text,
        used_chars=len(text),
        estimated_tokens=estimate_tokens(text),
        included_categories=tuple(included),
        omitted_categories=tuple(omitted),
        truncated=was_truncated,
    )


def _validate_limits(max_chars: int, max_tokens: int, *, allow_zero: bool = False) -> None:
    minimum = 0 if allow_zero else 1
    if not isinstance(max_chars, int) or not isinstance(max_tokens, int):
        raise TypeError("budget limits must be integers")
    if max_chars < minimum or max_tokens < minimum:
        raise ValueError("budget limits must be positive")
