import io

from PIL import Image

from s3viewer.preview import build_preview
from s3viewer.tiffpreview import TIFF_PREVIEW_EDGE


def test_tiff_preview_is_coarse_and_keeps_the_shape():
    data = _tiff(width=900, height=300)
    preview = build_preview("scan.tiff", data, content_type="image/tiff", size=len(data))
    assert preview.kind == "tiff"
    assert preview.image.startswith(b"\x89PNG\r\n\x1a\n")
    assert "900×300" in preview.notice
    assert "Grobe Vorschau" in preview.notice
    with Image.open(io.BytesIO(preview.image)) as image:
        assert image.width <= TIFF_PREVIEW_EDGE
        assert image.height <= TIFF_PREVIEW_EDGE
        assert image.width > image.height


def test_multipage_tiff_mentions_the_first_page():
    first = Image.new("L", (40, 20), 20)
    second = Image.new("L", (40, 20), 220)
    buffer = io.BytesIO()
    first.save(buffer, format="TIFF", save_all=True, append_images=[second])
    preview = build_preview("stapel.tif", buffer.getvalue(), content_type="image/tiff")
    assert "Seite 1 von 2" in preview.notice
    assert preview.image.startswith(b"\x89PNG\r\n\x1a\n")


def test_large_tiff_is_not_decoded():
    preview = build_preview(
        "gross.tiff",
        b"II*\x00not-a-real-tiff",
        content_type="image/tiff",
        size=80 * 1024 * 1024,
        truncated=True,
    )
    assert preview.kind == "tiff"
    assert preview.image == b""
    assert "heruntergeladen" in preview.notice


def _tiff(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), (20, 80, 160))
    for x in range(0, width, 40):
        for y in range(height):
            image.putpixel((x, y), (240, 200, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="TIFF")
    return buffer.getvalue()


def test_seven_band_float_stack_is_previewed():
    import numpy as np
    import tifffile

    array = np.zeros((64, 40, 7), dtype=np.float32)
    array[:, :, 0] = np.linspace(-2, 2, 64)[:, None]
    array[:, :, 1] = 15
    array[:, :, 2] = np.linspace(0, 40, 40)[None, :]
    buffer = io.BytesIO()
    tifffile.imwrite(
        buffer,
        array,
        photometric="minisblack",
        planarconfig="contig",
        compression="lzw",
    )
    preview = build_preview("tile_stack.tif", buffer.getvalue(), content_type="binary/octet-stream")
    assert preview.image.startswith(b"\x89PNG\r\n\x1a\n")
    assert "7 Kanäle" in preview.notice
    assert "Farbskala" in preview.notice
    assert "Viridis" in preview.notice
    assert "ersten drei" not in preview.notice
    with Image.open(io.BytesIO(preview.image)) as image:
        assert image.size == (40, 64)
        pixels = np.asarray(image)
        assert (pixels[:, :, 0] != pixels[:, :, 2]).any()
    labels = dict(preview.meta_rows)
    assert labels["Größe"] == "40 × 64 px"
    assert labels["Bänder"] == "7"
    assert labels["Datentyp"] == "Float32"


def test_preview_limit_is_500_megabytes():
    from s3viewer.tiffpreview import TIFF_PREVIEW_BYTE_LIMIT

    assert TIFF_PREVIEW_BYTE_LIMIT == 500 * 1024 * 1024


def test_cog_preview_uses_an_overview_and_shows_metadata():
    import numpy as np
    import tifffile

    from s3viewer.tiffpreview import TIFF_PREVIEW_EDGE

    full = np.arange(800 * 1200, dtype=np.uint8).reshape(800, 1200)
    overview = full[::8, ::8]
    buffer = io.BytesIO()
    with tifffile.TiffWriter(buffer) as writer:
        writer.write(
            full,
            tile=(128, 128),
            photometric="minisblack",
            compression="zlib",
            subifds=1,
            extratags=[(42113, "s", None, "255", True)],
        )
        writer.write(overview, tile=(128, 128), photometric="minisblack", compression="zlib", subfiletype=1)
    preview = build_preview("karte.tif", buffer.getvalue(), content_type="image/tiff")
    assert "Overview 1" in preview.notice
    assert f"{overview.shape[1]}×{overview.shape[0]}" in preview.notice
    labels = dict(preview.meta_rows)
    assert labels["Größe"] == "1200 × 800 px"
    assert labels["NoData"] == "255"
    assert "Kacheln" in labels["Layout"]
    assert "Deflate" in labels["Kompression"]
    with Image.open(io.BytesIO(preview.image)) as image:
        assert max(image.size) <= TIFF_PREVIEW_EDGE
        assert image.size != (1200, 800)


def test_large_non_cog_is_not_read_from_ranges():
    from s3viewer.tiffpreview import RangeReader, build_tiff_from_source

    data = _tiff(width=900, height=300)
    reader = RangeReader(lambda start, length: data[start : start + length], len(data), block=4096)
    preview = build_tiff_from_source("gross.tif", reader, size=600 * 1024 * 1024, allow_full=False)
    assert preview.image == b""
    assert "heruntergeladen" in preview.notice


def test_cog_range_reader_does_not_read_the_whole_file():
    import numpy as np
    import tifffile

    from s3viewer.tiffpreview import RangeReader, build_tiff_from_source

    rng = np.random.default_rng(0)
    values = rng.integers(0, 256, size=(1600, 2000), dtype=np.uint8)
    overview = values[::16, ::16]
    buffer = io.BytesIO()
    with tifffile.TiffWriter(buffer) as writer:
        writer.write(values, tile=(256, 256), photometric="minisblack", compression="zlib", subifds=1)
        writer.write(overview, tile=(256, 256), photometric="minisblack", compression="zlib", subfiletype=1)
    blob = buffer.getvalue()
    read = {"n": 0}

    def read_range(start: int, length: int) -> bytes:
        read["n"] += length
        return blob[start : start + length]

    preview = build_tiff_from_source(
        "gross.tif",
        RangeReader(read_range, len(blob), block=8192),
        size=len(blob),
        allow_full=False,
    )
    assert preview.image.startswith(b"\x89PNG\r\n\x1a\n")
    assert "Overview 1" in preview.notice
    assert read["n"] < len(blob) * 0.5


def test_colormap_and_rgb_bands_are_adjustable():
    import numpy as np

    from s3viewer.tiffpreview import render_styled, style_notice

    array = np.zeros((8, 6, 3), dtype=np.float32)
    array[:, :, 0] = np.linspace(0, 1, 8)[:, None]
    array[:, :, 1] = 0.2
    array[:, :, 2] = np.linspace(1, 0, 6)[None, :]
    viridis = render_styled(array, mode="palette", palette="viridis", band=0)
    ryg = render_styled(array, mode="palette", palette="ryg", band=0)
    assert viridis != ryg
    natural = render_styled(array, mode="rgb", red=0, green=1, blue=2)
    swapped = render_styled(array, mode="rgb", red=2, green=1, blue=0)
    assert natural != swapped
    notice = style_notice(
        {
            "width": 6,
            "height": 8,
            "count": 7,
            "dtype": "Float32",
            "mode": "rgb",
            "palette": "viridis",
            "band": 0,
            "red": 0,
            "green": 1,
            "blue": 2,
            "pages": 1,
            "overview_level": 0,
        }
    )
    assert "7 Kanäle" in notice
    assert "ersten drei" in notice
