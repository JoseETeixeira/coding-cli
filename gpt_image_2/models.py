"""Validated request objects.

Everything locally knowable is checked here, and this module is reached before
`credentials` and before `api`. That ordering is the whole point: an invalid
request must cost nothing — no credential read, no HTTP round trip, no spend.

`GenerateRequest` and `EditRequest` are frozen and are only meant to be built
through the two `validate_*` functions, so a request object in hand is proof
that every rule below already passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import constants, errors, images

__all__ = [
    "GenerateRequest",
    "EditRequest",
    "validate_generate",
    "validate_edit",
    "parse_size",
]


@dataclass(frozen=True)
class _CommonRequest:
    prompt: str
    size: str
    quality: str
    output_format: str
    n: int
    background: str
    output_compression: int | None
    output_dir: Path
    basename: str

    @property
    def extension(self) -> str:
        return constants.EXTENSION_BY_FORMAT[self.output_format]

    @property
    def mime_type(self) -> str:
        return constants.MIME_BY_FORMAT[self.output_format]


@dataclass(frozen=True)
class GenerateRequest(_CommonRequest):
    #: Present on generate only. `POST /v1/images/edits` has no `moderation`
    #: parameter, so `EditRequest` deliberately does not carry one.
    moderation: str = constants.DEFAULT_MODERATION


@dataclass(frozen=True)
class EditRequest(_CommonRequest):
    references: tuple[images.LocalImage, ...] = field(default_factory=tuple)
    mask: images.LocalImage | None = None


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------


def _validate_prompt(prompt: str | None) -> str:
    if prompt is None or not isinstance(prompt, str) or not prompt.strip():
        raise errors.invalid_request("prompt must be a non-blank string.", field="prompt")
    if len(prompt) > constants.MAX_PROMPT_CHARS:
        raise errors.invalid_request(
            f"prompt is {len(prompt)} characters, above this tool's local limit of "
            f"{constants.MAX_PROMPT_CHARS}.",
            field="prompt",
        )
    return prompt


def _validate_choice(value: str | None, allowed: tuple[str, ...], default: str, field_name: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise errors.invalid_request(f"{field_name} must be a string.", field=field_name)
    normalised = value.strip().lower()
    if normalised not in allowed:
        raise errors.invalid_request(
            f"{field_name} must be one of {', '.join(allowed)}; got '{value}'.",
            field=field_name,
        )
    return normalised


def _validate_background(value: str | None) -> str:
    if value is None:
        return constants.DEFAULT_BACKGROUND
    normalised = str(value).strip().lower()
    if normalised in constants.UNSUPPORTED_BACKGROUNDS:
        # Requirements IMG-REQ-003: fail clearly rather than silently rewriting
        # this to `auto`, which would hand back an opaque image the caller
        # believes is transparent.
        raise errors.unsupported_option(
            f"background='{normalised}' is not supported by {constants.MODEL}. "
            f"Use 'auto' or 'opaque', then remove the background with an image "
            f"editor if you need transparency.",
            field="background",
        )
    return _validate_choice(
        normalised, constants.BACKGROUNDS, constants.DEFAULT_BACKGROUND, "background"
    )


def _validate_n(value: int | None) -> int:
    if value is None:
        return constants.DEFAULT_N
    if isinstance(value, bool) or not isinstance(value, int):
        raise errors.invalid_request("n must be an integer.", field="n")
    if not constants.MIN_N <= value <= constants.MAX_N:
        raise errors.invalid_request(
            f"n must be between {constants.MIN_N} and {constants.MAX_N} "
            f"(this tool's local range); got {value}.",
            field="n",
        )
    return value


def _validate_compression(value: int | None, output_format: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise errors.invalid_request(
            "output_compression must be an integer.", field="output_compression"
        )
    if output_format not in constants.COMPRESSIBLE_FORMATS:
        raise errors.invalid_request(
            f"output_compression applies only to "
            f"{' and '.join(constants.COMPRESSIBLE_FORMATS)} output; "
            f"output_format is '{output_format}'.",
            field="output_compression",
        )
    if not constants.MIN_COMPRESSION <= value <= constants.MAX_COMPRESSION:
        raise errors.invalid_request(
            f"output_compression must be between {constants.MIN_COMPRESSION} and "
            f"{constants.MAX_COMPRESSION}; got {value}.",
            field="output_compression",
        )
    return value


def parse_size(value: str | None) -> str:
    """Validate `auto` or an explicit WIDTHxHEIGHT against the documented rules.

    The SDK types `size` as a closed `Literal` that predates gpt-image-2's
    larger dimensions, so the SDK cannot do this for us. Every rule here is
    from the current image-generation guide.
    """
    if value is None:
        return constants.DEFAULT_SIZE

    if not isinstance(value, str):
        raise errors.invalid_request("size must be a string.", field="size")

    candidate = value.strip().lower()
    if candidate == constants.SIZE_AUTO:
        return constants.SIZE_AUTO

    parts = candidate.split("x")
    if len(parts) != 2:
        raise errors.invalid_request(
            f"size must be '{constants.SIZE_AUTO}' or 'WIDTHxHEIGHT'; got '{value}'.",
            field="size",
        )

    try:
        width, height = int(parts[0]), int(parts[1])
    except ValueError:
        raise errors.invalid_request(
            f"size dimensions must be integers; got '{value}'.", field="size"
        ) from None

    if width <= 0 or height <= 0:
        raise errors.invalid_request(
            "size dimensions must be positive.", field="size"
        )

    if width % constants.SIZE_EDGE_MULTIPLE or height % constants.SIZE_EDGE_MULTIPLE:
        raise errors.invalid_request(
            f"size edges must be multiples of {constants.SIZE_EDGE_MULTIPLE}px; "
            f"got {width}x{height}.",
            field="size",
        )

    if min(width, height) < constants.MIN_EDGE_PX:
        raise errors.invalid_request(
            f"size edges must be at least {constants.MIN_EDGE_PX}px; got {width}x{height}.",
            field="size",
        )

    if max(width, height) > constants.MAX_EDGE_PX:
        raise errors.invalid_request(
            f"size edges must be at most {constants.MAX_EDGE_PX}px; got {width}x{height}.",
            field="size",
        )

    if max(width, height) / min(width, height) > constants.MAX_ASPECT_RATIO:
        raise errors.invalid_request(
            f"size aspect ratio must not exceed "
            f"{constants.MAX_ASPECT_RATIO:g}:1; got {width}x{height}.",
            field="size",
        )

    total = width * height
    if total < constants.MIN_TOTAL_PIXELS:
        raise errors.invalid_request(
            f"size must be at least {constants.MIN_TOTAL_PIXELS:,} total pixels; "
            f"{width}x{height} is {total:,}.",
            field="size",
        )
    if total > constants.MAX_TOTAL_PIXELS:
        raise errors.invalid_request(
            f"size must be at most {constants.MAX_TOTAL_PIXELS:,} total pixels; "
            f"{width}x{height} is {total:,}.",
            field="size",
        )

    return f"{width}x{height}"


def _validate_common(
    *,
    prompt: str | None,
    size: str | None,
    quality: str | None,
    output_format: str | None,
    n: int | None,
    background: str | None,
    output_compression: int | None,
    output_dir: str | None,
    basename: str | None,
) -> dict[str, object]:
    """Run the shared checks in the fixed order the design specifies."""
    checked_prompt = _validate_prompt(prompt)
    checked_quality = _validate_choice(
        quality, constants.QUALITIES, constants.DEFAULT_QUALITY, "quality"
    )
    checked_format = _validate_choice(
        output_format,
        constants.OUTPUT_FORMATS,
        constants.DEFAULT_OUTPUT_FORMAT,
        "output_format",
    )
    checked_compression = _validate_compression(output_compression, checked_format)
    checked_background = _validate_background(background)
    checked_n = _validate_n(n)
    checked_size = parse_size(size)
    checked_dir = images.resolve_output_dir(output_dir)
    checked_basename = images.sanitize_basename(basename)

    return {
        "prompt": checked_prompt,
        "size": checked_size,
        "quality": checked_quality,
        "output_format": checked_format,
        "n": checked_n,
        "background": checked_background,
        "output_compression": checked_compression,
        "output_dir": checked_dir,
        "basename": checked_basename,
    }


def validate_generate(
    *,
    prompt: str | None,
    size: str | None = None,
    quality: str | None = None,
    output_format: str | None = None,
    n: int | None = None,
    output_compression: int | None = None,
    background: str | None = None,
    moderation: str | None = None,
    output_dir: str | None = None,
    basename: str | None = None,
) -> GenerateRequest:
    common = _validate_common(
        prompt=prompt,
        size=size,
        quality=quality,
        output_format=output_format,
        n=n,
        background=background,
        output_compression=output_compression,
        output_dir=output_dir,
        basename=basename,
    )
    checked_moderation = _validate_choice(
        moderation, constants.MODERATIONS, constants.DEFAULT_MODERATION, "moderation"
    )
    return GenerateRequest(moderation=checked_moderation, **common)  # type: ignore[arg-type]


def validate_edit(
    *,
    prompt: str | None,
    image_paths: list[str] | tuple[str, ...] | None,
    mask_path: str | None = None,
    size: str | None = None,
    quality: str | None = None,
    output_format: str | None = None,
    n: int | None = None,
    output_compression: int | None = None,
    background: str | None = None,
    output_dir: str | None = None,
    basename: str | None = None,
) -> EditRequest:
    common = _validate_common(
        prompt=prompt,
        size=size,
        quality=quality,
        output_format=output_format,
        n=n,
        background=background,
        output_compression=output_compression,
        output_dir=output_dir,
        basename=basename,
    )

    if image_paths is None or isinstance(image_paths, (str, bytes)):
        raise errors.invalid_request(
            "image_paths must be a list of local image file paths.",
            field="image_paths",
        )

    paths = list(image_paths)
    if not paths:
        raise errors.invalid_request(
            "image_paths must contain at least one local image file path.",
            field="image_paths",
        )
    if len(paths) > constants.MAX_EDIT_IMAGES:
        raise errors.invalid_request(
            f"image_paths accepts at most {constants.MAX_EDIT_IMAGES} references "
            f"(this tool's local limit); got {len(paths)}.",
            field="image_paths",
        )

    # Order is preserved: the first reference is the mask target and the API
    # treats the sequence as ordered context.
    references = tuple(
        images.inspect_local_image(str(item), field="image_paths") for item in paths
    )

    mask: images.LocalImage | None = None
    if mask_path is not None and str(mask_path).strip():
        mask = images.inspect_local_image(str(mask_path), field="mask_path")
        images.validate_mask(mask, references[0])

    return EditRequest(references=references, mask=mask, **common)  # type: ignore[arg-type]
