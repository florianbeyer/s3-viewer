from PySide6.QtGui import QTextDocument

from s3viewer.highlight import (
    ATTRIBUTE_COLOR,
    COMMENT_COLOR,
    KEY_COLOR,
    KEYWORD_COLOR,
    NUMBER_COLOR,
    PreviewHighlighter,
    STRING_COLOR,
    TAG_COLOR,
)
from s3viewer.preview import build_preview


def test_json_highlights_keys_strings_numbers_and_keywords(qapp):
    text = '{\n  "ok": true,\n  "n": 2,\n  "name": "A"\n}\n'
    groups = _color_groups("json", text)
    assert '"ok"' in groups[KEY_COLOR]
    assert '"name"' in groups[KEY_COLOR]
    assert "true" in groups[KEYWORD_COLOR]
    assert "2" in groups[NUMBER_COLOR]
    assert '"A"' in groups[STRING_COLOR]


def test_json_string_can_span_lines(qapp):
    groups = _color_groups("json", '{\n  "a": "hello\nworld",\n  "b": 1\n}\n')
    assert "hello" in groups[STRING_COLOR]
    assert "world" in groups[STRING_COLOR]
    assert '"b"' in groups[KEY_COLOR]


def test_yaml_highlights_structure(qapp):
    text = '# kommentar\nname: Beispiel\ncount: 3\nenabled: true\nnote: "mit: doppelpunkt"\n'
    groups = _color_groups("yaml", text)
    assert "kommentar" in groups[COMMENT_COLOR]
    assert "name" in groups[KEY_COLOR]
    assert "count" in groups[KEY_COLOR]
    assert "Beispiel" in groups[STRING_COLOR]
    assert "3" in groups[NUMBER_COLOR]
    assert "true" in groups[KEYWORD_COLOR]
    assert "mit: doppelpunkt" in groups[STRING_COLOR]
    assert "#" not in groups[STRING_COLOR]


def test_yaml_block_scalar_stops_at_the_next_key(qapp):
    groups = _color_groups("yaml", "text: |\n  zeile\nnext: 1\n")
    assert "zeile" in groups[STRING_COLOR]
    assert "next" in groups[KEY_COLOR]
    assert "1" in groups[NUMBER_COLOR]


def test_xml_highlights_tags_attributes_and_comments(qapp):
    text = '<root>\n  <item id="a">Text</item>\n  <!-- note -->\n</root>\n'
    groups = _color_groups("xml", text)
    assert "item" in groups[TAG_COLOR]
    assert "id" in groups[ATTRIBUTE_COLOR]
    assert '"a"' in groups[STRING_COLOR]
    assert "note" in groups[COMMENT_COLOR]
    assert "Text" not in groups.get(TAG_COLOR, "")


def test_xml_attributes_can_span_lines(qapp):
    groups = _color_groups("xml", '<item\n  id="a">\n')
    assert "item" in groups[TAG_COLOR]
    assert "id" in groups[ATTRIBUTE_COLOR]
    assert '"a"' in groups[STRING_COLOR]


def test_plain_text_stays_uncolored(qapp):
    assert _color_groups("", "name: alpha\n") == {}


def test_yaml_html_and_svg_are_recognized():
    assert build_preview("app.yaml", b"a: 1\n").kind == "yaml"
    assert build_preview("page.html", b"<p>Hi</p>").kind == "html"
    svg = build_preview("icon.svg", b"<svg></svg>")
    assert svg.kind == "svg"
    assert "<svg>" in svg.text
    events = build_preview("events.ndjson", b'{"a":1}\n{"a":2}\n')
    assert events.kind == "ndjson"
    assert "formatiert" not in events.notice


def _color_groups(language: str, text: str) -> dict[str, str]:
    document = QTextDocument()
    highlighter = PreviewHighlighter(document)
    highlighter.set_language(language)
    document.setPlainText(text)
    highlighter.rehighlight()
    return _groups_in_document(document)


def _groups_in_document(document: QTextDocument) -> dict[str, str]:
    groups: dict[str, str] = {}
    block = document.begin()
    while block.isValid():
        layout = block.layout()
        if layout is None:
            block = block.next()
            continue
        for fmt_range in layout.formats():
            color = fmt_range.format.foreground().color()
            if not color.isValid():
                continue
            snippet = block.text()[fmt_range.start : fmt_range.start + fmt_range.length]
            key = color.name().lower()
            groups[key] = groups.get(key, "") + snippet
        block = block.next()
    return groups
