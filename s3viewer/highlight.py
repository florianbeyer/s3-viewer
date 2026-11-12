"""Färbt JSON, YAML und XML in der Dateivorschau ein."""

from __future__ import annotations

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument

KEY_COLOR = "#7dd3fc"
STRING_COLOR = "#86efac"
NUMBER_COLOR = "#fdba74"
KEYWORD_COLOR = "#c4b5fd"
COMMENT_COLOR = "#94a3b8"
TAG_COLOR = "#67e8f9"
ATTRIBUTE_COLOR = "#fcd34d"
PUNCT_COLOR = "#cbd5e1"

_JSON_STRING = 1
_YAML_DQ = 1
_YAML_SQ = 2
_YAML_BLOCK = 100
_XML_TEXT = 0
_XML_COMMENT = 1
_XML_CDATA = 2
_XML_TAG = 3
_XML_DQ = 4
_XML_SQ = 5

_YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "~"}
_JSON_WORDS = ("true", "false", "null")


def highlight_language(kind: str) -> str:
    if kind in {"json", "ndjson"}:
        return "json"
    if kind == "yaml":
        return "yaml"
    if kind in {"xml", "html", "svg"}:
        return "xml"
    return ""


class PreviewHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument):
        self._language = ""
        self._formats = {
            "key": _format(KEY_COLOR),
            "string": _format(STRING_COLOR),
            "number": _format(NUMBER_COLOR),
            "keyword": _format(KEYWORD_COLOR),
            "comment": _format(COMMENT_COLOR, italic=True),
            "tag": _format(TAG_COLOR),
            "attribute": _format(ATTRIBUTE_COLOR),
            "punct": _format(PUNCT_COLOR),
        }
        super().__init__(document)

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        self._language = language or ""

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt-API
        if self._language == "json":
            self._highlight_json(text)
        elif self._language == "yaml":
            self._highlight_yaml(text)
        elif self._language == "xml":
            self._highlight_xml(text)

    def _incoming(self) -> int:
        state = self.previousBlockState()
        return 0 if state < 0 else state

    def _highlight_json(self, text: str) -> None:
        in_string = self._incoming() == _JSON_STRING
        string_start = 0
        index = 0
        limit = len(text)
        while index < limit:
            if in_string:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == '"':
                    self._format_json_string(text, string_start, index)
                    in_string = False
                    index += 1
                    continue
                index += 1
                continue
            char = text[index]
            if char == '"':
                in_string = True
                string_start = index
                index += 1
                continue
            if char in "{}[],:":
                self.setFormat(index, 1, self._formats["punct"])
                index += 1
                continue
            if char == "-" or char.isdigit():
                number_end = _json_number_end(text, index)
                if number_end is not None:
                    self.setFormat(index, number_end - index, self._formats["number"])
                    index = number_end
                    continue
            word = _keyword_at(text, index, _JSON_WORDS)
            if word:
                self.setFormat(index, len(word), self._formats["keyword"])
                index += len(word)
                continue
            index += 1
        if in_string:
            self.setFormat(string_start, limit - string_start, self._formats["string"])
            self.setCurrentBlockState(_JSON_STRING)
            return
        self.setCurrentBlockState(0)

    def _format_json_string(self, text: str, start: int, quote_index: int) -> None:
        cursor = quote_index + 1
        while cursor < len(text) and text[cursor] in " \t":
            cursor += 1
        is_key = cursor < len(text) and text[cursor] == ":"
        role = "key" if is_key else "string"
        self.setFormat(start, quote_index - start + 1, self._formats[role])

    def _highlight_yaml(self, text: str) -> None:
        state = self._incoming()
        if state >= _YAML_BLOCK:
            if _yaml_block_continues(text, state):
                self.setFormat(0, len(text), self._formats["string"])
                self.setCurrentBlockState(state)
                return
            state = 0
        if state in {_YAML_DQ, _YAML_SQ}:
            quote = '"' if state == _YAML_DQ else "'"
            end = _yaml_quote_end(text, 0, quote, opened=True)
            if end is None:
                self.setFormat(0, len(text), self._formats["string"])
                self.setCurrentBlockState(state)
                return
            self.setFormat(0, end, self._formats["string"])
            self._highlight_yaml_from(text, end, in_value=True)
            return
        self._highlight_yaml_from(text, 0, in_value=False)

    def _highlight_yaml_from(self, text: str, index: int, in_value: bool) -> None:
        limit = len(text)
        if not in_value:
            index = _skip_spaces(text, index)
            if index >= limit:
                self.setCurrentBlockState(0)
                return
            if text[index] == "#":
                self.setFormat(index, limit - index, self._formats["comment"])
                self.setCurrentBlockState(0)
                return
            if text.startswith(("---", "..."), index) and _boundary(text, index + 3):
                self.setFormat(index, 3, self._formats["keyword"])
                index = _skip_spaces(text, index + 3)
            if index < limit and text[index] == "-" and _boundary(text, index + 1):
                self.setFormat(index, 1, self._formats["punct"])
                index = _skip_spaces(text, index + 1)
            colon = _yaml_key_colon(text, index)
            if colon is not None:
                self.setFormat(index, colon - index, self._formats["key"])
                self.setFormat(colon, 1, self._formats["punct"])
                index = colon + 1
        self._highlight_yaml_value(text, index)

    def _highlight_yaml_value(self, text: str, index: int) -> None:
        limit = len(text)
        while index < limit:
            char = text[index]
            if char in " \t":
                index += 1
                continue
            if char == "#":
                self.setFormat(index, limit - index, self._formats["comment"])
                self.setCurrentBlockState(0)
                return
            if char in "[]{},":
                self.setFormat(index, 1, self._formats["punct"])
                index += 1
                continue
            if char in "\"'":
                end = _yaml_quote_end(text, index, char, opened=False)
                if end is None:
                    self.setFormat(index, limit - index, self._formats["string"])
                    self.setCurrentBlockState(_YAML_DQ if char == '"' else _YAML_SQ)
                    return
                self.setFormat(index, end - index, self._formats["string"])
                index = end
                continue
            if char in "&*":
                end = index + 1
                while end < limit and (text[end].isalnum() or text[end] in "_-"):
                    end += 1
                self.setFormat(index, end - index, self._formats["keyword"])
                index = end
                continue
            end = index
            while end < limit and text[end] not in " \t#[]{},":
                end += 1
            token = text[index:end]
            if _is_block_scalar(token):
                self.setFormat(index, end - index, self._formats["punct"])
                cursor = _skip_spaces(text, end)
                if cursor < limit and text[cursor] == "#":
                    self.setFormat(cursor, limit - cursor, self._formats["comment"])
                self.setCurrentBlockState(_YAML_BLOCK + _indent(text))
                return
            if _is_number(token):
                role = "number"
            elif token.lower() in _YAML_WORDS:
                role = "keyword"
            else:
                role = "string"
            self.setFormat(index, end - index, self._formats[role])
            index = end
        self.setCurrentBlockState(0)

    def _highlight_xml(self, text: str) -> None:
        state = self._incoming()
        index = 0
        limit = len(text)
        while index < limit:
            if state == _XML_COMMENT:
                end = text.find("-->", index)
                if end < 0:
                    self.setFormat(index, limit - index, self._formats["comment"])
                    self.setCurrentBlockState(_XML_COMMENT)
                    return
                self.setFormat(index, end + 3 - index, self._formats["comment"])
                index = end + 3
                state = _XML_TEXT
                continue
            if state == _XML_CDATA:
                end = text.find("]]>", index)
                if end < 0:
                    self.setFormat(index, limit - index, self._formats["string"])
                    self.setCurrentBlockState(_XML_CDATA)
                    return
                self.setFormat(index, end - index, self._formats["string"])
                self.setFormat(end, 3, self._formats["punct"])
                index = end + 3
                state = _XML_TEXT
                continue
            if state in {_XML_DQ, _XML_SQ}:
                quote = '"' if state == _XML_DQ else "'"
                end = text.find(quote, index)
                if end < 0:
                    self.setFormat(index, limit - index, self._formats["string"])
                    self.setCurrentBlockState(state)
                    return
                self.setFormat(index, end + 1 - index, self._formats["string"])
                index = end + 1
                state = _XML_TAG
                continue
            if state == _XML_TAG:
                index, state = self._xml_inside_tag(text, index)
                if index >= limit:
                    self.setCurrentBlockState(state)
                    return
                continue
            if text.startswith("<!--", index):
                state = _XML_COMMENT
                continue
            if text.startswith("<![CDATA[", index):
                self.setFormat(index, 9, self._formats["punct"])
                index += 9
                state = _XML_CDATA
                continue
            if text.startswith("<?", index):
                self.setFormat(index, 2, self._formats["punct"])
                index += 2
                index = self._paint_xml_name(text, index)
                state = _XML_TAG
                continue
            if text.startswith("<!", index):
                end = text.find(">", index)
                if end < 0:
                    self.setFormat(index, limit - index, self._formats["keyword"])
                    self.setCurrentBlockState(_XML_TAG)
                    return
                self.setFormat(index, end + 1 - index, self._formats["keyword"])
                index = end + 1
                continue
            if text[index] == "<":
                index = self._paint_xml_open(text, index)
                state = _XML_TAG
                continue
            index += 1
        self.setCurrentBlockState(0 if state == _XML_TEXT else state)

    def _paint_xml_open(self, text: str, index: int) -> int:
        self.setFormat(index, 1, self._formats["punct"])
        index += 1
        if index < len(text) and text[index] == "/":
            self.setFormat(index, 1, self._formats["punct"])
            index += 1
        return self._paint_xml_name(text, index)

    def _paint_xml_name(self, text: str, index: int) -> int:
        start = index
        while index < len(text) and (text[index].isalnum() or text[index] in ":-_."):
            index += 1
        if index > start:
            self.setFormat(start, index - start, self._formats["tag"])
        return index

    def _xml_inside_tag(self, text: str, index: int) -> tuple[int, int]:
        limit = len(text)
        while index < limit:
            char = text[index]
            if char in " \t\r":
                index += 1
                continue
            if char == "?" and index + 1 < limit and text[index + 1] == ">":
                self.setFormat(index, 2, self._formats["punct"])
                return index + 2, _XML_TEXT
            if char == ">":
                self.setFormat(index, 1, self._formats["punct"])
                return index + 1, _XML_TEXT
            if char == "/" and index + 1 < limit and text[index + 1] == ">":
                self.setFormat(index, 2, self._formats["punct"])
                return index + 2, _XML_TEXT
            if char in "\"'":
                end = text.find(char, index + 1)
                state = _XML_DQ if char == '"' else _XML_SQ
                if end < 0:
                    self.setFormat(index, limit - index, self._formats["string"])
                    return limit, state
                self.setFormat(index, end + 1 - index, self._formats["string"])
                index = end + 1
                continue
            if char == "=":
                self.setFormat(index, 1, self._formats["punct"])
                index += 1
                continue
            if char.isalpha() or char in "_:":
                start = index
                index += 1
                while index < limit and (text[index].isalnum() or text[index] in ":-_."):
                    index += 1
                self.setFormat(start, index - start, self._formats["attribute"])
                continue
            index += 1
        return index, _XML_TAG


def _format(color: str, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if italic:
        fmt.setFontItalic(True)
    return fmt


def _boundary(text: str, index: int) -> bool:
    return index >= len(text) or not (text[index].isalnum() or text[index] == "_")


def _keyword_at(text: str, index: int, words: tuple[str, ...]) -> str | None:
    for word in words:
        if text.startswith(word, index) and _boundary(text, index + len(word)):
            return word
    return None


def _json_number_end(text: str, index: int) -> int | None:
    cursor = index
    if text[cursor] == "-":
        cursor += 1
    if cursor >= len(text) or not text[cursor].isdigit():
        return None
    while cursor < len(text) and text[cursor].isdigit():
        cursor += 1
    if cursor < len(text) and text[cursor] == ".":
        cursor += 1
        while cursor < len(text) and text[cursor].isdigit():
            cursor += 1
    if cursor < len(text) and text[cursor] in "eE":
        exponent = cursor + 1
        if exponent < len(text) and text[exponent] in "+-":
            exponent += 1
        if exponent < len(text) and text[exponent].isdigit():
            cursor = exponent + 1
            while cursor < len(text) and text[cursor].isdigit():
                cursor += 1
    return cursor


def _skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t":
        index += 1
    return index


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip(" "))


def _yaml_block_continues(text: str, state: int) -> bool:
    if text.strip() == "":
        return True
    return _indent(text) > state - _YAML_BLOCK


def _yaml_key_colon(text: str, index: int) -> int | None:
    if index >= len(text) or text[index] in "#[]{},&*!|>%@`":
        return None
    if text[index] in "\"'":
        end = _yaml_quote_end(text, index, text[index], opened=False)
        if end is None:
            return None
        cursor = _skip_spaces(text, end)
        if cursor < len(text) and text[cursor] == ":" and _colon_ends_key(text, cursor):
            return cursor
        return None
    cursor = index
    while cursor < len(text):
        if text[cursor] == "#":
            return None
        if text[cursor] == ":" and _colon_ends_key(text, cursor):
            return cursor
        if text[cursor] == ":":
            return None
        cursor += 1
    return None


def _colon_ends_key(text: str, index: int) -> bool:
    next_index = index + 1
    return next_index >= len(text) or text[next_index] in " \t"


def _yaml_quote_end(text: str, index: int, quote: str, opened: bool) -> int | None:
    cursor = index if opened else index + 1
    limit = len(text)
    while cursor < limit:
        if quote == "'" and text.startswith("''", cursor):
            cursor += 2
            continue
        if quote == '"' and text[cursor] == "\\":
            cursor += 2
            continue
        if text[cursor] == quote:
            return cursor + 1
        cursor += 1
    return None


def _is_block_scalar(token: str) -> bool:
    if not token or token[0] not in "|>":
        return False
    rest = token[1:]
    if rest[:1] in "+-":
        rest = rest[1:]
    return rest.isdigit() or rest == ""


def _is_number(token: str) -> bool:
    if token.lower() in {"inf", "-inf", "+inf", ".inf", "-.inf", "+.inf", "nan", ".nan"}:
        return True
    try:
        float(token)
    except ValueError:
        return False
    return True
