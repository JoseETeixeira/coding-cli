"""Filesystem, pixel, and publication contract for `gpt_image_2.images`.

Traces acceptance criterion IMG-AC-006 (and the local-input half of IMG-AC-004):
every rule about reading a local file, proving returned bytes really are the
requested format, and putting a file on disk without ever clobbering one.

Nothing here touches a network. `images` imports neither `openai` nor `mcp`,
which is exactly what makes this whole file a `tmp_path` exercise.

Two sections are audit regressions rather than original coverage, and both share
a trap worth naming once: the *code* they assert on is the same before and after
the fix, so a code-only assertion would pass against the bug.

* "Decompression bombs" — a 68-byte PNG that declares 60000x60000. Reverting the
  pre-`load()` size check still yields INVALID_INPUT_FILE, just 192 MB later, so
  those tests assert on the message and on a spy over `ImageFile.load`.
* "resolve_output_dir — the nearest-existing-ancestor walk" — the unit half of a
  check that has to happen before the credential. The money half lives in
  `test_validation.py`, which drives the same shapes through `server.generate_image`
  with counters on `resolve_api_key` and `build_client`.
"""

from __future__ import annotations

import base64
import hashlib
import struct
import threading
import zlib
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import pytest
from PIL import Image as PILImage
from PIL import ImageFile as PILImageFile

from conftest import REPO_ROOT, b64_image, make_image_bytes, write_image
from gpt_image_2 import constants, errors, images, models

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: A real PNG, kept small so slicing it produces predictable truncation.
_PNG = make_image_bytes("png", size=(64, 64))

#: A real GIF: decodable by Pillow, but not one of our accepted input formats.
_GIF = base64.b64decode(
    "R0lGODlhEAAQAIAAAP///wAAACH5BAEAAAAALAAAAAAQABAAAAIOhI+py+0Po5y02ouzPgUAOw=="
)


def raised_code(excinfo: pytest.ExceptionInfo[errors.ImageToolError]) -> str:
    """The closed error code, which is the only thing tests may assert on."""
    return excinfo.value.code


def _rejects_image_tool_error(call: Callable[[], Any]) -> errors.ImageToolError:
    """Run `call` and return the `ImageToolError` it must raise.

    A bare `pytest.raises(errors.ImageToolError)` lets an escaping
    `DecompressionBombError` surface as a test *error* rather than a failure —
    the right outcome, but a confusing one to read. Naming the expectation here
    keeps the failure message pointed at the taxonomy.
    """
    with pytest.raises(errors.ImageToolError) as excinfo:
        call()
    return excinfo.value


def make_local(directory: Path, name: str, **kwargs: Any) -> images.LocalImage:
    """A `LocalImage` built the only supported way: by inspecting a real file."""
    return images.inspect_local_image(str(write_image(directory, name, **kwargs)))


def png_declaring(width: int, height: int) -> bytes:
    """A structurally valid PNG header that LIES about its dimensions.

    Signature + IHDR + a token IDAT + IEND. 68 bytes whatever it declares, which
    is the entire decompression-bomb attack: the 50 MB byte cap cannot see it,
    and a decoder that trusts the header allocates `width * height * channels`
    bytes before noticing that the pixel data was never there.

    The CRCs are real, because Pillow validates them and a bad one would make
    this file fail for the wrong reason.
    """

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    # width, height, bit depth 8, colour type 2 (truecolour), default filters.
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00" * 16))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def load_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Every full-bitmap decode Pillow is asked to perform, in order.

    `ImageFile.load` is the call that allocates `width * height * channels`
    bytes, and `PngImageFile` inherits it unchanged. Recording it is what turns
    "rejected before any allocation" from a claim in a docstring into an
    assertion — the error *code* alone cannot tell the pre-load rejection apart
    from the post-load one, because both end up as INVALID_INPUT_FILE.
    """
    seen: list[tuple[int, int]] = []
    real_load = PILImageFile.ImageFile.load

    def _spy(self: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(tuple(self.size))
        return real_load(self, *args, **kwargs)

    monkeypatch.setattr(PILImageFile.ImageFile, "load", _spy)
    return seen


# ---------------------------------------------------------------------------
# inspect_local_image — rejection
# ---------------------------------------------------------------------------


def _missing(tmp_path: Path) -> str:
    return str(tmp_path / "nope.png")


def _directory(tmp_path: Path) -> str:
    target = tmp_path / "a-directory.png"
    target.mkdir()
    return str(target)


def _empty(tmp_path: Path) -> str:
    target = tmp_path / "empty.png"
    target.write_bytes(b"")
    return str(target)


def _text_renamed_png(tmp_path: Path) -> str:
    target = tmp_path / "actually-text.png"
    target.write_text("this is a text file wearing a png costume\n", encoding="utf-8")
    return str(target)


def _real_gif(tmp_path: Path) -> str:
    target = tmp_path / "animation.gif"
    target.write_bytes(_GIF)
    return str(target)


def _truncated_header(tmp_path: Path) -> str:
    """First ~40 bytes: signature plus IHDR, then nothing. Header-level corrupt."""
    target = tmp_path / "truncated-header.png"
    target.write_bytes(_PNG[:40])
    return str(target)


def _truncated_body(tmp_path: Path) -> str:
    """Enough to open, not enough to decode. Exercises the `load()` failure."""
    target = tmp_path / "truncated-body.png"
    target.write_bytes(_PNG[:60])
    return str(target)


def _one_byte_junk(tmp_path: Path) -> str:
    target = tmp_path / "junk.png"
    target.write_bytes(b"\x00")
    return str(target)


@pytest.mark.parametrize(
    ("name", "factory", "expected_code"),
    [
        ("blank", lambda _tmp: "", errors.INVALID_REQUEST),
        ("whitespace_only", lambda _tmp: "   \t ", errors.INVALID_REQUEST),
        ("missing", _missing, errors.INVALID_INPUT_FILE),
        ("directory", _directory, errors.INVALID_INPUT_FILE),
        ("empty_file", _empty, errors.INVALID_INPUT_FILE),
        ("foreign_text", _text_renamed_png, errors.INVALID_INPUT_FILE),
        ("foreign_gif", _real_gif, errors.INVALID_INPUT_FILE),
        ("truncated_header", _truncated_header, errors.INVALID_INPUT_FILE),
        ("truncated_body", _truncated_body, errors.INVALID_INPUT_FILE),
        ("one_byte_junk", _one_byte_junk, errors.INVALID_INPUT_FILE),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_inspect_local_image_rejects(
    tmp_path: Path,
    name: str,
    factory: Callable[[Path], str],
    expected_code: str,
) -> None:
    raw = factory(tmp_path)

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image(raw)

    assert raised_code(excinfo) == expected_code


def test_inspect_local_image_blank_names_the_field() -> None:
    """A blank path is a request-shape problem, so it points at the field."""
    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image("", field="mask_path")

    assert raised_code(excinfo) == errors.INVALID_REQUEST
    assert excinfo.value.details["field"] == "mask_path"


def test_inspect_local_image_reports_the_offending_path(tmp_path: Path) -> None:
    """IMG-REQ-004: the failure identifies the path, and nothing else."""
    bad = tmp_path / "actually-text.png"
    bad.write_text("nope", encoding="utf-8")

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image(str(bad))

    assert raised_code(excinfo) == errors.INVALID_INPUT_FILE
    assert Path(excinfo.value.details["path"]).name == "actually-text.png"
    assert set(excinfo.value.details) == {"path"}


# ---------------------------------------------------------------------------
# inspect_local_image — acceptance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fmt", "filename"),
    [("png", "shot.png"), ("jpeg", "shot.jpg"), ("webp", "shot.webp")],
)
def test_inspect_local_image_accepts_supported_formats(
    tmp_path: Path, fmt: str, filename: str
) -> None:
    path = write_image(tmp_path, filename, fmt=fmt, size=(48, 32), mode="RGB")

    local = images.inspect_local_image(str(path))

    assert local.format == fmt
    assert local.format in constants.EDIT_INPUT_FORMATS
    assert (local.width, local.height) == (48, 32)
    assert local.size_bytes == path.stat().st_size
    assert local.path == path.resolve()


def test_inspect_local_image_reports_alpha_for_rgba_png(tmp_path: Path) -> None:
    path = write_image(tmp_path, "rgba.png", fmt="png", mode="RGBA", alpha=17)

    local = images.inspect_local_image(str(path))

    assert local.has_alpha is True
    assert local.alpha_extrema == (17, 17)


def test_inspect_local_image_reports_no_alpha_for_rgb_jpeg(tmp_path: Path) -> None:
    path = write_image(tmp_path, "photo.jpg", fmt="jpeg", mode="RGB")

    local = images.inspect_local_image(str(path))

    assert local.has_alpha is False
    assert local.alpha_extrema is None


# ---------------------------------------------------------------------------
# The 50 MB local cap — proven with a shrunken constant, not a 50 MB file
# ---------------------------------------------------------------------------


@pytest.fixture
def describe_spy(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    """Records every decode attempt so ordering can be asserted, not assumed."""
    seen: list[bytes] = []

    def _spy(payload: bytes):
        seen.append(payload)
        raise errors.invalid_input_file("decode reached")

    monkeypatch.setattr(images, "_describe", _spy)
    return seen


def test_size_cap_rejects_at_the_limit_before_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, describe_spy: list[bytes]
) -> None:
    path = write_image(tmp_path, "big.png")
    size = path.stat().st_size
    monkeypatch.setattr(constants, "MAX_EDIT_FILE_BYTES", size)

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image(str(path))

    assert raised_code(excinfo) == errors.INVALID_INPUT_FILE
    # The whole point: the file was never read or decoded.
    assert describe_spy == []


def test_size_cap_lets_a_file_one_byte_under_the_limit_through_to_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, describe_spy: list[bytes]
) -> None:
    """The bound is exclusive-at-the-top, so `size == cap - 1` still decodes."""
    path = write_image(tmp_path, "big.png")
    size = path.stat().st_size
    monkeypatch.setattr(constants, "MAX_EDIT_FILE_BYTES", size + 1)

    with pytest.raises(errors.ImageToolError):
        images.inspect_local_image(str(path))

    assert describe_spy == [path.read_bytes()]


# ---------------------------------------------------------------------------
# Decompression bombs: a header-declared size is refused before `load()`
#
# The byte cap above cannot see this class of file at all. Every test in this
# section uses a 68-byte PNG — six orders of magnitude under the 50 MB limit,
# and still enough to demand hundreds of megabytes from a trusting decoder. It
# is also the cheapest thing an attacker can send, and it lands during
# pre-credential validation, where a caller-supplied file is inspected for free.
# ---------------------------------------------------------------------------


def test_the_load_spy_sees_an_ordinary_decode(
    tmp_path: Path, load_calls: list[tuple[int, int]]
) -> None:
    """Negative control for `load_calls`.

    Without this, every `assert load_calls == []` below could be passing because
    the spy was never wired to the method Pillow actually calls, and the whole
    section would be green and worthless.
    """
    path = write_image(tmp_path, "ordinary.png", size=(48, 32))

    local = images.inspect_local_image(str(path))

    assert (local.width, local.height) == (48, 32)
    assert load_calls == [(48, 32)], "the spy is not on the method that allocates"


def test_a_header_declared_bomb_is_refused_before_any_bitmap_is_allocated(
    tmp_path: Path, load_calls: list[tuple[int, int]]
) -> None:
    """Catches: deleting the pre-`load()` `img.size` check from `images._describe`.

    8000x8000 is 64,000,000 declared pixels — above this tool's 50,000,000
    `MAX_DECODE_PIXELS`, but comfortably below Pillow's own bomb ceiling
    (2 x 89,478,485), so Pillow raises nothing and our check is the only thing
    between a 68-byte file and a 192 MB allocation.

    Note carefully why the code assertion alone would be worthless here: revert
    the check and Pillow allocates the bitmap, then fails with a truncation
    `OSError`, which the broad `except` maps to INVALID_INPUT_FILE anyway. The
    two assertions that actually bite are the message — only the pre-load branch
    names the declared size and the limit — and `load_calls == []`.
    """
    bomb = tmp_path / "bomb.png"
    bomb.write_bytes(png_declaring(8000, 8000))
    assert bomb.stat().st_size < 1024, "the point is that this file is tiny"
    assert 8000 * 8000 > constants.MAX_DECODE_PIXELS
    assert 8000 * 8000 < 2 * PILImage.MAX_IMAGE_PIXELS, "Pillow would have caught it"

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image(str(bomb))

    assert raised_code(excinfo) == errors.INVALID_INPUT_FILE
    assert "8000x8000" in excinfo.value.message
    assert f"{constants.MAX_DECODE_PIXELS:,}" in excinfo.value.message
    assert Path(excinfo.value.details["path"]).name == "bomb.png"
    assert load_calls == [], "the bitmap was allocated before the size check ran"


def test_pillows_own_bomb_error_cannot_escape_the_closed_taxonomy(
    tmp_path: Path, load_calls: list[tuple[int, int]]
) -> None:
    """Catches: narrowing `except Exception` in `inspect_local_image` back to
    `(UnidentifiedImageError, OSError, ValueError)`.

    At 60000x60000 — 3.6 billion declared pixels — Pillow's guard fires first,
    and it fires inside `PILImage.open()`, before `_describe` gets to look at
    `img.size` at all. `DecompressionBombError` derives from plain `Exception`
    and from none of those three, so a narrowed except clause lets it escape
    `inspect_local_image` entirely and surface at the MCP edge as
    `internal_error` with a traceback, for what is plainly a bad input file.
    """
    bomb = tmp_path / "huge.png"
    bomb.write_bytes(png_declaring(60_000, 60_000))
    assert bomb.stat().st_size < 1024

    # Prove the premise instead of assuming it: this file really does make
    # Pillow raise its bomb error, and it raises from `open`, not from `load`.
    with pytest.raises(PILImage.DecompressionBombError):
        PILImage.open(BytesIO(bomb.read_bytes()))
    assert load_calls == []

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image(str(bomb))

    assert raised_code(excinfo) == errors.INVALID_INPUT_FILE
    assert Path(excinfo.value.details["path"]).name == "huge.png"
    assert set(excinfo.value.details) == {"path"}
    assert load_calls == []


def test_the_declared_pixel_ceiling_is_inclusive_at_the_top(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, load_calls: list[tuple[int, int]]
) -> None:
    """Catches: `>` becoming `>=` (or the reverse) on the MAX_DECODE_PIXELS check.

    The ceiling is shrunk rather than the file grown, exactly as the 50 MB cap
    above is tested, so the at-limit case allocates 3 MB instead of 150 MB.
    """
    monkeypatch.setattr(constants, "MAX_DECODE_PIXELS", 1_000_000)

    at_limit = tmp_path / "at-limit.png"
    at_limit.write_bytes(png_declaring(1000, 1000))  # exactly 1,000,000
    over = tmp_path / "over.png"
    over.write_bytes(png_declaring(1000, 1008))  # 1,008,000

    # Exactly at the ceiling is still allowed through to the decode, where this
    # particular file fails for the ordinary truncation reason instead.
    with pytest.raises(errors.ImageToolError) as allowed:
        images.inspect_local_image(str(at_limit))
    assert raised_code(allowed) == errors.INVALID_INPUT_FILE
    assert "1000x1000" not in allowed.value.message
    assert load_calls == [(1000, 1000)]

    # One 8-pixel row over it is not.
    with pytest.raises(errors.ImageToolError) as refused:
        images.inspect_local_image(str(over))
    assert raised_code(refused) == errors.INVALID_INPUT_FILE
    assert "1000x1008" in refused.value.message
    assert "1,000,000" in refused.value.message
    assert load_calls == [(1000, 1000)], "the oversize header still reached load()"


def test_a_bomb_routed_through_validate_edit_stays_inside_the_taxonomy(
    tmp_path: Path, load_calls: list[tuple[int, int]]
) -> None:
    """The same file through the real caller: `models.validate_edit`.

    `inspect_local_image` is only ever reached through here in production, as a
    reference or as a mask, and both entries must produce a closed code. A
    `DecompressionBombError` escaping either one becomes `internal_error` at the
    MCP edge — a 500-shaped answer to a caller mistake, and a traceback in the
    log for a file the caller chose.
    """
    bomb = tmp_path / "bomb.png"
    bomb.write_bytes(png_declaring(60_000, 60_000))

    as_reference = _rejects_image_tool_error(
        lambda: models.validate_edit(prompt="p", image_paths=[str(bomb)])
    )
    assert as_reference.code == errors.INVALID_INPUT_FILE
    assert load_calls == []

    reference = write_image(tmp_path, "reference.png", mode="RGBA", alpha=0)
    as_mask = _rejects_image_tool_error(
        lambda: models.validate_edit(
            prompt="p", image_paths=[str(reference)], mask_path=str(bomb)
        )
    )
    assert as_mask.code == errors.INVALID_INPUT_FILE
    # The legitimate reference decoded; only the bomb was refused. (An RGBA file
    # records two entries: `_describe` calls `load()`, then `getchannel("A")`
    # calls it again as a no-op. The set is the assertion that matters.)
    assert set(load_calls) == {(64, 64)}


# ---------------------------------------------------------------------------
# validate_mask
# ---------------------------------------------------------------------------


def test_validate_mask_accepts_a_matching_transparent_mask(
    reference_png: Path, mask_png: Path
) -> None:
    reference = images.inspect_local_image(str(reference_png))
    mask = images.inspect_local_image(str(mask_png))

    assert images.validate_mask(mask, reference) is None


def _mask_wrong_size(tmp_path: Path) -> images.LocalImage:
    return make_local(tmp_path, "m.png", fmt="png", size=(32, 32), mode="RGBA", alpha=0)


def _mask_wrong_format(tmp_path: Path) -> images.LocalImage:
    return make_local(tmp_path, "m.webp", fmt="webp", size=(64, 64), mode="RGBA", alpha=0)


def _mask_no_alpha(tmp_path: Path) -> images.LocalImage:
    return make_local(tmp_path, "m.png", fmt="png", size=(64, 64), mode="RGB")


def _mask_fully_opaque(tmp_path: Path) -> images.LocalImage:
    return make_local(tmp_path, "m.png", fmt="png", size=(64, 64), mode="RGBA", alpha=255)


@pytest.mark.parametrize(
    ("name", "factory"),
    [
        ("dimension_mismatch", _mask_wrong_size),
        ("format_mismatch", _mask_wrong_format),
        ("no_alpha_channel", _mask_no_alpha),
        ("fully_opaque_alpha", _mask_fully_opaque),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_validate_mask_rejects(
    tmp_path: Path,
    reference_png: Path,
    name: str,
    factory: Callable[[Path], images.LocalImage],
) -> None:
    reference = images.inspect_local_image(str(reference_png))
    mask_dir = tmp_path / name
    mask_dir.mkdir()
    mask = factory(mask_dir)

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.validate_mask(mask, reference)

    assert raised_code(excinfo) == errors.INVALID_MASK
    assert Path(excinfo.value.details["path"]).parent.name == name


# ---------------------------------------------------------------------------
# sanitize_basename
# ---------------------------------------------------------------------------


def test_sanitize_basename_defaults_when_omitted() -> None:
    assert images.sanitize_basename(None) == constants.DEFAULT_BASENAME == "image"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("photo", "photo"),
        ("  my photo  ", "my photo"),
        ("my    photo", "my photo"),
        (".hidden", "hidden"),
        ("photo...", "photo"),
        ("photo.  ", "photo"),
        ("../../etc/passwd", "passwd"),
        ("..\\..\\win.ini", "win.ini"),
        ("C:\\Windows\\System32\\drivers\\etc\\hosts", "hosts"),
        ('bad<>:"|?*chars', "badchars"),
        ("ctrl\x00chars\x1f", "ctrlchars"),
        ("CONSOLE", "CONSOLE"),
        ("nul-ish", "nul-ish"),
    ],
)
def test_sanitize_basename_reduces_to_a_safe_component(raw: str, expected: str) -> None:
    result = images.sanitize_basename(raw)

    assert result == expected
    assert "/" not in result
    assert "\\" not in result
    assert result == Path(result).name
    assert result not in {".", ".."}


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "\t\n", "....", "...", "///", "<>:|?*", "CON", "con", "con.png",
     "CON.PNG", "LPT1", "lpt1.jpeg", "NUL", "aux.webp", "COM9"],
)
def test_sanitize_basename_rejects(raw: str) -> None:
    with pytest.raises(errors.ImageToolError) as excinfo:
        images.sanitize_basename(raw)

    assert raised_code(excinfo) == errors.INVALID_REQUEST
    assert excinfo.value.details["field"] == "basename"


# Regression: the reserved-name check compared the raw stem, so "CON .png"
# slipped through even though Windows strips the trailing space and resolves
# it to the CON device. The stem is now stripped of spaces and dots first.
@pytest.mark.parametrize("raw", ["CON .png", "NUL .png", "COM1 .txt"])
def test_sanitize_basename_rejects_a_reserved_name_with_a_trailing_space(
    raw: str,
) -> None:
    with pytest.raises(errors.ImageToolError) as excinfo:
        images.sanitize_basename(raw)

    assert raised_code(excinfo) == errors.INVALID_REQUEST


def test_sanitize_basename_truncates_a_long_name() -> None:
    result = images.sanitize_basename("a" * 200)

    assert len(result) <= constants.MAX_BASENAME_CHARS
    assert result == "a" * constants.MAX_BASENAME_CHARS


def test_sanitize_basename_truncation_leaves_no_trailing_dot_or_space() -> None:
    """Windows silently eats a trailing dot, which would desync the reported name."""
    raw = ("x" * (constants.MAX_BASENAME_CHARS - 1)) + ". tail"

    result = images.sanitize_basename(raw)

    assert len(result) <= constants.MAX_BASENAME_CHARS
    assert result == result.rstrip(". ")


# ---------------------------------------------------------------------------
# resolve_output_dir — only the cwd-independence half lives here
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["", "   ", "relative/dir", "./out", "out"])
def test_resolve_output_dir_rejections_do_not_depend_on_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    first = tmp_path / "cwd-one"
    second = tmp_path / "cwd-two"
    first.mkdir()
    second.mkdir()

    codes = []
    for cwd in (first, second):
        monkeypatch.chdir(cwd)
        with pytest.raises(errors.ImageToolError) as excinfo:
            images.resolve_output_dir(raw)
        codes.append(raised_code(excinfo))
        assert excinfo.value.details["field"] == "output_dir"

    assert codes == [errors.INVALID_REQUEST, errors.INVALID_REQUEST]


def test_resolve_output_dir_absolute_override_is_returned_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert images.resolve_output_dir(f"  {tmp_path}  ") == Path(str(tmp_path))


def test_resolve_output_dir_default_is_read_from_the_injected_cwd(tmp_path: Path) -> None:
    assert (
        images.resolve_output_dir(None, cwd=tmp_path)
        == tmp_path / constants.DEFAULT_OUTPUT_SUBDIR
    )


# ---------------------------------------------------------------------------
# resolve_output_dir — the nearest-existing-ancestor walk
#
# Constitution principle 3: this has to happen here, before the credential and
# before the paid call. `tests/gpt_image_2/test_validation.py` drives the same
# two shapes through the real `server.generate_image` and asserts that neither
# the credential nor the client is touched; these are the unit half.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "suffix",
    [
        pytest.param("", id="output_dir-is-the-file-itself"),
        pytest.param("sub", id="one-level-under-the-file"),
        pytest.param("sub/deeper/deepest", id="three-levels-under-the-file"),
    ],
)
def test_resolve_output_dir_rejects_a_path_that_is_or_lies_under_a_regular_file(
    tmp_path: Path, suffix: str
) -> None:
    """Catches: deleting the `while True: if probe.exists() ...` ancestor walk.

    Being absolute is not enough. An `output_dir` naming an existing regular
    file passes the absoluteness check, and without the walk the failure only
    surfaces inside `publish_atomic` — after the image has been generated and
    billed, on a `mkdir` that cannot succeed. The walk moves the same knowledge
    to where it is free.
    """
    occupied = tmp_path / "not-a-directory.txt"
    occupied.write_bytes(b"in the way")
    candidate = occupied.joinpath(*suffix.split("/")) if suffix else occupied

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.resolve_output_dir(str(candidate))

    assert raised_code(excinfo) == errors.INVALID_REQUEST
    assert excinfo.value.details["field"] == "output_dir"
    # The message names the file that is actually in the way, which is the only
    # thing the caller can act on when the blocker is three levels up.
    assert str(occupied) in excinfo.value.message
    # Nothing was created and nothing was clobbered on the way to the answer.
    assert occupied.read_bytes() == b"in the way"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["not-a-directory.txt"]


def test_resolve_output_dir_accepts_a_deep_path_whose_ancestors_do_not_exist_yet(
    tmp_path: Path,
) -> None:
    """The walk must stop at the nearest existing DIRECTORY, not reject absence.

    Catches: an over-eager rewrite that requires `output_dir` (or its parent) to
    exist. IMG-REQ-006 explicitly allows the server to create the requested
    directory and its missing descendants, so a path four levels into thin air
    is legal and must come back verbatim, uncreated.
    """
    target = tmp_path / "a" / "b" / "c" / constants.DEFAULT_OUTPUT_SUBDIR

    assert images.resolve_output_dir(str(target)) == target
    assert not target.exists()
    assert not (tmp_path / "a").exists(), "validation must not create anything"


def test_resolve_output_dir_accepts_an_existing_directory(tmp_path: Path) -> None:
    """The other side of the same branch: an existing directory is fine."""
    existing = tmp_path / "already-here"
    existing.mkdir()

    assert images.resolve_output_dir(str(existing)) == existing


# ---------------------------------------------------------------------------
# decode_image_payload
# ---------------------------------------------------------------------------


def test_decode_image_payload_round_trips_a_png() -> None:
    raw = make_image_bytes("png", size=(48, 32))

    decoded = images.decode_image_payload(
        base64.b64encode(raw).decode("ascii"), "png", index=0
    )

    assert decoded.format == "png"
    assert (decoded.width, decoded.height) == (48, 32)
    assert decoded.data == raw
    assert decoded.size_bytes == len(raw)


@pytest.mark.parametrize(
    ("name", "payload_factory", "expected_format"),
    [
        ("empty_string", lambda: "", "png"),
        ("not_base64", lambda: "not base64!", "png"),
        ("base64_of_non_image", lambda: base64.b64encode(b"definitely not an image").decode("ascii"), "png"),
        ("base64_of_gif", lambda: base64.b64encode(_GIF).decode("ascii"), "png"),
        ("base64_of_truncated_png", lambda: base64.b64encode(_PNG[:60]).decode("ascii"), "png"),
        ("jpeg_when_png_expected", lambda: b64_image(fmt="jpeg"), "png"),
        ("webp_when_png_expected", lambda: b64_image(fmt="webp"), "png"),
        ("png_when_jpeg_expected", lambda: b64_image(fmt="png"), "jpeg"),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_decode_image_payload_rejects(
    name: str, payload_factory: Callable[[], str], expected_format: str
) -> None:
    with pytest.raises(errors.ImageToolError) as excinfo:
        images.decode_image_payload(payload_factory(), expected_format, index=3)

    assert raised_code(excinfo) == errors.OUTPUT_ERROR
    assert excinfo.value.details["image_index"] == 3


# ---------------------------------------------------------------------------
# publish_atomic — the no-overwrite guarantee
# ---------------------------------------------------------------------------


def test_publish_atomic_writes_the_exact_bytes(out_dir: Path) -> None:
    data = make_image_bytes("png", size=(48, 32))

    target = images.publish_atomic(data, out_dir, "image", ".png")

    assert target == out_dir / "image.png"
    assert target.read_bytes() == data


def test_publish_atomic_creates_missing_parent_directories(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "generated-images"

    target = images.publish_atomic(b"\x89PNG-ish", nested, "image", ".png")

    assert target.parent == nested
    assert nested.is_dir()


def test_publish_atomic_uses_the_documented_collision_names(out_dir: Path) -> None:
    written = [
        images.publish_atomic(f"payload-{i}".encode(), out_dir, "image", ".png")
        for i in range(3)
    ]

    assert [path.name for path in written] == ["image.png", "image-2.png", "image-3.png"]
    assert [path.read_bytes() for path in written] == [
        b"payload-0",
        b"payload-1",
        b"payload-2",
    ]


def test_publish_atomic_never_overwrites_an_existing_file(out_dir: Path) -> None:
    out_dir.mkdir(parents=True)
    existing = out_dir / "image.png"
    original = b"a precious pre-existing asset"
    existing.write_bytes(original)
    original_digest = hashlib.sha256(original).hexdigest()

    target = images.publish_atomic(b"the new image", out_dir, "image", ".png")

    assert target == out_dir / "image-2.png"
    assert existing.read_bytes() == original
    assert hashlib.sha256(existing.read_bytes()).hexdigest() == original_digest
    assert target.read_bytes() == b"the new image"


def test_publish_atomic_leaves_no_temporary_file_on_success(out_dir: Path) -> None:
    images.publish_atomic(b"payload", out_dir, "image", ".png")

    assert list(out_dir.glob(f"*{constants.TEMP_SUFFIX}")) == []
    assert [path.name for path in out_dir.iterdir()] == ["image.png"]


def test_publish_atomic_cleans_up_the_temporary_file_after_a_failure(
    out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> bool:
        raise OSError("disk went away mid-publish")

    monkeypatch.setattr(images, "_link_or_create", _boom)

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.publish_atomic(b"payload", out_dir, "image", ".png")

    assert raised_code(excinfo) == errors.OUTPUT_ERROR
    assert list(out_dir.glob(f"*{constants.TEMP_SUFFIX}")) == []
    assert list(out_dir.iterdir()) == []


def test_publish_atomic_fails_when_every_candidate_name_is_taken(
    out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(constants, "MAX_COLLISION_SUFFIX", 3)
    out_dir.mkdir(parents=True)
    for name in ("image.png", "image-2.png", "image-3.png"):
        (out_dir / name).write_bytes(b"taken")

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.publish_atomic(b"payload", out_dir, "image", ".png")

    assert raised_code(excinfo) == errors.OUTPUT_ERROR
    assert list(out_dir.glob(f"*{constants.TEMP_SUFFIX}")) == []
    assert sorted(path.name for path in out_dir.iterdir()) == [
        "image-2.png",
        "image-3.png",
        "image.png",
    ]
    assert {path.read_bytes() for path in out_dir.iterdir()} == {b"taken"}


def test_publish_atomic_refuses_a_basename_that_escapes_the_output_dir(
    out_dir: Path,
) -> None:
    """Containment is re-checked after the join, not only during sanitization."""
    escapee = out_dir.parent / "evil.png"

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.publish_atomic(b"payload", out_dir, "..{sep}evil".format(sep="/"), ".png")

    assert raised_code(excinfo) == errors.INVALID_REQUEST
    assert not escapee.exists()
    assert list(out_dir.glob(f"*{constants.TEMP_SUFFIX}")) == []


def test_publish_atomic_fails_when_the_destination_is_a_file(tmp_path: Path) -> None:
    occupied = tmp_path / "not-a-directory"
    occupied.write_bytes(b"in the way")

    with pytest.raises(errors.ImageToolError) as excinfo:
        images.publish_atomic(b"payload", occupied, "image", ".png")

    assert raised_code(excinfo) == errors.OUTPUT_ERROR
    assert occupied.read_bytes() == b"in the way"


def test_publish_atomic_survives_a_filesystem_that_refuses_hard_links(
    out_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `O_EXCL` fallback must produce identical names, bytes, and cleanup."""

    def _no_links(*_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError("this volume does not do hard links")

    monkeypatch.setattr(images.os, "link", _no_links)

    first = images.publish_atomic(b"one", out_dir, "image", ".png")
    second = images.publish_atomic(b"two", out_dir, "image", ".png")

    assert [first.name, second.name] == ["image.png", "image-2.png"]
    assert first.read_bytes() == b"one"
    assert second.read_bytes() == b"two"
    assert list(out_dir.glob(f"*{constants.TEMP_SUFFIX}")) == []


# ---------------------------------------------------------------------------
# Audit-driven regressions: the publication primitive and remote inputs
# ---------------------------------------------------------------------------


def test_concurrent_publishes_never_lose_or_clobber_an_image(out_dir: Path) -> None:
    """Hammer publish_atomic from many threads at one basename.

    This is the test that actually pins the no-clobber primitive. The previous
    suite passed even if `_link_or_create` were rewritten as a check-then-write,
    because a single-threaded test cannot observe the TOCTOU window. Here two
    threads that pick the same candidate name race for real: with a
    create-exclusive publish exactly one wins and the loser advances its suffix,
    so N threads produce N distinct files. With check-then-write, two threads
    can pass `exists()` together and one silently overwrites the other, which
    shows up as fewer than N files or as a body that does not match its writer.
    """
    workers = 16
    bodies = {i: make_image_bytes("png", size=(16 + i, 16)) for i in range(workers)}
    results: dict[int, Path] = {}
    errors_seen: list[BaseException] = []
    start = threading.Barrier(workers)

    def publish(index: int) -> None:
        try:
            start.wait(timeout=10)
            results[index] = images.publish_atomic(
                bodies[index], out_dir, "image", ".png"
            )
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertions
            errors_seen.append(exc)

    threads = [threading.Thread(target=publish, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors_seen, f"publish raised under contention: {errors_seen[:3]}"
    assert len(results) == workers

    paths = list(results.values())
    assert len({str(p) for p in paths}) == workers, "two threads shared a filename"

    on_disk = sorted(p.name for p in out_dir.glob("image*.png"))
    assert len(on_disk) == workers, f"expected {workers} files, found {on_disk}"

    # Every writer's bytes survived intact: nothing was overwritten.
    for index, path in results.items():
        assert path.read_bytes() == bodies[index], f"image {index} was clobbered"

    assert list(out_dir.glob("*.part")) == []


def test_link_or_create_refuses_an_existing_target(out_dir: Path, tmp_path: Path) -> None:
    """The primitive itself reports 'taken' rather than overwriting."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "image.png"
    target.write_bytes(b"original")

    source = tmp_path / "src.bin"
    source.write_bytes(b"replacement")

    assert images._link_or_create(source, target, b"replacement") is False
    assert target.read_bytes() == b"original"


@pytest.mark.parametrize(
    "remote",
    [
        "https://example.com/photo.png",
        "http://example.com/photo.png",
        "HTTPS://EXAMPLE.COM/PHOTO.PNG",
        "ftp://example.com/photo.png",
        "//example.com/photo.png",
        "data:image/png;base64,iVBORw0KGgo=",
    ],
)
def test_remote_inputs_are_never_fetched(remote: str) -> None:
    """IMG-REQ-004: 'SHALL not fetch remote resources'.

    Nothing in the suite previously passed a URL-shaped value, so a mutation
    that added an `httpx.get` branch to `inspect_local_image` would have passed
    every test. A URL must be treated as what it is here: a path that does not
    name a local file.
    """
    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image(remote)

    assert excinfo.value.code in {errors.INVALID_INPUT_FILE, errors.INVALID_REQUEST}


@pytest.mark.parametrize(
    ("candidate", "expected_phrase"),
    [
        pytest.param("https://example.com/photo.png", "Remote URLs", id="https-url"),
        pytest.param("data:image/png;base64,iVBORw0KGgo=", "Remote URLs", id="data-url"),
        pytest.param(
            "\\\\gpt-image-2-no-such-host\\share\\photo.png",
            "Network (UNC)",
            id="unc-backslashes",
        ),
        pytest.param(
            "//gpt-image-2-no-such-host/share/photo.png",
            "Network (UNC)",
            id="unc-forward-slashes",
        ),
    ],
)
def test_remote_and_unc_paths_are_refused_before_the_filesystem_is_touched(
    candidate: str, expected_phrase: str
) -> None:
    """Catches: removing the `_reject_remote` call from `inspect_local_image`.

    Without it the code stays INVALID_INPUT_FILE either way — a URL is simply a
    filename that does not exist — so the code proves nothing and the assertion
    has to be on the branch that produced it. Two things ride on this:

    * The message tells the caller *why* rather than "no such file", which is
      the wrong story for a URL.
    * A UNC path never reaches `Path.resolve()`, which on Windows performs a
      real DNS/SMB lookup and blocks for seconds against a host that does not
      exist. That is caller-controlled network I/O inside a paid operation's
      deadline, and IMG-REQ-004 says this tool fetches nothing remote.

    `details["path"]` echoes the raw candidate, not a resolved one, which is the
    second tell that no filesystem call happened.
    """
    with pytest.raises(errors.ImageToolError) as excinfo:
        images.inspect_local_image(candidate)

    assert raised_code(excinfo) == errors.INVALID_INPUT_FILE
    assert expected_phrase in excinfo.value.message
    assert excinfo.value.details["path"] == candidate[:80]


def test_images_module_has_no_network_capability() -> None:
    """Structural guard: the filesystem module must not import an HTTP client."""
    source = (REPO_ROOT / "gpt_image_2" / "images.py").read_text(encoding="utf-8")
    for forbidden in ("httpx", "requests", "urllib", "aiohttp", "socket"):
        assert forbidden not in source, f"images.py references {forbidden}"


def test_a_bomb_in_a_provider_payload_stays_inside_the_taxonomy() -> None:
    """The response path needs the same broad catch the input path has.

    PIL runs its own decompression-bomb check inside `Image.open()`, before
    `_describe` can apply MAX_DECODE_PIXELS, and `DecompressionBombError`
    derives from plain `Exception`. With a narrow
    `except (UnidentifiedImageError, OSError, ValueError)` it escaped
    `decode_image_payload` entirely.

    Mutation this catches: narrowing that except clause again. The bomb then
    escapes `_publish_all`'s `except errors.ImageToolError`, which discards
    valid, already-paid-for images from the same response and reports
    `internal_error` with a traceback instead of an indexed `output_error`.
    """
    bomb = base64.b64encode(png_declaring(20_000, 20_000)).decode("ascii")

    error = _rejects_image_tool_error(
        lambda: images.decode_image_payload(bomb, "png", index=1)
    )
    assert error.code == errors.OUTPUT_ERROR
    assert error.details["image_index"] == 1
