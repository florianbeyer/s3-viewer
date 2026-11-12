"""Grobe TIFF-Vorschau, klein genug zum schnellen Laden."""

from __future__ import annotations

import io
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from s3viewer.i18n import tr
from s3viewer.preview import Preview, content_type_base, extension_of

TIFF_PREVIEW_BYTE_LIMIT = 32 * 1024 * 1024
TIFF_PREVIEW_EDGE = 640
_MAX_PIXELS = 40_000_000


@dataclass(frozen=True)
class RenderedTiff:
    png: bytes
    notice: str


def is_tiff(key: str, content_type: str = "") -> bool:
    if extension_of(key) in {"tif", "tiff"}:
        return True
    return content_type_base(content_type) == "image/tiff"


def too_large_notice(size: int) -> str:
    limit = TIFF_PREVIEW_BYTE_LIMIT // (1024 * 1024)
    if size > TIFF_PREVIEW_BYTE_LIMIT:
        amount = max(1, round(size / (1024 * 1024)))
        return (
            tr("tiff_too_big_known", amount=amount, limit=limit)
        )
    return tr("tiff_too_big", limit=limit)


def build_tiff_preview(
    key: str,
    data: bytes,
    *,
    content_type: str = "",
    size: int | None = None,
    truncated: bool = False,
) -> Preview:
    filename = key.rsplit("/", 1)[-1] or key
    actual_size = size if size is not None else len(data)
    preview = Preview(
        kind="tiff",
        filename=filename,
        truncated=truncated,
        size=actual_size,
        content_type=content_type_base(content_type),
    )
    if not data:
        preview.kind = "empty"
        preview.notice = tr("empty_file")
        return preview
    if truncated or len(data) > TIFF_PREVIEW_BYTE_LIMIT or actual_size > TIFF_PREVIEW_BYTE_LIMIT:
        preview.notice = too_large_notice(actual_size)
        return preview
    try:
        rendered = render_tiff_preview(data)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        preview.notice = tr("tiff_failed")
        return preview
    preview.image = rendered.png
    preview.notice = rendered.notice
    return preview


def render_tiff_preview(data: bytes) -> RenderedTiff:
    try:
        return _render_with_pillow(data)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        return _render_with_tifffile(data)


def _render_with_pillow(data: bytes) -> RenderedTiff:
    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = _MAX_PIXELS
    try:
        with _quiet_stderr():
            image = Image.open(io.BytesIO(data))
        with image:
            original_width, original_height = image.size
            pages = int(getattr(image, "n_frames", 1) or 1)
            image.seek(0)
            try:
                image.draft("RGB", (TIFF_PREVIEW_EDGE, TIFF_PREVIEW_EDGE))
            except Exception:
                pass
            image.thumbnail((TIFF_PREVIEW_EDGE, TIFF_PREVIEW_EDGE), Image.Resampling.BOX)
            display = _display_image(image)
            buffer = io.BytesIO()
            display.save(buffer, format="PNG", compress_level=1)
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit
    notice = tr("tiff_rough", edge=TIFF_PREVIEW_EDGE, width=original_width, height=original_height)
    if pages > 1:
        notice += tr("tiff_page", pages=pages)
    return RenderedTiff(png=buffer.getvalue(), notice=notice)


def _render_with_tifffile(data: bytes) -> RenderedTiff:
    import numpy as np
    import tifffile

    with tifffile.TiffFile(io.BytesIO(data)) as tiff:
        page = tiff.pages[0]
        array = page.asarray()
        pages = len(tiff.pages)
    bands = _as_channels_last(np.asarray(array))
    height, width, count = bands.shape
    step = max(1, max(height, width) // TIFF_PREVIEW_EDGE)
    if step > 1:
        bands = bands[::step, ::step]
    shown = min(3, count)
    planes = [_scale_to_uint8(bands[:, :, index]) for index in range(shown)]
    if shown == 1:
        image = Image.fromarray(planes[0], mode="L").convert("RGB")
    elif shown == 2:
        zeros = np.zeros_like(planes[0])
        image = Image.fromarray(np.dstack((planes[0], planes[1], zeros)), mode="RGB")
    else:
        image = Image.fromarray(np.dstack(tuple(planes)), mode="RGB")
    image.thumbnail((TIFF_PREVIEW_EDGE, TIFF_PREVIEW_EDGE), Image.Resampling.BOX)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=1)
    channel_text = tr("tiff_channels_one") if count == 1 else tr("tiff_channels_many", count=count)
    if count > 3:
        channel_text += tr("tiff_first_three")
    elif count == 2:
        channel_text += tr("tiff_both")
    notice = tr(
        "tiff_stack",
        edge=TIFF_PREVIEW_EDGE,
        width=width,
        height=height,
        channels=channel_text,
        dtype=bands.dtype,
    )
    if pages > 1:
        notice += tr("tiff_page", pages=pages)
    return RenderedTiff(png=buffer.getvalue(), notice=notice)


def _as_channels_last(array):
    import numpy as np

    values = np.squeeze(array)
    if values.ndim == 2:
        return values[:, :, np.newaxis]
    if values.ndim != 3:
        raise ValueError(tr("tiff_shape", shape=tuple(array.shape)))
    if values.shape[0] <= 16 and values.shape[0] < values.shape[1] and values.shape[0] < values.shape[2]:
        values = np.moveaxis(values, 0, -1)
    return values


def _scale_to_uint8(plane):
    import numpy as np

    if plane.dtype == np.uint8:
        return plane
    data = plane.astype(np.float32, copy=False)
    finite = np.isfinite(data)
    output = np.zeros(plane.shape, dtype=np.uint8)
    if not finite.any():
        return output
    values = data[finite]
    low, high = np.percentile(values, (2, 98))
    if high <= low:
        low, high = float(values.min()), float(values.max())
    if high <= low:
        return output
    scaled = np.clip((data - low) / (high - low), 0, 1)
    scaled[~finite] = 0
    return (scaled * 255).astype(np.uint8)


@contextmanager
def _quiet_stderr():
    try:
        stderr_fd = sys.stderr.fileno()
    except (AttributeError, OSError):
        yield
        return
    saved = os.dup(stderr_fd)
    sink = open(os.devnull, "w")
    try:
        os.dup2(sink.fileno(), stderr_fd)
        yield
    finally:
        os.dup2(saved, stderr_fd)
        os.close(saved)
        sink.close()


def _display_image(image: Image.Image) -> Image.Image:
    if image.mode in {"RGB", "RGBA"}:
        return image
    if image.mode in {"P", "PA", "LA"}:
        return image.convert("RGBA")
    return image.convert("RGB")
