from s3viewer.preview import build_preview, content_type_for_save


def test_json_is_pretty_printed():
    preview = build_preview("daten/config.json", b'{"ok":true,"n":2}', content_type="application/json")
    assert preview.kind == "json"
    assert '"ok": true' in preview.text
    assert preview.filename == "config.json"


def test_xml_is_pretty_printed():
    preview = build_preview("note.xml", b"<root><item>A</item></root>", content_type="application/xml")
    assert preview.kind == "xml"
    assert "<item>A</item>" in preview.text


def test_german_csv_becomes_a_table():
    raw = "Name;Wert\nAlpha;1\nBeta;2\n".encode()
    preview = build_preview("daten/tabelle.csv", raw, content_type="text/csv")
    assert preview.kind == "csv"
    assert preview.headers == ["Name", "Wert"]
    assert preview.rows[0] == ["Alpha", "1"]
    assert preview.rows[1] == ["Beta", "2"]
    assert preview.row_numbers == [2, 3]


def test_csv_without_header_gets_generated_columns():
    preview = build_preview("zahlen.csv", b"1,2\n3,4\n")
    assert preview.headers == ["Spalte 1", "Spalte 2"]
    assert preview.rows[0] == ["1", "2"]
    assert preview.row_numbers == [1, 2]


def test_plain_text_and_empty_file():
    text = build_preview("readme.txt", b"Hallo Welt\n", content_type="text/plain")
    assert text.kind == "text"
    assert text.text == "Hallo Welt\n"
    empty = build_preview("leer.txt", b"")
    assert empty.kind == "empty"


def test_png_is_not_shown_as_text():
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    preview = build_preview("bild.png", data, content_type="image/png")
    assert preview.kind == "binary"
    assert preview.text == ""


def test_save_content_type_keeps_json_and_adds_charset():
    assert content_type_for_save("json", "application/json") == "application/json; charset=utf-8"
    assert content_type_for_save("text", "") == "text/plain; charset=utf-8"
    assert content_type_for_save("xml", "text/xml; charset=iso-8859-1") == "text/xml; charset=iso-8859-1"


def test_extensionless_text_is_previewed():
    preview = build_preview("logs/Dockerfile", b"FROM python:3.12\n")
    assert preview.kind == "text"
    assert "python" in preview.text
