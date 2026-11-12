from datetime import datetime, timezone

from botocore.exceptions import ClientError
from PySide6.QtCore import Qt

from s3viewer.highlight import KEY_COLOR, KEYWORD_COLOR
from s3viewer.i18n import language, set_language
from s3viewer.s3 import BucketInfo, Connected, ConnectionSettings, FetchedObject, ObjectEntry
from s3viewer.window import MainWindow


class FakeSession:
    def __init__(self, settings: ConnectionSettings | None = None):
        self.settings = settings or ConnectionSettings(
            endpoint_url="https://s3.example.com",
            access_key="ak",
            secret_key="sk",
        )
        self.closed = False

    def establish(self) -> Connected:
        if self.settings.direct_bucket == "kaputt":
            raise ClientError(
                {
                    "Error": {"Code": "SignatureDoesNotMatch", "Message": "no"},
                    "ResponseMetadata": {"HTTPStatusCode": 403},
                },
                "ListBuckets",
            )
        buckets = [BucketInfo("projekt"), BucketInfo("archiv")]
        if self.settings.direct_bucket and self.settings.direct_bucket not in {bucket.name for bucket in buckets}:
            buckets.append(BucketInfo(self.settings.direct_bucket))
        return Connected(buckets=buckets)

    def list_buckets(self):
        return self.establish().buckets

    def list_folder(self, bucket: str, prefix: str):
        prefix = prefix or ""
        if bucket != "projekt":
            return [], False
        if prefix in {"", "/"}:
            return [
                ObjectEntry("readme.txt", "readme.txt", False, 11, datetime(2024, 5, 1, tzinfo=timezone.utc)),
                ObjectEntry("daten", "daten/", True),
            ], False
        if prefix == "daten/":
            return [
                ObjectEntry("tabelle.csv", "daten/tabelle.csv", False, 24, datetime(2024, 5, 2, tzinfo=timezone.utc)),
                ObjectEntry("config.json", "daten/config.json", False, 16, datetime(2024, 5, 2, tzinfo=timezone.utc)),
                ObjectEntry("bild.png", "daten/bild.png", False, 32, datetime(2024, 5, 2, tzinfo=timezone.utc)),
            ], False
        return [], False

    def fetch(self, _bucket: str, key: str, _limit: int = 1_000_000) -> FetchedObject:
        bodies = {
            "readme.txt": (b"Hallo Welt\n", "text/plain"),
            "daten/tabelle.csv": (b"Name;Wert\nAlpha;1\nBeta;2\n", "text/csv"),
            "daten/config.json": (b'{"ok": true, "n": 2}', "application/json"),
            "daten/bild.png": (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png"),
        }
        data, content_type = bodies[key]
        return FetchedObject(data=data, size=len(data), content_type=content_type, truncated=False)

    def download(self, bucket: str, key: str, destination: str, progress=None, cancel=None) -> None:
        if cancel is not None and getattr(cancel, "cancelled", False):
            from s3viewer.s3 import DownloadCancelled

            raise DownloadCancelled()
        data = self.fetch(bucket, key).data
        if progress is not None:
            progress(len(data))
        with open(destination, "wb") as handle:
            handle.write(data)

    def put_text(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self.saved = (bucket, key, data, content_type)

    def close(self) -> None:
        self.closed = True


def test_browse_buckets_folders_and_preview_files(qtbot, tmp_path):
    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("ak")
    window.secret_key.setText("sk")

    qtbot.mouseClick(window.connect_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.bucket_list.count() == 2, timeout=4000)
    assert _bucket_names(window) == ["archiv", "projekt"]

    _click_bucket(qtbot, window, "projekt")
    qtbot.waitUntil(lambda: _object_names(window) == ["daten", "readme.txt"], timeout=4000)

    _click_object(qtbot, window, "readme.txt")
    qtbot.waitUntil(lambda: "Hallo Welt" in window.preview_text.toPlainText(), timeout=4000)
    assert window.preview_badge.text() == "Text"

    _click_object(qtbot, window, "daten")
    qtbot.waitUntil(lambda: "config.json" in _object_names(window), timeout=4000)
    assert _object_names(window)[0] == ".."

    _click_object(qtbot, window, "config.json")
    qtbot.waitUntil(lambda: '"ok": true' in window.preview_text.toPlainText(), timeout=4000)
    assert window.preview_badge.text() == "JSON"
    assert window.preview_text.isReadOnly() is False
    assert window.preview_text.line_number_width() > 8
    assert window.save_edit_button.isVisible()
    colors = _texts_by_color(window.preview_text)
    assert "ok" in colors.get(KEY_COLOR, "")
    assert "true" in colors.get(KEYWORD_COLOR, "")

    _click_object(qtbot, window, "tabelle.csv")
    qtbot.waitUntil(lambda: window.preview_table.columnCount() == 2, timeout=4000)
    assert window.preview_table.horizontalHeaderItem(0).text() == "Name"
    assert window.preview_table.item(0, 0).text() == "Alpha"
    assert window.preview_table.item(1, 1).text() == "2"
    assert window.preview_table.verticalHeaderItem(0).text() == "2"
    assert window.preview_table.verticalHeaderItem(1).text() == "3"
    assert window.preview_badge.text() == "CSV"

    _click_object(qtbot, window, "bild.png")
    qtbot.waitUntil(lambda: "keine Textvorschau" in window.preview_message.text(), timeout=4000)

    qtbot.mouseClick(window.up_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "readme.txt" in _object_names(window), timeout=4000)
    assert ".." not in _object_names(window)


def test_bucket_and_file_name_filters(qtbot, tmp_path):
    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("ak")
    window.secret_key.setText("sk")
    qtbot.mouseClick(window.connect_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.bucket_list.count() == 2, timeout=4000)

    window.bucket_filter.setFocus()
    qtbot.keyClicks(window.bucket_filter, "arc")
    assert _visible_buckets(window) == ["archiv"]
    assert window.bucket_count.text() == "1 / 2"

    window.bucket_filter.clear()
    assert _visible_buckets(window) == ["archiv", "projekt"]

    window.bucket_filter.setText("pro")
    _click_bucket(qtbot, window, "projekt")
    qtbot.waitUntil(lambda: _object_names(window) == ["daten", "readme.txt"], timeout=4000)

    window.filter_edit.setFocus()
    qtbot.keyClicks(window.filter_edit, "read")
    assert _visible_objects(window) == ["readme.txt"]
    assert window.file_count.text() == "1 / 2"

    window.filter_edit.clear()
    _click_object(qtbot, window, "daten")
    qtbot.waitUntil(lambda: "config.json" in _object_names(window), timeout=4000)
    assert window.filter_edit.text() == ""

    qtbot.keyClicks(window.filter_edit, "json")
    assert _visible_objects(window) == ["..", "config.json"]
    assert window.object_table.isRowHidden(_row_named(window, "tabelle.csv"))
    assert window.object_table.isRowHidden(_row_named(window, "bild.png"))


def test_several_files_can_be_selected_for_download(qtbot, tmp_path):
    from PySide6.QtCore import QItemSelectionModel

    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("ak")
    window.secret_key.setText("sk")
    qtbot.mouseClick(window.connect_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.bucket_list.count() == 2, timeout=4000)
    _click_bucket(qtbot, window, "projekt")
    qtbot.waitUntil(lambda: _object_names(window) == ["daten", "readme.txt"], timeout=4000)
    assert window.upload_button.isEnabled() is True
    assert window.upload_folder_button.isEnabled() is True
    assert window.new_folder_button.isEnabled() is True
    assert window.save_button.isEnabled() is False
    assert window.delete_button.isEnabled() is False

    _select_rows(window, ["daten", "readme.txt"])
    assert {entry.name for entry in window._selected_entries()} == {"daten", "readme.txt"}
    assert window.delete_button.isEnabled() is True
    assert window.save_button.isEnabled() is True

    window.filter_edit.setText("read")
    window.object_table.setFocus()
    qtbot.keyClick(window.object_table, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert {entry.name for entry in window._selected_entries()} == {"readme.txt"}


def test_selected_files_and_folders_can_be_deleted(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    class Session(FakeSession):
        def list_object_keys(self, bucket, prefix):
            assert bucket == "projekt"
            assert prefix == "daten/"
            return ["daten/tabelle.csv", "daten/leer/"], False

        def delete_keys(self, bucket, keys, progress=None):
            self.deleted = (bucket, list(keys))
            if progress is not None:
                progress(len(keys))
            return len(keys)

    window = MainWindow(session_factory=Session, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("ak")
    window.secret_key.setText("sk")
    qtbot.mouseClick(window.connect_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.bucket_list.count() == 2, timeout=4000)
    _click_bucket(qtbot, window, "projekt")
    qtbot.waitUntil(lambda: _object_names(window) == ["daten", "readme.txt"], timeout=4000)
    _select_rows(window, ["daten", "readme.txt"])

    monkeypatch.setattr(
        "s3viewer.window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.No,
    )
    window._delete_selected()
    assert not hasattr(window.session, "deleted")

    monkeypatch.setattr(
        "s3viewer.window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    window._delete_selected()
    qtbot.waitUntil(lambda: getattr(window.session, "deleted", None) is not None, timeout=4000)
    bucket, keys = window.session.deleted
    assert bucket == "projekt"
    assert set(keys) == {"daten/tabelle.csv", "daten/leer/", "daten/", "readme.txt"}


def test_tiff_file_shows_a_coarse_preview(qtbot, tmp_path):
    import io

    from PIL import Image

    picture = Image.new("RGB", (900, 300), (20, 80, 160))
    buffer = io.BytesIO()
    picture.save(buffer, format="TIFF")
    payload = buffer.getvalue()

    class Session(FakeSession):
        def list_folder(self, bucket: str, prefix: str):
            entries, capped = super().list_folder(bucket, prefix)
            if bucket == "projekt" and (prefix or "") in {"", "/"}:
                entries = [
                    *entries,
                    ObjectEntry(
                        "scan.tiff",
                        "scan.tiff",
                        False,
                        len(payload),
                        datetime(2024, 5, 3, tzinfo=timezone.utc),
                    ),
                ]
            return entries, capped

        def fetch(self, bucket: str, key: str, limit: int = 1_000_000):
            if key == "scan.tiff":
                return FetchedObject(data=payload, size=len(payload), content_type="image/tiff", truncated=False)
            return super().fetch(bucket, key, limit)

    window = MainWindow(session_factory=Session, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("ak")
    window.secret_key.setText("sk")
    qtbot.mouseClick(window.connect_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.bucket_list.count() == 2, timeout=4000)
    _click_bucket(qtbot, window, "projekt")
    qtbot.waitUntil(lambda: "scan.tiff" in _object_names(window), timeout=4000)
    _click_object(qtbot, window, "scan.tiff")
    qtbot.waitUntil(lambda: not window.preview_image._source.isNull(), timeout=4000)
    assert window.preview_badge.text() == "TIFF"
    assert "Grobe Vorschau" in window.preview_notice.text()
    assert window.preview_stack.currentWidget() is window.preview_image_page
    assert window.preview_image._source.width() <= 640


def test_text_preview_can_be_edited_and_written_back(qtbot, tmp_path):
    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("ak")
    window.secret_key.setText("sk")
    qtbot.mouseClick(window.connect_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.bucket_list.count() == 2, timeout=4000)
    _click_bucket(qtbot, window, "projekt")
    qtbot.waitUntil(lambda: "readme.txt" in _object_names(window), timeout=4000)
    _click_object(qtbot, window, "readme.txt")
    qtbot.waitUntil(lambda: "Hallo Welt" in window.preview_text.toPlainText(), timeout=4000)
    window.preview_text.appendPlainText("!")
    assert window.save_edit_button.isEnabled()
    qtbot.mouseClick(window.save_edit_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: getattr(window.session, "saved", None) is not None, timeout=4000)
    bucket, key, data, content_type = window.session.saved
    assert bucket == "projekt"
    assert key == "readme.txt"
    assert b"!" in data
    assert "utf-8" in content_type
    qtbot.waitUntil(lambda: window.save_edit_button.isEnabled() is False, timeout=4000)


def test_connection_panel_folds_up(qtbot, tmp_path):
    settings_path = tmp_path / "settings.ini"
    window = MainWindow(session_factory=FakeSession, settings_path=str(settings_path))
    qtbot.addWidget(window)
    window.show()
    assert window.upload_button.isEnabled() is False
    assert window.new_folder_button.isEnabled() is False
    window.endpoint.setText("https://s3.example.com/bucket")
    assert window.connection_body.isVisible()
    assert window.endpoint.isVisible()

    qtbot.mouseClick(window.connection_toggle, Qt.MouseButton.LeftButton)
    assert window.connection_body.isVisible() is False
    assert window.endpoint.isVisible() is False
    assert window.connect_button.isVisible()
    assert window.connect_button.text() == ""
    assert window.save_profile_button.isVisible() is False
    assert window.delete_profile_button.isVisible() is False
    assert window.connection_summary.text() == "s3.example.com"
    assert window.connection_toggle.text() == "▼"

    qtbot.mouseClick(window.connection_toggle, Qt.MouseButton.LeftButton)
    assert window.connection_body.isVisible()
    assert window.connection_toggle.text() == "▲"
    assert window.save_profile_button.isVisible()
    assert window.delete_profile_button.isVisible()
    assert window.save_profile_button.text() == "Speichern"
    assert window.delete_profile_button.text() == "Entfernen"
    assert window.connect_button.text() == "Verbinden"
    assert window.disconnect_button.text() == "Trennen"

    qtbot.mouseClick(window.connection_toggle, Qt.MouseButton.LeftButton)
    window._save_settings()
    restored = MainWindow(session_factory=FakeSession, settings_path=str(settings_path))
    qtbot.addWidget(restored)
    assert restored.connection_body.isVisible() is False
    assert restored.endpoint.text() == "https://s3.example.com/bucket"


def _select_rows(window: MainWindow, names: list[str]) -> None:
    from PySide6.QtCore import QItemSelectionModel

    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    selection = window.object_table.selectionModel()
    selection.clearSelection()
    for name in names:
        index = window.object_table.model().index(_row_named(window, name), 0)
        selection.select(index, flags)


def test_connection_error_is_shown_without_a_dialog(qtbot, tmp_path):
    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("ak")
    window.secret_key.setText("sk")
    window.bucket_edit.setText("kaputt")
    qtbot.mouseClick(window.connect_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Signatur" in window.banner.text(), timeout=4000)
    assert window.session is None


def test_language_and_dark_mode_switch(qtbot, tmp_path):
    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    assert window.connect_button.text() == "Verbinden"
    assert window.language_button.text() == "DE"
    assert window.connection_title.text() == "Verbindung"
    try:
        qtbot.mouseClick(window.language_button, Qt.MouseButton.LeftButton)
        assert language() == "en"
        assert window.language_button.text() == "EN"
        assert window.connection_title.text() == "Connection"
        assert window.connect_button.text() == "Connect"
        assert window.files_title.text() == "Files"
        assert "Filter file name" == window.filter_edit.placeholderText()
        assert window.dark_button.toolTip() == "Dark mode"
        moon = window.dark_button.icon().cacheKey()
        qtbot.mouseClick(window.dark_button, Qt.MouseButton.LeftButton)
        assert window.dark_button.isChecked()
        assert window.dark_button.toolTip() == "Light mode"
        assert window.dark_button.icon().cacheKey() != moon
        assert "#1b2430" in window.styleSheet()
        window.close()
        restored = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
        qtbot.addWidget(restored)
        assert restored.language_button.text() == "EN"
        assert restored.dark_button.isChecked()
        assert restored.connection_title.text() == "Connection"
    finally:
        set_language("de")


def test_secret_is_not_written_to_settings(qtbot, tmp_path):
    settings_path = tmp_path / "settings.ini"
    window = MainWindow(session_factory=FakeSession, settings_path=str(settings_path))
    qtbot.addWidget(window)
    window.endpoint.setText("https://s3.example.com")
    window.access_key.setText("AKIAEXAMPLE")
    window.secret_key.setText("super-geheim")
    window._save_settings()
    stored = settings_path.read_text(encoding="utf-8")
    assert "super-geheim" not in stored
    assert "s3.example.com" in stored

    restored = MainWindow(session_factory=FakeSession, settings_path=str(settings_path))
    qtbot.addWidget(restored)
    assert restored.endpoint.text() == "https://s3.example.com"
    assert restored.access_key.text() == "AKIAEXAMPLE"
    assert restored.secret_key.text() == ""


def test_missing_endpoint_is_rejected_before_connecting(qtbot, tmp_path):
    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window._connect()
    assert "Endpunkt" in window.banner.text()


def _visible_buckets(window: MainWindow) -> list[str]:
    names = []
    for index in range(window.bucket_list.count()):
        item = window.bucket_list.item(index)
        if item is not None and not item.isHidden():
            names.append(item.text())
    return names


def _visible_objects(window: MainWindow) -> list[str]:
    names = []
    for index, row in enumerate(window._rows):
        if window.object_table.isRowHidden(index):
            continue
        if row.is_up:
            names.append("..")
        elif row.entry is not None:
            names.append(row.entry.name)
    return names


def _row_named(window: MainWindow, name: str) -> int:
    for index, row in enumerate(window._rows):
        if row.entry is not None and row.entry.name == name:
            return index
    raise AssertionError(name)


def _bucket_names(window: MainWindow) -> list[str]:
    names = []
    for index in range(window.bucket_list.count()):
        item = window.bucket_list.item(index)
        names.append(item.text())
    return names


def _object_names(window: MainWindow) -> list[str]:
    names = []
    for row in window._rows:
        if row.is_up:
            names.append("..")
        elif row.entry is not None:
            names.append(row.entry.name)
    return names


def _click_bucket(qtbot, window: MainWindow, name: str) -> None:
    for index in range(window.bucket_list.count()):
        item = window.bucket_list.item(index)
        if item.text() == name:
            window.bucket_list.scrollToItem(item)
            rect = window.bucket_list.visualItemRect(item)
            if rect.isValid() and not rect.isEmpty():
                qtbot.mouseClick(window.bucket_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
            else:
                window.bucket_list.itemClicked.emit(item)
            return
    raise AssertionError(name)


def _click_object(qtbot, window: MainWindow, name: str) -> None:
    qtbot.waitUntil(lambda: _guard_expired(window))
    for index, row in enumerate(window._rows):
        if row.entry is not None and row.entry.name == name:
            window.object_table.scrollTo(window.object_table.model().index(index, 0))
            rect = window.object_table.visualRect(window.object_table.model().index(index, 0))
            if rect.isValid() and not rect.isEmpty():
                qtbot.mouseClick(window.object_table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
            else:
                window.object_table.cellClicked.emit(index, 0)
            return
    raise AssertionError(name)


def test_transfer_bar_shows_bytes_for_upload_and_download(qtbot, tmp_path, monkeypatch):
    source = tmp_path / "notiz.txt"
    source.write_bytes(b"0123456789")

    class Session(FakeSession):
        def upload(self, bucket, key, source, progress=None):
            self.uploaded = (bucket, key)
            assert progress is not None
            progress(4)
            progress(6)

    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window._begin_transfer(10, kind="upload")
    window._on_bytes_advanced(4)
    assert window.transfer_row.isVisible()
    assert window.progress.isVisible()
    assert window.progress.value() == 4
    assert window.progress.maximum() == 10
    assert "4 B / 10 B" in window.progress.toolTip()
    window._finish_transfer()
    window._busy = 0
    window.progress.hide()

    window.session = Session()
    window.bucket_name = "projekt"
    window.prefix = ""
    window._upload_plan([(str(source), "notiz.txt")])
    qtbot.waitUntil(
        lambda: getattr(window.session, "uploaded", None) == ("projekt", "notiz.txt") and window._transfer_active is False,
        timeout=4000,
    )
    assert window._transfer_peak == 10

    monkeypatch.setattr(
        "s3viewer.window.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "readme.txt"), ""),
    )
    window.session = FakeSession()
    window.bucket_name = "projekt"
    window._download_entries([ObjectEntry("readme.txt", "readme.txt", False, 11)])
    qtbot.waitUntil(lambda: window._transfer_active is False and window._transfer_peak == 11, timeout=4000)
    assert (tmp_path / "readme.txt").read_bytes() == b"Hallo Welt\n"


def test_new_folder_is_created_in_the_open_prefix(qtbot, tmp_path, monkeypatch):
    class Session(FakeSession):
        def create_folder(self, bucket, key):
            self.created = (bucket, key)

    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.session = Session()
    window.bucket_name = "projekt"
    window.prefix = "daten/"
    monkeypatch.setattr("s3viewer.window.QInputDialog.getText", lambda *_args, **_kwargs: ("a/b", True))
    window._create_folder()
    assert "Schrägstriche" in window.banner.text()

    monkeypatch.setattr("s3viewer.window.QInputDialog.getText", lambda *_args, **_kwargs: ("stapel", True))
    window._create_folder()
    qtbot.waitUntil(lambda: getattr(window.session, "created", None) == ("projekt", "daten/stapel/"), timeout=4000)


def test_download_can_be_cancelled(qtbot, tmp_path, monkeypatch):
    import threading
    import time

    from s3viewer.s3 import DownloadCancelled

    started = threading.Event()

    class Session(FakeSession):
        def download(self, bucket, key, destination, progress=None, cancel=None):
            started.set()
            while cancel is None or not cancel.cancelled:
                time.sleep(0.02)
            raise DownloadCancelled()

    window = MainWindow(session_factory=FakeSession, settings_path=str(tmp_path / "settings.ini"))
    qtbot.addWidget(window)
    window.show()
    window.session = Session()
    window.bucket_name = "projekt"
    monkeypatch.setattr(
        "s3viewer.window.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(tmp_path / "readme.txt"), ""),
    )
    window._download_entries([ObjectEntry("readme.txt", "readme.txt", False, 11)])
    qtbot.waitUntil(lambda: window.transfer_row.isVisible() and window.cancel_download_button.isVisible(), timeout=4000)
    qtbot.waitUntil(started.is_set, timeout=4000)
    qtbot.mouseClick(window.cancel_download_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == "Download abgebrochen", timeout=4000)
    assert window.transfer_row.isVisible() is False
    assert not (tmp_path / "readme.txt").exists()


def _guard_expired(window: MainWindow) -> bool:
    from time import monotonic

    return monotonic() >= window._nav_guard_until


def _texts_by_color(editor) -> dict[str, str]:
    groups: dict[str, str] = {}
    block = editor.document().begin()
    while block.isValid():
        layout = block.layout()
        if layout is not None:
            for fmt_range in layout.formats():
                color = fmt_range.format.foreground().color()
                if color.isValid():
                    snippet = block.text()[fmt_range.start : fmt_range.start + fmt_range.length]
                    key = color.name().lower()
                    groups[key] = groups.get(key, "") + snippet
        block = block.next()
    return groups
