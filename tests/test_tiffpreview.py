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
    assert "ersten drei" in preview.notice
    with Image.open(io.BytesIO(preview.image)) as image:
        assert image.size == (40, 64)
