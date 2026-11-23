"""Grobe TIFF-Vorschau, klein genug zum schnellen Laden."""

from __future__ import annotations

import io
import os
import random
import sys
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, UnidentifiedImageError

from s3viewer.i18n import tr
from s3viewer.preview import Preview, content_type_base, extension_of

TIFF_PREVIEW_BYTE_LIMIT = 500 * 1024 * 1024
TIFF_PREVIEW_EDGE = 640
_MAX_PIXELS = 80_000_000
_MAX_DECODED_BYTES = 512 * 1024 * 1024
_OVERVIEW_LIMIT = 32

PALETTE_IDS = ("viridis", "ryg", "ylgnbu", "rdylbu", "spectral")

_STOPS: dict[str, tuple[tuple[int, int, int], ...]] = {
    "viridis": (
        (68, 1, 84),
        (72, 35, 116),
        (64, 67, 135),
        (52, 94, 141),
        (41, 120, 142),
        (32, 144, 140),
        (34, 167, 132),
        (68, 190, 112),
        (121, 209, 81),
        (189, 222, 38),
        (253, 231, 37),
    ),
    "ryg": (
        (0, 104, 55),
        (26, 152, 80),
        (102, 189, 99),
        (166, 217, 106),
        (217, 239, 139),
        (255, 255, 191),
        (254, 224, 139),
        (253, 174, 97),
        (244, 109, 67),
        (215, 48, 39),
        (165, 0, 38),
    ),
    "ylgnbu": (
        (255, 255, 217),
        (237, 248, 177),
        (199, 233, 180),
        (127, 205, 187),
        (65, 182, 196),
        (29, 145, 192),
        (34, 94, 168),
        (12, 44, 132),
    ),
    "rdylbu": (
        (165, 0, 38),
        (215, 48, 39),
        (244, 109, 67),
        (253, 174, 97),
        (254, 224, 144),
        (255, 255, 191),
        (224, 243, 248),
        (171, 217, 233),
        (116, 173, 209),
        (69, 117, 180),
        (49, 54, 149),
    ),
    "spectral": (
        (158, 1, 66),
        (213, 62, 79),
        (244, 109, 67),
        (253, 174, 97),
        (254, 224, 139),
        (255, 255, 191),
        (230, 245, 152),
        (171, 221, 164),
        (102, 194, 165),
        (50, 136, 189),
        (94, 79, 162),
    ),
}

_COMPRESSION_NAMES = {
    "ADOBE_DEFLATE": "Deflate",
    "DEFLATE": "Deflate",
    "LZW": "LZW",
    "JPEG": "JPEG",
    "NONE": "—",
    "PACKBITS": "PackBits",
    "CCITT_T4": "CCITT",
    "CCITT_T6": "CCITT",
    "JPEG2000": "JPEG2000",
    "ZSTD": "ZSTD",
    "WEBP": "WebP",
    "LERC": "LERC",
    "LZMA": "LZMA",
}

_DTYPE_NAMES = {
    "uint8": "UInt8",
    "uint16": "UInt16",
    "uint32": "UInt32",
    "uint64": "UInt64",
    "int8": "Int8",
    "int16": "Int16",
    "int32": "Int32",
    "int64": "Int64",
    "float16": "Float16",
    "float32": "Float32",
    "float64": "Float64",
    "bool": "Bool",
}

_RGB_PHOTOMETRIC = {"RGB", "YCBCR", "CIELAB", "ICCLAB", "ITULAB"}


class _TooLarge(Exception):
    pass


class _TooManyPixels(Exception):
    pass


@dataclass
class RenderedTiff:
    png: bytes
    notice: str
    array: object = None
    bands: int = 0
    mode: str = ""
    nodata: str = ""
    info: dict = field(default_factory=dict)


class RangeReader(io.RawIOBase):
    """Seekable view over HTTP range reads, with a small block cache."""

    def __init__(
        self,
        read_range: Callable[[int, int], bytes],
        size: int,
        *,
        block: int = 256 * 1024,
    ):
        super().__init__()
        self._read_range = read_range
        self._size = max(0, int(size))
        self._pos = 0
        self._block = max(4096, int(block))
        self._cache = b""
        self._cache_start = 0
        self.mode = "rb"
        self.name = "s3-range"

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            pos = offset
        elif whence == io.SEEK_CUR:
            pos = self._pos + offset
        elif whence == io.SEEK_END:
            pos = self._size + offset
        else:
            raise ValueError(f"whence {whence}")
        self._pos = max(0, min(int(pos), self._size))
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self._size - self._pos
        size = min(int(size), self._size - self._pos)
        if size <= 0:
            return b""
        data = self._read_cached(self._pos, size)
        self._pos += len(data)
        return data

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        count = len(data)
        buffer[:count] = data
        return count

    def _read_cached(self, pos: int, size: int) -> bytes:
        end = pos + size
        cache_end = self._cache_start + len(self._cache)
        if self._cache and pos >= self._cache_start and end <= cache_end:
            start = pos - self._cache_start
            return self._cache[start : start + size]
        fetch = min(max(size, self._block), self._size - pos)
        data = self._read_range(pos, fetch) or b""
        self._cache_start = pos
        self._cache = data
        return data[:size]


def is_tiff(key: str, content_type: str = "") -> bool:
    if extension_of(key) in {"tif", "tiff"}:
        return True
    return content_type_base(content_type) == "image/tiff"


def too_large_notice(size: int) -> str:
    limit = TIFF_PREVIEW_BYTE_LIMIT // (1024 * 1024)
    if size > TIFF_PREVIEW_BYTE_LIMIT:
        amount = max(1, round(size / (1024 * 1024)))
        return tr("tiff_too_big_known", amount=amount, limit=limit)
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
    except _TooLarge:
        preview.notice = too_large_notice(actual_size)
        return preview
    except _TooManyPixels:
        preview.notice = tr("tiff_failed")
        return preview
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        preview.notice = tr("tiff_failed")
        return preview
    _apply_rendered(preview, rendered)
    return preview


def build_tiff_from_source(
    key: str,
    source,
    *,
    content_type: str = "",
    size: int = 0,
    allow_full: bool = True,
) -> Preview:
    filename = key.rsplit("/", 1)[-1] or key
    preview = Preview(
        kind="tiff",
        filename=filename,
        size=size,
        content_type=content_type_base(content_type),
    )
    try:
        rendered = render_tiff_source(source, allow_full=allow_full)
    except _TooLarge:
        preview.notice = too_large_notice(size)
        return preview
    except _TooManyPixels:
        preview.notice = tr("tiff_failed")
        return preview
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, RuntimeError):
        preview.notice = tr("tiff_failed") if allow_full else too_large_notice(size)
        return preview
    _apply_rendered(preview, rendered)
    return preview


def render_tiff_preview(data: bytes) -> RenderedTiff:
    try:
        return render_tiff_source(io.BytesIO(data), allow_full=True)
    except (_TooLarge, _TooManyPixels):
        raise
    except Exception:
        return _render_with_pillow(data)


def render_tiff_source(source, *, allow_full: bool) -> RenderedTiff:
    import tifffile

    with tifffile.TiffFile(source) as tiff:
        if not tiff.pages:
            raise ValueError("empty tiff")
        page = tiff.pages[0]
        pages = len(tiff.pages)
        overviews = _overview_pages(tiff, page)
        levels = [page, *overviews]
        index = _choose_level(levels, allow_full=allow_full)
        chosen = levels[index]
        if _decoded_bytes(chosen) > _MAX_DECODED_BYTES:
            raise _TooManyPixels()
        array = _as_channels_last(np.asarray(chosen.asarray()))
        count = int(array.shape[2])
        array = _downsample(array)
        mode = _default_mode(page, count)
        nodata = _nodata_text(page)
        full_width, full_height = _page_size(page)
        overview_sizes = [_page_size(item) for item in overviews]
        overview_width, overview_height = _page_size(chosen)
        info = {
            "width": full_width,
            "height": full_height,
            "count": count,
            "dtype": _dtype_label(array.dtype),
            "compression": _compression_label(page),
            "tiled": bool(getattr(page, "is_tiled", False)),
            "tile_width": int(getattr(page, "tilewidth", 0) or 0),
            "tile_height": int(getattr(page, "tilelength", 0) or 0),
            "overviews": overview_sizes,
            "overview_level": index,
            "overview_width": overview_width,
            "overview_height": overview_height,
            "nodata": nodata,
            "pages": pages,
            "mode": mode,
            "palette": "viridis",
            "band": 0,
            "red": 0,
            "green": 1 if count > 1 else 0,
            "blue": 2 if count > 2 else 0,
        }
    png = render_styled(
        array,
        mode=mode,
        palette="viridis",
        band=0,
        red=0,
        green=int(info["green"]),
        blue=int(info["blue"]),
        nodata=nodata,
    )
    return RenderedTiff(
        png=png,
        notice=style_notice(info),
        array=array,
        bands=count,
        mode=mode,
        nodata=nodata,
        info=info,
    )


def render_styled(
    array,
    *,
    mode: str,
    palette: str = "viridis",
    band: int = 0,
    red: int = 0,
    green: int = 1,
    blue: int = 2,
    nodata: str = "",
) -> bytes:
    values = _as_channels_last(np.asarray(array))
    _height, _width, count = values.shape
    raw_uint8 = mode == "rgb" and values.dtype == np.uint8
    if mode == "rgb" and count >= 2:
        planes = []
        for index in (red, green, blue):
            if index >= count:
                planes.append(np.zeros(values.shape[:2], dtype=np.uint8))
                continue
            scaled, _valid = _scale_plane(values[:, :, int(index)], nodata, raw_uint8=raw_uint8)
            planes.append(scaled)
        image = Image.fromarray(np.dstack(planes), mode="RGB")
    else:
        index = int(np.clip(band, 0, count - 1))
        scaled, valid = _scale_plane(values[:, :, index], nodata, raw_uint8=False)
        rgb = _lut(palette)[scaled]
        if not valid.all():
            alpha = np.where(valid, 255, 0).astype(np.uint8)
            image = Image.fromarray(np.dstack((rgb, alpha)), mode="RGBA")
        else:
            image = Image.fromarray(rgb, mode="RGB")
    image.thumbnail((TIFF_PREVIEW_EDGE, TIFF_PREVIEW_EDGE), Image.Resampling.BOX)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


def random_palette() -> str:
    return random.choice(PALETTE_IDS)


def colorbar_png(palette: str, *, width: int = 256, height: int = 14) -> bytes:
    lut = _lut(palette)
    row = lut
    if width != lut.shape[0]:
        resized = Image.fromarray(lut[np.newaxis, :, :], mode="RGB").resize((width, 1), Image.Resampling.BILINEAR)
        row = np.asarray(resized)[0]
    image = np.repeat(row[np.newaxis, :, :], height, axis=0)
    buffer = io.BytesIO()
    Image.fromarray(image.astype(np.uint8), mode="RGB").save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


def style_notice(info: dict) -> str:
    count = int(info.get("count") or 0)
    channel_text = tr("tiff_channels_one") if count == 1 else tr("tiff_channels_many", count=count)
    mode = info.get("mode") or "palette"
    if mode == "rgb":
        red, green, blue = int(info.get("red") or 0), int(info.get("green") or 0), int(info.get("blue") or 0)
        if count > 3 and (red, green, blue) == (0, 1, 2):
            channel_text += tr("tiff_first_three")
        elif count == 2:
            channel_text += tr("tiff_both")
    else:
        palette = str(info.get("palette") or "viridis")
        label = tr(f"tiff_palette_{palette}") if palette in {*PALETTE_IDS, "random"} else palette
        band = int(info.get("band") or 0) + 1
        channel_text += f", {tr('tiff_mode_palette')} {label}, {tr('tiff_band', index=band)}"
    notice = tr(
        "tiff_stack",
        edge=TIFF_PREVIEW_EDGE,
        width=info.get("width"),
        height=info.get("height"),
        channels=channel_text,
        dtype=info.get("dtype") or "",
    )
    level = int(info.get("overview_level") or 0)
    if level > 0:
        notice += tr(
            "tiff_overview",
            level=level,
            width=info.get("overview_width"),
            height=info.get("overview_height"),
        )
    pages = int(info.get("pages") or 1)
    if pages > 1:
        notice += tr("tiff_page", pages=pages)
    return notice


def tiff_detail_rows(info: dict) -> list[tuple[str, str]]:
    overviews = info.get("overviews") or []
    overview_text = ", ".join(f"{width}×{height}" for width, height in overviews) if overviews else "—"
    if int(info.get("overview_level") or 0) > 0:
        preview = (
            f"Overview {info['overview_level']} ({info['overview_width']}×{info['overview_height']})"
        )
    else:
        preview = tr("tiff_full_res")
    if info.get("tiled"):
        layout = tr(
            "tiff_layout_tiles",
            width=info.get("tile_width") or 0,
            height=info.get("tile_height") or 0,
        )
    else:
        layout = tr("tiff_layout_strips")
    return [
        (tr("tiff_meta_size"), f"{info.get('width')} × {info.get('height')} px"),
        (tr("tiff_meta_bands"), str(info.get("count") or "")),
        (tr("tiff_meta_dtype"), str(info.get("dtype") or "")),
        (tr("tiff_meta_compression"), str(info.get("compression") or "—")),
        (tr("tiff_meta_layout"), layout),
        (tr("tiff_meta_overviews"), overview_text),
        (tr("tiff_meta_preview"), preview),
        (tr("tiff_meta_nodata"), str(info.get("nodata") or "—")),
    ]


def _apply_rendered(preview: Preview, rendered: RenderedTiff) -> None:
    preview.image = rendered.png
    preview.notice = rendered.notice
    preview.tiff_array = rendered.array
    preview.tiff_bands = rendered.bands
    preview.tiff_mode = rendered.mode
    preview.tiff_nodata = rendered.nodata
    preview.tiff_info = dict(rendered.info)
    preview.meta_rows = tiff_detail_rows(rendered.info) if rendered.info else []


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


def _overview_pages(tiff, page) -> list:
    found = []
    try:
        full_width, full_height = _page_size(page)
    except Exception:
        return []
    children = []
    subpages = getattr(page, "pages", None)
    if subpages is not None:
        try:
            children = list(subpages)
        except Exception:
            children = []
    for child in children[:_OVERVIEW_LIMIT]:
        if _is_smaller(child, full_width, full_height):
            found.append(child)
    if found:
        return found
    try:
        siblings = list(tiff.pages)[1 : 1 + _OVERVIEW_LIMIT]
    except Exception:
        siblings = []
    for child in siblings:
        try:
            subtype = int(getattr(child, "subfiletype", 0) or 0)
        except Exception:
            subtype = 0
        if subtype & 1 and _is_smaller(child, full_width, full_height):
            found.append(child)
    return found


def _is_smaller(page, full_width: int, full_height: int) -> bool:
    try:
        width, height = _page_size(page)
    except Exception:
        return False
    return width < full_width or height < full_height


def _choose_level(levels: list, *, allow_full: bool) -> int:
    def long_side(page) -> int:
        width, height = _page_size(page)
        return max(width, height)

    overview_indexes = [
        index for index in range(1, len(levels)) if _decoded_bytes(levels[index]) <= _MAX_DECODED_BYTES
    ]
    full_ok = _decoded_bytes(levels[0]) <= _MAX_DECODED_BYTES
    full_long = long_side(levels[0])
    if overview_indexes and full_long > TIFF_PREVIEW_EDGE:
        pool = overview_indexes
    elif full_ok and (allow_full or full_long <= TIFF_PREVIEW_EDGE):
        pool = [0]
    elif overview_indexes:
        pool = overview_indexes
    elif full_ok and allow_full:
        pool = [0]
    elif not allow_full:
        raise _TooLarge()
    else:
        raise _TooManyPixels()
    above = [index for index in pool if long_side(levels[index]) >= TIFF_PREVIEW_EDGE]
    if above:
        return min(above, key=lambda index: (long_side(levels[index]), index))
    return max(pool, key=lambda index: (long_side(levels[index]), -index))


def _decoded_bytes(page) -> int:
    width, height = _page_size(page)
    samples = max(1, int(getattr(page, "samplesperpixel", 1) or 1))
    dtype = getattr(page, "dtype", None)
    try:
        itemsize = 1 if dtype is None else max(1, int(np.dtype(dtype).itemsize))
    except Exception:
        itemsize = 1
    return width * height * samples * itemsize


def _page_size(page) -> tuple[int, int]:
    shape = tuple(int(value) for value in page.shape)
    if len(shape) < 2:
        raise ValueError(tr("tiff_shape", shape=shape))
    if len(shape) >= 3 and shape[0] <= 32 and shape[0] < shape[1] and shape[0] < shape[2]:
        height, width = shape[1], shape[2]
    else:
        height, width = shape[0], shape[1]
    return width, height


def _default_mode(page, bands: int) -> str:
    if bands >= 3 and _photometric_name(page) in _RGB_PHOTOMETRIC:
        return "rgb"
    return "palette"


def _photometric_name(page) -> str:
    value = getattr(page, "photometric", "")
    return str(getattr(value, "name", value)).upper()


def _nodata_text(page) -> str:
    try:
        tag = page.tags.get(42113)
    except Exception:
        return ""
    if tag is None:
        return ""
    value = getattr(tag, "value", "")
    if isinstance(value, bytes):
        value = value.split(b"\x00", 1)[0].decode("utf-8", "replace")
    elif isinstance(value, tuple) and value:
        value = value[0]
    text = str(value).strip().strip("\x00")
    if text.lower() in {"", "none"}:
        return ""
    return text


def _compression_label(page) -> str:
    value = getattr(page, "compression", "")
    name = str(getattr(value, "name", value) or "").upper()
    if not name:
        return "—"
    return _COMPRESSION_NAMES.get(name, name.replace("_", " ").title())


def _dtype_label(dtype) -> str:
    name = np.dtype(dtype).name
    return _DTYPE_NAMES.get(name, name)


def _as_channels_last(array):
    values = np.squeeze(np.asarray(array))
    if values.ndim == 2:
        return values[:, :, np.newaxis]
    if values.ndim != 3:
        raise ValueError(tr("tiff_shape", shape=tuple(np.asarray(array).shape)))
    if values.shape[0] <= 32 and values.shape[0] < values.shape[1] and values.shape[0] < values.shape[2]:
        values = np.moveaxis(values, 0, -1)
    return values


def _downsample(bands):
    height, width = bands.shape[:2]
    long_side = max(height, width)
    if long_side <= TIFF_PREVIEW_EDGE:
        return bands
    scale = TIFF_PREVIEW_EDGE / float(long_side)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    rows = np.linspace(0, height - 1, new_height).astype(np.int64)
    cols = np.linspace(0, width - 1, new_width).astype(np.int64)
    return np.ascontiguousarray(bands[rows][:, cols])


def _scale_plane(plane, nodata: str, *, raw_uint8: bool):
    if raw_uint8 and plane.dtype == np.uint8:
        valid = np.ones(plane.shape, dtype=bool)
        parsed = _parse_nodata(nodata)
        if parsed is not None and not np.isnan(parsed):
            valid = plane != np.array(parsed).astype(plane.dtype)
        return plane, valid
    data = plane.astype(np.float32, copy=False)
    valid = np.isfinite(data)
    parsed = _parse_nodata(nodata)
    if parsed is not None:
        if np.isnan(parsed):
            valid &= np.isfinite(data)
        elif plane.dtype.kind in "iu" and float(parsed).is_integer():
            valid &= plane != np.array(parsed).astype(plane.dtype)
        else:
            valid &= ~np.isclose(data, np.float32(parsed), rtol=0, atol=0)
    output = np.zeros(plane.shape, dtype=np.uint8)
    if not valid.any():
        return output, valid
    values = data[valid]
    if plane.dtype.kind in "iu":
        low, high = float(values.min()), float(values.max())
    else:
        low, high = (float(item) for item in np.percentile(values, (2, 98)))
        if high <= low:
            low, high = float(values.min()), float(values.max())
    if high <= low:
        return output, valid
    scaled = np.clip((data - low) / (high - low), 0, 1)
    scaled = np.where(valid, scaled, 0)
    return (scaled * 255).astype(np.uint8), valid


def _parse_nodata(nodata: str):
    text = (nodata or "").strip()
    if not text or text == "—":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _lut(palette: str) -> np.ndarray:
    name = palette if palette in _STOPS else random.choice(PALETTE_IDS)
    stops = _STOPS[name]
    positions = np.linspace(0, 1, len(stops))
    grid = np.linspace(0, 1, 256)
    lut = np.zeros((256, 3), dtype=np.uint8)
    for channel in range(3):
        lut[:, channel] = np.interp(grid, positions, [stop[channel] for stop in stops]).astype(np.uint8)
    return lut


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
