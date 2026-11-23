"""Erkennt Textformate und bereitet eine lesbare Vorschau auf."""

from __future__ import annotations

from s3viewer.i18n import tr
import csv
import io
import json
from dataclasses import dataclass, field
from xml.dom import minidom

PREVIEW_BYTE_LIMIT = 1_000_000
IMAGE_PREVIEW_BYTE_LIMIT = 80 * 1024 * 1024
IMAGE_PREVIEW_EDGE = 1600
CSV_ROW_LIMIT = 2000
CSV_COLUMN_LIMIT = 40

TEXT_EXTENSIONS = {
    "txt",
    "text",
    "log",
    "md",
    "rst",
    "markdown",
    "csv",
    "tsv",
    "json",
    "geojson",
    "ndjson",
    "xml",
    "html",
    "htm",
    "xhtml",
    "css",
    "js",
    "mjs",
    "ts",
    "tsx",
    "jsx",
    "py",
    "rb",
    "go",
    "rs",
    "java",
    "kt",
    "c",
    "h",
    "cpp",
    "hpp",
    "cs",
    "php",
    "sql",
    "sh",
    "bash",
    "zsh",
    "yaml",
    "yml",
    "toml",
    "ini",
    "cfg",
    "conf",
    "config",
    "properties",
    "env",
    "svg",
    "tex",
    "r",
    "dockerfile",
}

IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "jfif",
    "gif",
    "webp",
    "bmp",
    "ico",
    "heic",
    "heif",
}

IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/x-ms-bmp",
    "image/x-icon",
    "image/vnd.microsoft.icon",
    "image/heic",
    "image/heif",
}

BINARY_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "bmp",
    "ico",
    "heic",
    "zip",
    "gz",
    "tgz",
    "bz2",
    "xz",
    "7z",
    "rar",
    "tar",
    "pdf",
    "parquet",
    "orc",
    "avro",
    "feather",
    "pkl",
    "pickle",
    "npy",
    "npz",
    "exe",
    "so",
    "dylib",
    "bin",
    "dat",
    "mp3",
    "mp4",
    "mov",
    "avi",
    "mkv",
    "webm",
    "wav",
    "flac",
    "ogg",
    "iso",
    "img",
    "qcow2",
    "sqlite",
    "db",
    "ttf",
    "otf",
    "woff",
    "woff2",
    "eot",
    "class",
    "jar",
    "war",
    "ear",
    "xls",
    "xlsx",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "ods",
    "odt",
    "odp",
}

TEXT_CONTENT_TYPES = {
    "application/json",
    "application/geo+json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/toml",
    "application/javascript",
    "application/sql",
    "application/xhtml+xml",
    "application/csv",
    "application/x-ndjson",
    "image/svg+xml",
}


@dataclass
class Preview:
    kind: str
    filename: str
    text: str = ""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    row_numbers: list[int] = field(default_factory=list)
    notice: str = ""
    truncated: bool = False
    size: int = 0
    image: bytes = b""
    content_type: str = ""
    tiff_array: object = None
    meta_rows: list[tuple[str, str]] = field(default_factory=list)
    tiff_bands: int = 0
    tiff_mode: str = ""
    tiff_nodata: str = ""
    tiff_info: dict = field(default_factory=dict)


def extension_of(key: str) -> str:
    name = key.rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def is_image(key: str, content_type: str = "") -> bool:
    if extension_of(key) in IMAGE_EXTENSIONS:
        return True
    return content_type_base(content_type) in IMAGE_CONTENT_TYPES


def decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _has_binary_null(data: bytes) -> bool:
    sample = data[:8192]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    return b"\x00" in sample


def looks_textual(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:8192]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        text = sample.decode("latin-1", errors="replace")
        printable = sum(char.isprintable() or char in "\n\r\t" for char in text)
        return printable / max(len(text), 1) > 0.90


def content_type_base(content_type: str) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


EDITABLE_KINDS = {"text", "json", "ndjson", "xml", "html", "svg", "yaml"}


def content_type_for_save(kind: str, existing: str) -> str:
    base = content_type_base(existing)
    defaults = {
        "json": "application/json",
        "ndjson": "application/x-ndjson",
        "xml": "application/xml",
        "html": "text/html",
        "svg": "image/svg+xml",
        "yaml": "application/yaml",
        "text": "text/plain",
    }
    if not base or base in {"application/octet-stream", "binary/octet-stream"}:
        base = defaults.get(kind, "text/plain")
    if "charset=" in (existing or "").lower():
        return existing
    return f"{base}; charset=utf-8"


def detect_kind(key: str, content_type: str, data: bytes) -> str:
    ext = extension_of(key)
    ctype = content_type_base(content_type)
    if ext in {"tif", "tiff"} or ctype == "image/tiff":
        return "tiff"
    if ext in IMAGE_EXTENSIONS or ctype in IMAGE_CONTENT_TYPES:
        return "image"
    if ext in BINARY_EXTENSIONS and not ctype.startswith("text/") and ctype not in TEXT_CONTENT_TYPES:
        return "binary"
    if ext in {"json", "geojson"} or ctype in {"application/json", "application/geo+json"}:
        return "json"
    if ext == "ndjson" or ctype in {"application/x-ndjson", "application/ndjson"}:
        return "ndjson"
    if ext in {"yaml", "yml"} or ctype in {"application/yaml", "application/x-yaml", "text/yaml", "text/x-yaml"}:
        return "yaml"
    if ext in {"html", "htm", "xhtml"} or ctype in {"text/html", "application/xhtml+xml"}:
        return "html"
    if ext == "svg" or ctype == "image/svg+xml":
        return "svg"
    if ext == "xml" or ctype in {"application/xml", "text/xml"}:
        return "xml"
    if ext == "csv" or ctype in {"text/csv", "application/csv"}:
        return "csv"
    if ext == "tsv" or ctype == "text/tab-separated-values":
        return "tsv"
    textual = ext in TEXT_EXTENSIONS or ctype.startswith("text/") or ctype in TEXT_CONTENT_TYPES
    if textual or looks_textual(data):
        if _has_binary_null(data) and ext not in TEXT_EXTENSIONS and not ctype.startswith("text/"):
            return "binary"
        return "text"
    return "binary"


def _build_image_preview(preview: Preview, data: bytes, *, size: int, truncated: bool) -> Preview:
    if not data:
        preview.kind = "empty"
        preview.notice = tr("empty_file")
        return preview
    if truncated or len(data) > IMAGE_PREVIEW_BYTE_LIMIT or size > IMAGE_PREVIEW_BYTE_LIMIT:
        preview.notice = tr("image_too_big", limit=IMAGE_PREVIEW_BYTE_LIMIT // (1024 * 1024))
        return preview
    try:
        png, width, height = _image_png(data)
    except (OSError, ValueError):
        preview.notice = tr("image_failed")
        return preview
    preview.image = png
    long_side = max(width, height)
    if long_side > IMAGE_PREVIEW_EDGE:
        preview.notice = tr("image_scaled", edge=IMAGE_PREVIEW_EDGE, width=width, height=height)
    return preview


def _image_png(data: bytes) -> tuple[bytes, int, int]:
    from PIL import Image, UnidentifiedImageError

    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 80_000_000
    try:
        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise ValueError(str(exc)) from exc
        with image:
            image.seek(0)
            width, height = image.size
            if image.mode in {"RGBA", "LA", "PA"}:
                frame = image.convert("RGBA")
            elif image.mode == "P":
                frame = image.convert("RGBA")
            else:
                frame = image.convert("RGB")
            frame.thumbnail((IMAGE_PREVIEW_EDGE, IMAGE_PREVIEW_EDGE), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            frame.save(buffer, format="PNG", compress_level=1)
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit
    return buffer.getvalue(), width, height


def build_preview(
    key: str,
    data: bytes,
    *,
    content_type: str = "",
    size: int | None = None,
    truncated: bool = False,
) -> Preview:
    filename = key.rsplit("/", 1)[-1] or key
    actual_size = size if size is not None else len(data)
    kind = detect_kind(key, content_type, data)
    preview = Preview(
        kind=kind,
        filename=filename,
        truncated=truncated,
        size=actual_size,
        content_type=content_type_base(content_type),
    )
    if kind == "tiff":
        from s3viewer.tiffpreview import build_tiff_preview

        return build_tiff_preview(
            key,
            data,
            content_type=content_type,
            size=actual_size,
            truncated=truncated,
        )
    if kind == "image":
        return _build_image_preview(
            preview,
            data,
            size=actual_size,
            truncated=truncated,
        )
    if kind == "binary":
        preview.notice = tr("no_text_preview")
        return preview
    if not data:
        preview.kind = "empty"
        preview.text = ""
        preview.notice = tr("empty_file")
        return preview

    text = decode_text(data)
    if truncated:
        text = _drop_partial_last_line(text)
        preview.notice = tr("preview_truncated")

    if kind == "json":
        pretty, json_notice = _pretty_json(text)
        preview.text = pretty
        preview.notice = _join_notices(preview.notice, json_notice)
        return preview
    if kind == "xml":
        pretty, xml_notice = _pretty_xml(data if not truncated else text.encode("utf-8"))
        preview.text = pretty
        preview.notice = _join_notices(preview.notice, xml_notice)
        return preview
    if kind in {"csv", "tsv"}:
        headers, rows, row_numbers, table_notice = _parse_table(text, "\t" if kind == "tsv" else None)
        if headers is None:
            preview.kind = "text"
            preview.text = text
            preview.notice = _join_notices(preview.notice, table_notice)
            return preview
        preview.text = text
        preview.headers = headers
        preview.rows = rows
        preview.row_numbers = row_numbers
        preview.notice = _join_notices(preview.notice, table_notice)
        return preview

    preview.text = text
    return preview


def _drop_partial_last_line(text: str) -> str:
    if "\n" not in text:
        return text
    head, _sep, _tail = text.rpartition("\n")
    return head + "\n"


def _pretty_json(text: str) -> tuple[str, str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text, tr("json_raw")
    return json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", ""


def _pretty_xml(data: bytes) -> tuple[str, str]:
    try:
        document = minidom.parseString(data)
        pretty = document.toprettyxml(indent="  ")
    except Exception:
        try:
            return decode_text(data), tr("xml_raw")
        except Exception:
            return data.decode("utf-8", errors="replace"), tr("xml_raw")
    lines = [line for line in pretty.splitlines() if line.strip()]
    return "\n".join(lines) + "\n", ""


def _parse_table(text: str, delimiter: str | None) -> tuple[list[str] | None, list[list[str]], list[int], str]:
    sample = text[:8192]
    if delimiter is None:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    numbered: list[tuple[int, list[str]]] = []
    limited = False
    for line_number, row in enumerate(reader, start=1):
        if len(numbered) >= CSV_ROW_LIMIT:
            limited = True
            break
        if not any(cell.strip() for cell in row):
            continue
        numbered.append((line_number, row))
    if not numbered:
        return [], [], [], ""
    width = max(len(row) for _, row in numbered)
    if width > CSV_COLUMN_LIMIT:
        return None, [], [], tr("table_too_wide")
    notice = tr("table_limited") if limited else ""
    _header_number, header = numbered[0]
    body = numbered[1:]
    if not _looks_like_header(header):
        body = numbered
        header = [tr("column", index=index + 1) for index in range(width)]
    width = max(width, len(header))
    header = header + [""] * (width - len(header))
    row_numbers = [line_number for line_number, _row in body]
    normalized = [row + [""] * (width - len(row)) for _line_number, row in body]
    return header, normalized, row_numbers, notice


def _looks_like_header(row: list[str]) -> bool:
    if not row:
        return False
    numeric = 0
    for cell in row:
        try:
            float(cell.strip().replace(",", "."))
        except ValueError:
            continue
        else:
            numeric += 1
    return numeric < len(row) / 2


def _join_notices(*parts: str) -> str:
    return " ".join(part for part in parts if part)
