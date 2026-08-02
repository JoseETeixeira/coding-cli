"""Local image inspection, response decoding, and no-overwrite publication.

This module owns every filesystem and pixel rule. It imports neither `mcp` nor
`openai`, which is what lets the whole output contract be tested with a temp
directory and no network.

The publication primitive is the security-relevant part. `os.replace` is
atomic but *overwrites*, and a plain existence check followed by a write is a
race. `os.link` is atomic and fails with `FileExistsError` instead of
clobbering, so it is both at once — and an `O_EXCL` create is the fallback for
filesystems that refuse hard links.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from PIL import UnidentifiedImageError

from . import constants, errors

__all__ = [
    "LocalImage",
    "DecodedImage",
    "inspect_local_image",
    "validate_mask",
    "sanitize_basename",
    "resolve_output_dir",
    "decode_image_payload",
    "publish_atomic",
]

# Decompression-bomb defence is two-layer, and both layers matter.
#
# 1. `constants.MAX_DECODE_PIXELS` is checked in `_describe` against the
#    header's DECLARED dimensions, before `load()` decodes anything.
# 2. Pillow's own guard, left exactly as it ships. It fires earlier still —
#    inside `Image.open()` — and it raises `DecompressionBombError`, which
#    derives from plain `Exception`. Layer 1 never sees those, which is why
#    both `inspect_local_image` and `decode_image_payload` catch broadly:
#    nothing a caller or the provider sends may escape the closed taxonomy.


@dataclass(frozen=True)
class LocalImage:
    """A local file that has been proven to be a supported, decodable image."""

    path: Path
    format: str
    width: int
    height: int
    size_bytes: int
    has_alpha: bool
    alpha_extrema: tuple[int, int] | None


@dataclass(frozen=True)
class DecodedImage:
    """Bytes from the API that have been proven to be the requested format."""

    data: bytes
    format: str
    width: int
    height: int

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def _describe(image_bytes: bytes) -> tuple[str, int, int, bool, tuple[int, int] | None]:
    """Decode once and report format, dimensions, and alpha facts.

    `load()` performs the full decode, so a truncated or corrupt file raises
    here rather than surviving to be written or uploaded. Doing this once and
    returning everything satisfies the "do not decode an input twice" NFR.
    """
    with PILImage.open(BytesIO(image_bytes)) as img:
        pillow_format = (img.format or "").upper()

        # Check the declared dimensions from the header BEFORE `load()` decodes
        # anything. A 68-byte PNG can declare 60000x60000 and force a
        # multi-hundred-megabyte allocation per reference — during
        # pre-credential validation, where an attacker-supplied file is cheapest
        # to send. Pillow's own bomb guard raises DecompressionBombError, which
        # derives from plain Exception and would escape the closed taxonomy, so
        # this check owns the outcome instead.
        declared_w, declared_h = img.size
        if declared_w * declared_h > constants.MAX_DECODE_PIXELS:
            raise errors.invalid_input_file(
                f"Image declares {declared_w}x{declared_h} "
                f"({declared_w * declared_h:,} pixels), above this tool's local "
                f"decode limit of {constants.MAX_DECODE_PIXELS:,} pixels."
            )

        img.load()
        width, height = img.size
        bands = img.getbands()
        has_alpha = "A" in bands
        extrema: tuple[int, int] | None = None
        if has_alpha:
            channel_extrema = img.getchannel("A").getextrema()
            # getextrema() returns a 2-tuple for a single-band image.
            extrema = (int(channel_extrema[0]), int(channel_extrema[1]))

    known = constants.FORMAT_BY_PILLOW_NAME.get(pillow_format)
    if known is None:
        raise errors.invalid_input_file(
            f"Unsupported image format {pillow_format or 'unknown'!s}. Supported "
            f"formats are {', '.join(constants.EDIT_INPUT_FORMATS)}."
        )
    return known, width, height, has_alpha, extrema


_URL_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def _reject_remote(candidate: str, *, field: str) -> None:
    """Refuse anything that names a remote resource, before touching the disk.

    Requirements IMG-REQ-004: this tool never fetches remote resources. Two
    shapes have to be caught here rather than left to the filesystem:

    * A URL (`https://...`, `ftp://...`, `data:`). Left alone these merely fail
      as "no such file", which works but says the wrong thing.
    * A **UNC path** (`\\\\server\\share`, or `//server/share`). This one matters
      for more than tidiness: `Path.resolve()` on a UNC path makes Windows
      perform a real DNS/SMB lookup, which blocks for seconds against a host
      that does not exist. That is caller-controlled network I/O inside a paid
      operation's deadline, so it is refused up front.
    """
    if _URL_SCHEME.match(candidate) or candidate.lower().startswith("data:"):
        raise errors.invalid_input_file(
            "Remote URLs are not accepted; provide a path to a local image file.",
            path=candidate[:80],
        )
    normalised = candidate.replace("\\", "/")
    if normalised.startswith("//"):
        raise errors.invalid_input_file(
            "Network (UNC) paths are not accepted; provide a path to a local "
            "image file.",
            path=candidate[:80],
        )


def inspect_local_image(raw_path: str, *, field: str = "image_paths") -> LocalImage:
    """Prove a caller-supplied path is a local, supported, decodable image.

    Ordering is deliberate: existence, then regular-file, then size, and only
    then a decode. A 4 GB file or a named pipe is rejected before anything
    tries to read it into memory.
    """
    if not isinstance(raw_path, str):
        raise errors.invalid_request(
            f"An image path must be a string; got {type(raw_path).__name__}.",
            field=field,
        )
    if not raw_path.strip():
        raise errors.invalid_request("An image path must not be blank.", field=field)

    _reject_remote(raw_path.strip(), field=field)

    path = Path(raw_path).expanduser()

    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise errors.invalid_input_file(
            "No such file. Provide a path to a local image file.", path=str(path)
        ) from None

    if not resolved.is_file():
        raise errors.invalid_input_file(
            "Not a regular file. Directories, devices, and pipes are not accepted.",
            path=str(resolved),
        )

    size_bytes = resolved.stat().st_size
    if size_bytes == 0:
        raise errors.invalid_input_file("File is empty.", path=str(resolved))
    if size_bytes >= constants.MAX_EDIT_FILE_BYTES:
        raise errors.invalid_input_file(
            f"File is {size_bytes} bytes, at or above this tool's local "
            f"{constants.MAX_EDIT_FILE_BYTES}-byte limit for edit inputs.",
            path=str(resolved),
        )

    try:
        payload = resolved.read_bytes()
    except OSError:
        raise errors.invalid_input_file(
            "File could not be read.", path=str(resolved)
        ) from None

    try:
        fmt, width, height, has_alpha, extrema = _describe(payload)
    except errors.ImageToolError as exc:
        raise errors.invalid_input_file(exc.message, path=str(resolved)) from None
    except Exception:
        # Deliberately broad. PIL raises a wide and version-dependent family
        # here — UnidentifiedImageError, OSError, ValueError, SyntaxError, and
        # DecompressionBombError, which derives from plain Exception. A caller's
        # file must never be able to escape the closed taxonomy and surface as
        # `internal_error` with a traceback.
        raise errors.invalid_input_file(
            "File is not a readable image, or is truncated, corrupt, or "
            "unsupported.",
            path=str(resolved),
        ) from None

    if fmt not in constants.EDIT_INPUT_FORMATS:
        raise errors.invalid_input_file(
            f"Format {fmt} is not accepted for edit inputs. Supported formats are "
            f"{', '.join(constants.EDIT_INPUT_FORMATS)}.",
            path=str(resolved),
        )

    return LocalImage(
        path=resolved,
        format=fmt,
        width=width,
        height=height,
        size_bytes=size_bytes,
        has_alpha=has_alpha,
        alpha_extrema=extrema,
    )


def validate_mask(mask: LocalImage, first_reference: LocalImage) -> None:
    """Enforce the three mask rules from Requirements IMG-REQ-004.

    The alpha rule is the one worth explaining: a mask selects the region to
    redraw through its *transparent* pixels. A fully opaque alpha channel
    selects nothing, so the request would be paid for and change nothing. That
    is a local failure, not a service round-trip.
    """
    if (mask.width, mask.height) != (first_reference.width, first_reference.height):
        raise errors.invalid_mask(
            f"Mask is {mask.width}x{mask.height} but the first reference image is "
            f"{first_reference.width}x{first_reference.height}. They must match.",
            path=str(mask.path),
        )

    if mask.format != first_reference.format:
        raise errors.invalid_mask(
            f"Mask format {mask.format} does not match the first reference image's "
            f"format {first_reference.format}. They must match.",
            path=str(mask.path),
        )

    if not mask.has_alpha:
        raise errors.invalid_mask(
            "Mask has no alpha channel. A mask marks the region to redraw with "
            "transparent pixels, so it must carry alpha — use a PNG or WebP "
            "reference and mask when you need masked editing.",
            path=str(mask.path),
        )

    if mask.alpha_extrema is not None and mask.alpha_extrema[0] == mask.alpha_extrema[1] == 255:
        raise errors.invalid_mask(
            "Mask is fully opaque, so it selects no region to edit. Make the area "
            "you want redrawn transparent.",
            path=str(mask.path),
        )


_UNSAFE_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE_RUN = re.compile(r"\s+")


def sanitize_basename(raw: str | None) -> str:
    """Reduce a caller basename to a safe single filename component.

    Everything that could escape the output directory or produce an unopenable
    file is removed rather than rejected, except the empty result, which fails
    closed. Containment is re-verified after the join in `publish_atomic`, so
    this function is a filter and not the only defence.
    """
    if raw is None:
        return constants.DEFAULT_BASENAME

    # Guard the type before calling .strip(). Without this a Path or an int
    # escapes as a raw AttributeError, which is outside the closed taxonomy
    # every other validator in models.py maintains.
    if not isinstance(raw, str):
        raise errors.invalid_request(
            f"basename must be a string; got {type(raw).__name__}.",
            field="basename",
        )

    candidate = raw.strip()
    if not candidate:
        raise errors.invalid_request(
            "basename must not be blank. Omit it to use the default "
            f"'{constants.DEFAULT_BASENAME}'.",
            field="basename",
        )

    # Take the last path-ish component so `../../etc/passwd` becomes `passwd`
    # before the character filter runs.
    candidate = candidate.replace("\\", "/").rsplit("/", 1)[-1]
    candidate = _UNSAFE_NAME_CHARS.sub("", candidate)
    candidate = _WHITESPACE_RUN.sub(" ", candidate).strip()
    # Leading dots hide files; trailing dots and spaces are silently stripped by
    # Windows, which would make the name we report differ from the name on disk.
    candidate = candidate.lstrip(".").rstrip(". ")
    candidate = candidate[: constants.MAX_BASENAME_CHARS].rstrip(". ")

    if not candidate:
        raise errors.invalid_request(
            "basename contained no usable characters after sanitization.",
            field="basename",
        )

    # Strip whitespace and dots from the stem before the reserved-name check.
    # Windows discards trailing spaces and dots when resolving a path, so
    # "CON .png" and "NUL..png" both reach the real device; comparing the raw
    # stem would let them through.
    stem = candidate.split(".", 1)[0].strip(" .").upper()
    if stem in constants.WINDOWS_RESERVED_NAMES:
        raise errors.invalid_request(
            f"basename '{candidate}' uses the reserved Windows device name "
            f"'{stem}'.",
            field="basename",
        )

    return candidate


def resolve_output_dir(output_dir: str | None, *, cwd: Path | None = None) -> Path:
    """Resolve the destination directory.

    When omitted, the working directory is read *now* rather than at import, so
    the default follows the caller's session instead of wherever the server
    happened to start. When supplied, it must be absolute: silently resolving a
    relative override against the server's CWD would put files somewhere the
    caller did not ask for.
    """
    if output_dir is None:
        base = Path.cwd() if cwd is None else cwd
        return base / constants.DEFAULT_OUTPUT_SUBDIR

    if not isinstance(output_dir, str):
        raise errors.invalid_request(
            f"output_dir must be a string; got {type(output_dir).__name__}.",
            field="output_dir",
        )

    candidate = output_dir.strip()
    if not candidate:
        raise errors.invalid_request(
            "output_dir must not be blank. Omit it to use "
            f"'<working-directory>/{constants.DEFAULT_OUTPUT_SUBDIR}/'.",
            field="output_dir",
        )

    path = Path(candidate)
    if not path.is_absolute():
        raise errors.invalid_request(
            f"output_dir must be an absolute path; got '{candidate}'. This tool "
            "does not resolve a relative override against its own working "
            "directory.",
            field="output_dir",
        )

    # Constitution principle 3: every locally knowable path constraint is
    # checked BEFORE the credential and the paid call. Absoluteness alone is not
    # enough — an output_dir naming an existing regular file passes that check,
    # and the failure would otherwise surface only after the image had been
    # generated and billed. Walk to the nearest existing ancestor and confirm we
    # could actually create the directory there.
    probe = path
    while True:
        if probe.exists():
            if not probe.is_dir():
                raise errors.invalid_request(
                    f"output_dir '{candidate}' is not a directory (or lies under "
                    f"'{probe}', which is a file).",
                    field="output_dir",
                )
            break
        parent = probe.parent
        if parent == probe:
            # Reached a root that does not exist: an unmapped drive or share.
            raise errors.invalid_request(
                f"output_dir '{candidate}' is on a root that does not exist.",
                field="output_dir",
            )
        probe = parent

    return path


def decode_image_payload(b64_payload: str, expected_format: str, *, index: int) -> DecodedImage:
    """Base64-decode and prove the bytes really are the requested format."""
    if not b64_payload:
        raise errors.output_error(
            "The API returned an image entry with no base64 data.", index=index
        )

    try:
        data = base64.b64decode(b64_payload, validate=True)
    except (binascii.Error, ValueError):
        raise errors.output_error(
            "The API returned image data that is not valid base64.", index=index
        ) from None

    if not data:
        raise errors.output_error(
            "The API returned an empty image after decoding.", index=index
        )

    try:
        fmt, width, height, _has_alpha, _extrema = _describe(data)
    except errors.ImageToolError:
        raise errors.output_error(
            "The API returned an image in an unrecognised format.", index=index
        ) from None
    except Exception:
        # Broad for the same reason `inspect_local_image` is, and the narrow
        # form here was a real defect: PIL runs its own decompression-bomb check
        # inside `Image.open()`, BEFORE `_describe` gets to apply
        # MAX_DECODE_PIXELS, and `DecompressionBombError` derives from plain
        # Exception. A provider payload declaring, say, 20000x20000 therefore
        # escaped the closed taxonomy entirely, past `_publish_all`'s
        # `except ImageToolError` — discarding valid, already-paid-for images
        # from the same response and surfacing as `internal_error`.
        raise errors.output_error(
            "The API returned data that could not be decoded as an image.",
            index=index,
        ) from None

    if fmt != expected_format:
        raise errors.output_error(
            f"The API returned a {fmt} image but {expected_format} was requested.",
            index=index,
        )

    return DecodedImage(data=data, format=fmt, width=width, height=height)


def _candidate_name(basename: str, extension: str, attempt: int) -> str:
    """image.png, image-2.png, image-3.png, ..."""
    if attempt == 0:
        return f"{basename}{extension}"
    return f"{basename}-{attempt + constants.FIRST_COLLISION_SUFFIX - 1}{extension}"


def _link_or_create(tmp_path: Path, target: Path, data: bytes) -> bool:
    """Publish `tmp_path` as `target` without ever overwriting.

    Returns False when the target already exists, so the caller can advance the
    collision suffix. Raises only on a genuine filesystem failure.
    """
    try:
        os.link(tmp_path, target)
        return True
    except FileExistsError:
        return False
    except (OSError, NotImplementedError, AttributeError):
        # Filesystem refuses hard links (some network shares, some FAT volumes).
        # O_EXCL keeps the create exclusive; the write that follows is not
        # atomic with it, but the name still cannot be stolen from an existing
        # file, which is the property this tool guarantees.
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return True


def publish_atomic(
    data: bytes,
    dest_dir: Path,
    basename: str,
    extension: str,
) -> Path:
    """Write `data` into `dest_dir` under a collision-safe name. Never overwrite.

    The temporary file lives in the destination directory so the publish step is
    a same-filesystem link, and it is removed in a `finally` on every path — a
    failure must not leave a `.part` file that looks like output.
    """
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise errors.output_error(
            f"Output directory could not be created: {type(exc).__name__}."
        ) from None

    if not dest_dir.is_dir():
        raise errors.output_error(
            "Output directory path exists but is not a directory."
        )

    fd, tmp_name = tempfile.mkstemp(dir=str(dest_dir), suffix=constants.TEMP_SUFFIX)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        for attempt in range(constants.MAX_COLLISION_SUFFIX):
            target = dest_dir / _candidate_name(basename, extension, attempt)

            # Containment re-check: after sanitization *and* the join, the file
            # must still be a direct child of the destination.
            if target.parent.resolve() != dest_dir.resolve():
                raise errors.invalid_request(
                    "Resolved output path escapes the output directory.",
                    field="basename",
                )

            if _link_or_create(tmp_path, target, data):
                return target

        raise errors.output_error(
            f"Could not find a free filename after {constants.MAX_COLLISION_SUFFIX} "
            f"attempts starting from '{basename}{extension}'."
        )
    except errors.ImageToolError:
        raise
    except OSError as exc:
        raise errors.output_error(
            f"Writing the output image failed: {type(exc).__name__}."
        ) from None
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:  # pragma: no cover - best effort cleanup
            pass
