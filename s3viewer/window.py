"""Hauptfenster: Verbindung, Buckets, Ordner und Dateivorschau."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Callable
from urllib.parse import urlparse

from PySide6.QtCore import QEvent, QItemSelectionModel, QObject, QRect, QSize, Qt, QSettings, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from s3viewer import APP_TITLE
from s3viewer.clipboard import CopiedObject, paste_pairs
from s3viewer.highlight import PreviewHighlighter, highlight_language
from s3viewer.preview import (
    EDITABLE_KINDS,
    PREVIEW_BYTE_LIMIT,
    Preview,
    build_preview,
    content_type_for_save,
)
from s3viewer.profiles import (
    config_dir_display,
    default_profiles_root,
    delete_profile,
    list_profile_names,
    load_profile,
    normalize_profile_name,
    save_profile,
    settings_ini_path,
)
from s3viewer.tiffpreview import TIFF_PREVIEW_BYTE_LIMIT, is_tiff
from s3viewer.upload import (
    colliding_keys,
    folder_marker_key,
    folder_upload_plan,
    upload_destination_label,
    upload_plan,
    uploaded_message,
)
from s3viewer.s3 import (
    MAX_LISTED,
    BucketInfo,
    CancelFlag,
    Connected,
    ConnectionSettings,
    DownloadCancelled,
    ObjectEntry,
    S3Session,
    sort_entries,
    validate_settings,
)
from s3viewer.i18n import language, set_language, tr
from s3viewer.theme import stylesheet
from s3viewer.workers import TaskRunner

NAV_GUARD_SECONDS = 0.4

@dataclass
class BrowserRow:
    entry: ObjectEntry | None
    is_up: bool = False


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt-API
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt-API
        self._editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self._line_numbers = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_width()

    def line_number_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_width(self) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt-API
        super().resizeEvent(event)
        rect = self.contentsRect()
        self._line_numbers.setGeometry(QRect(rect.left(), rect.top(), self.line_number_width(), rect.height()))

    def _update_line_number_area(self, rect, dy: int) -> None:
        if dy:
            self._line_numbers.scroll(0, dy)
        else:
            self._line_numbers.update(0, rect.y(), self._line_numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()

    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self._line_numbers)
        painter.fillRect(event.rect(), QColor("#0b1220"))
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self._line_numbers.width() - 8,
                    self.fontMetrics().height(),
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    str(number + 1),
                )
            block = block.next()
            number += 1
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())


class FitImage(QLabel):
    """Zeigt ein Bild so groß wie möglich, ohne das Seitenverhältnis zu ändern."""

    def __init__(self) -> None:
        super().__init__()
        self._source = QPixmap()
        self._fitting = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(180)

    def set_source(self, pixmap: QPixmap) -> None:
        self._source = pixmap
        self._refit()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt-API
        super().resizeEvent(event)
        self._refit()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt-API
        super().showEvent(event)
        self._refit()

    def _refit(self) -> None:
        if self._fitting:
            return
        self._fitting = True
        try:
            if self._source.isNull() or self.width() < 2 or self.height() < 2:
                if self._source.isNull():
                    self.clear()
                return
            scaled = self._source.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            super().setPixmap(scaled)
        finally:
            self._fitting = False


class TransferSignals(QObject):
    planned = Signal(int)
    advanced = Signal(int)


REGION_CHOICES = (
    "us-east-1",
    "RegionOne",
    "eu-central-1",
    "eu-central-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-north-1",
    "eu-south-1",
    "eu-south-2",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "ca-central-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-south-1",
    "sa-east-1",
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        session_factory: Callable[[ConnectionSettings], S3Session] | None = None,
        settings_path: str | None = None,
        profiles_path: str | None = None,
    ):
        super().__init__()
        self._session_factory = session_factory or S3Session
        self._settings_path = settings_path
        self._profiles_root = Path(profiles_path) if profiles_path else default_profiles_root()
        self._loading_profiles = False
        self.tasks = TaskRunner(self)
        self.session: S3Session | None = None
        self.bucket_name = ""
        self.prefix = ""
        self._rows: list[BrowserRow] = []
        self._current_entry: ObjectEntry | None = None
        self._inflight_key: str | None = None
        self._preview_text_cache = ""
        self._busy = 0
        self._connecting = False
        self._closing = False
        self.conn_epoch = 0
        self._gen = {"list": 0, "preview": 0, "download": 0, "buckets": 0}
        self._nav_guard_until = 0.0
        self._did_initial_dock = False
        self._restored_state = False
        self._dark = False
        self._connection_collapsed = False
        self._transfer_signals = TransferSignals(self)
        self._transfer_signals.planned.connect(self._on_transfer_planned)
        self._transfer_signals.advanced.connect(self._on_bytes_advanced)
        self._transfer_active = False
        self._transfer_kind = ""
        self._download_cancel: CancelFlag | None = None
        self._file_clipboard: list[CopiedObject] = []
        self._transfer_done = 0
        self._transfer_total = 0
        self._transfer_peak = 0

        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)
        self._load_icons()
        self._build_ui()
        self._apply_shortcuts()
        self._restore_settings()
        self._apply_theme()
        self._retranslate()
        self._sync_buttons()
        self.statusBar().showMessage(tr("not_connected"))
        if self.connection_body.isVisible():
            if not self.endpoint.text():
                self.endpoint.setFocus()
            else:
                self.secret_key.setFocus()

    def _load_icons(self) -> None:
        style = self.style()
        self.icon_folder = style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        self.icon_file = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self.icon_up = style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        self.icon_bucket = QIcon.fromTheme("folder-remote")
        if self.icon_bucket.isNull():
            self.icon_bucket = style.standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon)
        window_icon = self.icon_bucket
        self.setWindowIcon(window_icon)

    def _icon_button(self, theme_name: str, fallback: QStyle.StandardPixmap, tip_key: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("iconButton")
        icon = QIcon.fromTheme(theme_name)
        if icon.isNull():
            icon = self.style().standardIcon(fallback)
        button.setIcon(icon)
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(34, 34)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("i18n", tip_key)
        return button

    def _apply_theme(self) -> None:
        self.setStyleSheet(stylesheet(self._dark))
        color = QColor("#e5e7eb" if self._dark else "#1f2933")
        muted = QColor("#64748b" if self._dark else "#94a3b8")
        self.connect_button.setIcon(_themed_icon(_draw_plug, color, muted))
        self.upload_button.setIcon(_themed_icon(_draw_upload, color, muted))
        self.upload_folder_button.setIcon(_themed_icon(_draw_folder_upload, color, muted))
        self.new_folder_button.setIcon(_themed_icon(_draw_folder_new, color, muted))
        self.delete_button.setIcon(_themed_icon(_draw_trash, color, muted))
        self._sync_dark_button()

    def _sync_dark_button(self) -> None:
        self.dark_button.setIcon(_mode_icon(sun=self._dark))
        self.dark_button.setToolTip(tr("light_mode") if self._dark else tr("dark_mode"))

    def _toggle_language(self) -> None:
        set_language("en" if language() == "de" else "de")
        self._retranslate()
        self._save_settings()

    def _toggle_dark(self) -> None:
        self._dark = self.dark_button.isChecked()
        self._apply_theme()
        self._save_settings()

    def _retranslate(self) -> None:
        self.language_button.setText("EN" if language() == "en" else "DE")
        self.language_button.setToolTip(tr("language"))
        for button in self.findChildren(QPushButton):
            key = button.property("i18n")
            if key:
                button.setToolTip(tr(str(key), path=config_dir_display()))
        self._sync_dark_button()
        self.bucket_heading.setText(tr("buckets"))
        if not self.bucket_name:
            self.files_title.setText(tr("files"))
        self.connection_title.setText(tr("connection"))
        if self._current_entry is None:
            self.preview_title.setText(tr("preview"))
            self.preview_dock.setWindowTitle(tr("preview"))
            self.preview_message.setText(tr("preview_idle"))
        else:
            self.preview_dock.setWindowTitle(tr("preview_named", name=self._current_entry.name))
        for index, row in enumerate(self._rows):
            if row.is_up:
                item = self.object_table.item(index, 0)
                if item is not None:
                    item.setToolTip(tr("parent_folder"))
        self.cancel_download_button.setText(tr("cancel_download"))
        if self._transfer_active:
            self.transfer_label.setText(
                tr("transfer_download")
                if self._transfer_kind == "download"
                else tr("transfer_delete")
                if self._transfer_kind == "delete"
                else tr("transfer_copy")
                if self._transfer_kind == "copy"
                else tr("transfer_upload")
            )
        self.bucket_filter.setPlaceholderText(tr("filter_buckets"))
        self.bucket_filter.setToolTip(tr("filter_buckets_tip"))
        self.filter_edit.setPlaceholderText(tr("filter_files"))
        self.filter_edit.setToolTip(tr("filter_files_tip"))
        self.label_endpoint.setText(tr("endpoint"))
        self.label_region.setText(tr("region"))
        self.label_access.setText(tr("access_key"))
        self.label_secret.setText(tr("secret_key"))
        self.label_bucket.setText(tr("bucket"))
        self.label_signature.setText(tr("signature"))
        self.endpoint.setPlaceholderText(tr("endpoint_ph"))
        self.endpoint.setToolTip(tr("endpoint_tip"))
        self.region.setToolTip(tr("region_tip"))
        self.access_key.setPlaceholderText(tr("access_ph"))
        self.secret_key.setPlaceholderText(tr("secret_ph"))
        self.secret_key.setToolTip(tr("secret_tip"))
        self.bucket_edit.setPlaceholderText(tr("bucket_ph"))
        self.bucket_edit.setToolTip(tr("bucket_tip"))
        self.signature.setToolTip(tr("signature_tip"))
        self.path_style.setText(tr("path_style"))
        self.path_style.setToolTip(tr("path_tip"))
        self.verify_tls.setText(tr("verify_tls"))
        self.verify_tls.setToolTip(tr("verify_tip"))
        self.hint.setText(tr("hint"))
        self.profile_combo.setToolTip(tr("profile_tip", path=config_dir_display()))
        if self.profile_combo.count() and self.profile_combo.itemData(0) in {"", None}:
            self.profile_combo.setItemText(0, tr("saved_connection"))
        self.object_table.setHorizontalHeaderLabels([tr("col_name"), tr("col_size"), tr("col_modified")])
        if not self.bucket_name:
            self.file_placeholder.setText(tr("files_placeholder"))
        self._toggle_secret(self.reveal_button.isChecked())
        self._set_connection_collapsed(self._connection_collapsed)
        self._sync_buttons()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)
        layout.addWidget(self._build_connection())
        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        layout.addWidget(self.banner)
        self._reload_profiles()

        self.bucket_list = QListWidget()
        self.bucket_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bucket_list.itemClicked.connect(self._on_bucket_clicked)
        self.bucket_count = QLabel("")
        self.bucket_count.setObjectName("muted")
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_header = QHBoxLayout()
        self.bucket_heading = QLabel("Buckets")
        self.bucket_heading.setObjectName("section")
        left_header.addWidget(self.bucket_heading)
        left_header.addStretch(1)
        left_header.addWidget(self.bucket_count)
        left_layout.addLayout(left_header)
        self.bucket_filter = QLineEdit()
        self.bucket_filter.setObjectName("bucketFilter")
        self.bucket_filter.setPlaceholderText("Bucket-Name filtern")
        self.bucket_filter.setClearButtonEnabled(True)
        self.bucket_filter.setToolTip("Zeigt nur Buckets, deren Name diesen Text enthält.")
        self.bucket_filter.textChanged.connect(self._apply_bucket_filter)
        left_layout.addWidget(self.bucket_filter)
        left_layout.addWidget(self.bucket_list)

        self.files_title = QLabel("Dateien")
        self.files_title.setObjectName("section")
        self.up_button = self._icon_button("go-up", QStyle.StandardPixmap.SP_ArrowUp, "up")
        self.up_button.clicked.connect(self._go_up)
        self.refresh_button = self._icon_button("view-refresh", QStyle.StandardPixmap.SP_BrowserReload, "refresh")
        self.refresh_button.clicked.connect(self._refresh)
        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName("fileFilter")
        self.filter_edit.setPlaceholderText("Dateiname filtern")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setToolTip("Zeigt nur Dateien und Ordner, deren Name diesen Text enthält.")
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.file_count = QLabel("")
        self.file_count.setObjectName("muted")
        self.path_host = QWidget()
        self.path_layout = QHBoxLayout(self.path_host)
        self.path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_layout.setSpacing(2)
        path_scroll = QScrollArea()
        path_scroll.setWidget(self.path_host)
        path_scroll.setWidgetResizable(True)
        path_scroll.setFrameShape(QFrame.Shape.NoFrame)
        path_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        path_scroll.setFixedHeight(36)

        files_header = QHBoxLayout()
        files_header.addWidget(self.up_button)
        files_header.addWidget(path_scroll, 1)
        self.save_button = self._icon_button("document-save", QStyle.StandardPixmap.SP_DialogSaveButton, "download_tip")
        self.save_button.clicked.connect(self._download_selected)
        files_header.addWidget(self.save_button)
        self.delete_button = self._icon_button("edit-delete", QStyle.StandardPixmap.SP_TrashIcon, "delete_tip")
        self.delete_button.setIcon(_themed_icon(_draw_trash, QColor("#1f2933"), QColor("#94a3b8")))
        self.delete_button.clicked.connect(self._delete_selected)
        files_header.addWidget(self.delete_button)
        self.upload_button = self._icon_button("go-up", QStyle.StandardPixmap.SP_ArrowUp, "upload_tip")
        self.upload_button.setIcon(_themed_icon(_draw_upload, QColor("#1f2933"), QColor("#94a3b8")))
        self.upload_button.clicked.connect(self._upload_files)
        files_header.addWidget(self.upload_button)
        self.upload_folder_button = self._icon_button("folder-download", QStyle.StandardPixmap.SP_DirIcon, "upload_folder_tip")
        self.upload_folder_button.setIcon(_themed_icon(_draw_folder_upload, QColor("#1f2933"), QColor("#94a3b8")))
        self.upload_folder_button.clicked.connect(self._upload_folder)
        files_header.addWidget(self.upload_folder_button)
        self.new_folder_button = self._icon_button("folder-new", QStyle.StandardPixmap.SP_DirIcon, "new_folder_tip")
        self.new_folder_button.setIcon(_themed_icon(_draw_folder_new, QColor("#1f2933"), QColor("#94a3b8")))
        self.new_folder_button.clicked.connect(self._create_folder)
        files_header.addWidget(self.new_folder_button)
        files_header.addWidget(self.refresh_button)
        file_filter_row = QHBoxLayout()
        file_filter_row.addWidget(self.filter_edit, 1)
        file_filter_row.addWidget(self.file_count)

        self.object_table = QTableWidget(0, 3)
        self.object_table.setHorizontalHeaderLabels(["Name", "Größe", "Geändert"])
        self.object_table.verticalHeader().setVisible(False)
        self.object_table.verticalHeader().setDefaultSectionSize(30)
        self.object_table.setShowGrid(False)
        self.object_table.setAlternatingRowColors(True)
        self.object_table.setWordWrap(False)
        self.object_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.object_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.object_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.object_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.object_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.object_table.customContextMenuRequested.connect(self._show_file_menu)
        self.object_table.installEventFilter(self)
        self.object_table.itemSelectionChanged.connect(self._sync_buttons)
        header = self.object_table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.object_table.currentCellChanged.connect(self._on_current_cell)
        self.object_table.cellClicked.connect(self._on_cell_clicked)
        self.object_table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        self.file_placeholder = QLabel(
            "Nach der Verbindung links einen Bucket wählen.\n"
            "Ordner öffnen sich per Klick. Textdateien, CSV, JSON, YAML und XML\n"
            "erscheinen in der Dateivorschau."
        )
        self.file_placeholder.setObjectName("placeholder")
        self.file_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_placeholder.setWordWrap(True)
        self.file_stack = QStackedWidget()
        self.file_stack.addWidget(self.file_placeholder)
        self.file_stack.addWidget(self.object_table)

        files = QWidget()
        files_layout = QVBoxLayout(files)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(8)
        files_layout.addWidget(self.files_title)
        files_layout.addLayout(files_header)
        files_layout.addLayout(file_filter_row)
        files_layout.addWidget(self.file_stack, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(files)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 700])
        left.setMinimumWidth(200)
        left.setMaximumWidth(360)
        layout.addWidget(splitter, 1)
        self._build_preview()
        self._render_path()

        self.transfer_row = QWidget()
        self.transfer_row.setObjectName("transferRow")
        transfer_layout = QHBoxLayout(self.transfer_row)
        transfer_layout.setContentsMargins(10, 8, 10, 8)
        transfer_layout.setSpacing(10)
        self.transfer_label = QLabel(tr("transfer_download"))
        self.transfer_label.setObjectName("transferLabel")
        self.progress = QProgressBar()
        self.progress.setObjectName("transfer")
        self.progress.setFixedHeight(22)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")
        self.transfer_amount = QLabel("")
        self.transfer_amount.setObjectName("muted")
        self.transfer_amount.setMinimumWidth(110)
        self.cancel_download_button = QPushButton(tr("cancel_download"))
        self.cancel_download_button.setObjectName("cancelTransfer")
        self.cancel_download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_download_button.clicked.connect(self._cancel_download)
        transfer_layout.addWidget(self.transfer_label)
        transfer_layout.addWidget(self.progress, 1)
        transfer_layout.addWidget(self.transfer_amount)
        transfer_layout.addWidget(self.cancel_download_button)
        self.transfer_row.hide()
        layout.addWidget(self.transfer_row)

        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedWidth(120)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.hide()
        self.statusBar().addPermanentWidget(self.busy_bar)

    def _build_connection(self) -> QWidget:
        card = QFrame()
        card.setObjectName("connCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(4)

        self.connection_toggle = QPushButton("▲")
        self.connection_toggle.setObjectName("fold")
        self.connection_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connection_toggle.setToolTip("Verbindung nach oben einklappen")
        self.connection_toggle.clicked.connect(self._toggle_connection)
        self.connection_title = QLabel("Verbindung")
        self.connection_title.setObjectName("section")
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("profileCombo")
        self.profile_combo.setMinimumWidth(220)
        self.profile_combo.setToolTip("Gespeicherte Verbindung laden")
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        self.save_profile_button = self._icon_button("document-save-as", QStyle.StandardPixmap.SP_DialogSaveButton, "save_profile_tip")
        self.save_profile_button.clicked.connect(self._save_named_profile)
        self.delete_profile_button = self._icon_button("edit-delete", QStyle.StandardPixmap.SP_TrashIcon, "delete_profile_tip")
        self.delete_profile_button.clicked.connect(self._delete_named_profile)
        self.connect_button = self._icon_button("network-connect", QStyle.StandardPixmap.SP_DialogApplyButton, "connect")
        self.connect_button.setIcon(_themed_icon(_draw_plug, QColor("#1f2933"), QColor("#94a3b8")))
        self.connect_button.clicked.connect(self._connect)
        self.disconnect_button = self._icon_button("network-disconnect", QStyle.StandardPixmap.SP_DialogCancelButton, "disconnect")
        self.disconnect_button.clicked.connect(self._disconnect)
        self.language_button = QPushButton("DE")
        self.language_button.setObjectName("langButton")
        self.language_button.setFixedSize(42, 34)
        self.language_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.language_button.clicked.connect(self._toggle_language)
        self.dark_button = self._icon_button("weather-clear-night", QStyle.StandardPixmap.SP_TitleBarShadeButton, "dark_mode")
        self.dark_button.setIcon(_mode_icon(sun=False))
        self.dark_button.setIconSize(QSize(20, 20))
        self.dark_button.setCheckable(True)
        self.dark_button.clicked.connect(self._toggle_dark)
        self.connection_summary = QLabel("")
        self.connection_summary.setObjectName("muted")
        self.connection_summary.hide()
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.connection_toggle)
        header.addWidget(self.connection_title)
        header.addWidget(self.profile_combo, 1)
        header.addWidget(self.language_button)
        header.addWidget(self.dark_button)
        header.addWidget(self.connection_summary)
        self.header_layout = header
        outer.addLayout(header)

        self.connection_actions = QWidget()
        self.actions_layout = QHBoxLayout(self.connection_actions)
        self.actions_layout.setContentsMargins(4, 2, 0, 2)
        self.actions_layout.setSpacing(8)
        self.actions_layout.addStretch(1)
        outer.addWidget(self.connection_actions)
        self._apply_connection_labels()

        self.connection_body = QWidget()
        grid = QGridLayout(self.connection_body)
        grid.setContentsMargins(4, 4, 4, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.endpoint = QLineEdit()
        self.endpoint.setPlaceholderText("https://s3.cloud.example.com")
        self.endpoint.setToolTip("S3-API-Adresse der OpenStack-Umgebung, inklusive https://")
        self.region = QComboBox()
        self.region.setObjectName("region")
        self.region.setEditable(True)
        self.region.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.region.setMaxVisibleItems(12)
        self.region.addItems(REGION_CHOICES)
        self.region.setCurrentIndex(0)
        self.region.setFixedWidth(168)
        self.region.setToolTip("Bei OpenStack oft der Region-Name, zum Beispiel RegionOne. Der Wert geht in die Signatur ein.")
        self.access_key = QLineEdit()
        self.access_key.setPlaceholderText("S3 Access Key")
        self.secret_key = QLineEdit()
        self.secret_key.setPlaceholderText("S3 Secret Key")
        self.secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_key.setToolTip("Wird nur im Speicher gehalten und nicht gespeichert.")
        self.reveal_button = self._icon_button("view-visible", QStyle.StandardPixmap.SP_FileDialogInfoView, "show_secret")
        self.reveal_button.setCheckable(True)
        self.reveal_button.toggled.connect(self._toggle_secret)
        self.bucket_edit = QLineEdit()
        self.bucket_edit.setPlaceholderText("optional")
        self.bucket_edit.setToolTip("Nur nötig, wenn die Rechte keine Bucket-Liste erlauben.")
        self.signature = QComboBox()
        self.signature.addItem("s3v4", "s3v4")
        self.signature.addItem("s3 (SigV2)", "s3")
        self.signature.setToolTip("Ältere OpenStack-Installationen brauchen manchmal SigV2.")
        self.path_style = QCheckBox("Pfad-Stil")
        self.path_style.setChecked(True)
        self.path_style.setToolTip(
            "Für OpenStack aktiv lassen. Der Bucket steht dann im URL-Pfad und nicht in der Domain."
        )
        self.verify_tls = QCheckBox("TLS-Zertifikat prüfen")
        self.verify_tls.setChecked(True)
        self.verify_tls.setToolTip("Ausschalten, wenn der Endpunkt ein selbstsigniertes Zertifikat verwendet.")

        for field in (self.endpoint, self.access_key, self.secret_key, self.bucket_edit):
            field.returnPressed.connect(self._connect)
        region_edit = self.region.lineEdit()
        if region_edit is not None:
            region_edit.returnPressed.connect(self._connect)

        self.label_endpoint = QLabel("Endpunkt")
        self.label_region = QLabel("Region")
        self.label_access = QLabel("Zugriffsschlüssel")
        self.label_secret = QLabel("Geheimer Schlüssel")
        self.label_bucket = QLabel("Bucket")
        self.label_signature = QLabel("Signatur")
        grid.addWidget(self.label_endpoint, 0, 0)
        grid.addWidget(self.endpoint, 0, 1, 1, 3)
        grid.addWidget(self.label_region, 0, 4)
        grid.addWidget(self.region, 0, 5)
        grid.addWidget(self.label_access, 1, 0)
        grid.addWidget(self.access_key, 1, 1)
        grid.addWidget(self.label_secret, 1, 2)
        grid.addWidget(self.secret_key, 1, 3)
        grid.addWidget(self.reveal_button, 1, 4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        options = QHBoxLayout()
        options.setSpacing(10)
        options.addWidget(self.label_bucket)
        options.addWidget(self.bucket_edit)
        options.addWidget(self.label_signature)
        options.addWidget(self.signature)
        options.addWidget(self.path_style)
        options.addWidget(self.verify_tls)
        options.addStretch(1)
        grid.addLayout(options, 2, 0, 1, 6)

        self.hint = QLabel()
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        grid.addWidget(self.hint, 3, 0, 1, 6)
        self.bucket_edit.setFixedWidth(180)
        self.endpoint.textChanged.connect(self._update_connection_summary)
        outer.addWidget(self.connection_body)
        return card

    def _toggle_connection(self) -> None:
        self._set_connection_collapsed(not self._connection_collapsed)

    def _set_connection_collapsed(self, collapsed: bool) -> None:
        self._connection_collapsed = collapsed
        self.connection_body.setVisible(not collapsed)
        self.connection_summary.setVisible(collapsed)
        self._update_connection_summary()
        if collapsed:
            self.connection_toggle.setText("▼")
            self.connection_toggle.setToolTip(tr("fold_expand"))
        else:
            self.connection_toggle.setText("▲")
            self.connection_toggle.setToolTip(tr("fold_collapse"))
        self._apply_connection_labels()

    def _detach_button(self, button: QPushButton) -> None:
        for layout in (self.header_layout, self.actions_layout):
            if layout.indexOf(button) >= 0:
                layout.removeWidget(button)
                return

    def _apply_connection_labels(self) -> None:
        expanded = not self._connection_collapsed
        connect_key = "connecting" if self._connecting else "connect"
        state = (expanded, connect_key, language())
        if state == getattr(self, "_connection_label_state", None):
            return
        self._connection_label_state = state
        labeled = (
            (self.save_profile_button, "save_profile"),
            (self.delete_profile_button, "delete_profile"),
            (self.connect_button, connect_key),
            (self.disconnect_button, "disconnect"),
        )
        for button, _key in labeled:
            self._detach_button(button)
        if expanded:
            for button, key in labeled:
                button.setText(tr(key))
                text_width = button.fontMetrics().horizontalAdvance(button.text())
                button.setFixedSize(18 + 8 + text_width + 22, 34)
                self.actions_layout.insertWidget(self.actions_layout.count() - 1, button)
                button.show()
            self.connection_actions.show()
            return
        self.connection_actions.hide()
        lang_index = self.header_layout.indexOf(self.language_button)
        self.header_layout.insertWidget(lang_index, self.connect_button)
        self.header_layout.insertWidget(lang_index + 1, self.disconnect_button)
        for button in (self.connect_button, self.disconnect_button):
            button.setText("")
            button.setFixedSize(34, 34)
            button.show()
        for button in (self.save_profile_button, self.delete_profile_button):
            button.setText("")
            button.hide()
            button.setParent(self.connection_actions)

    def _update_connection_summary(self) -> None:
        text = self.endpoint.text().strip()
        if "://" in text:
            host = urlparse(text).netloc
            text = host or text
        name = self.profile_combo.currentData()
        if name and text:
            text = f"{name} · {text}"
        self.connection_summary.setText(text or tr("summary_empty"))

    def _reload_profiles(self, select: str | None = None) -> None:
        self._loading_profiles = True
        current = select if select is not None else self.profile_combo.currentData()
        self.profile_combo.clear()
        self.profile_combo.addItem(tr("saved_connection"), "")
        try:
            names = list_profile_names(self._profiles_root)
        except ValueError as exc:
            self._loading_profiles = False
            self._set_banner(str(exc))
            self.delete_profile_button.setEnabled(False)
            return
        for name in names:
            self.profile_combo.addItem(name, name)
        index = self.profile_combo.findData(current) if current else 0
        self.profile_combo.setCurrentIndex(index if index >= 0 else 0)
        self._loading_profiles = False
        self.delete_profile_button.setEnabled(bool(self.profile_combo.currentData()))
        self._update_connection_summary()

    def _on_profile_selected(self, _index: int) -> None:
        if self._loading_profiles:
            return
        name = self.profile_combo.currentData()
        self.delete_profile_button.setEnabled(bool(name))
        self._update_connection_summary()
        if not name:
            return
        try:
            settings = load_profile(self._profiles_root, str(name))
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        self._apply_saved_profile(settings)
        self._set_banner(None)

    def _apply_saved_profile(self, settings: ConnectionSettings) -> None:
        self.endpoint.setText(settings.endpoint_url)
        self.access_key.setText(settings.access_key)
        self.secret_key.setText(settings.secret_key)
        self._set_region(settings.region)
        self.bucket_edit.setText(settings.direct_bucket)
        signature = self.signature.findData(settings.signature_version)
        if signature >= 0:
            self.signature.setCurrentIndex(signature)
        self.path_style.setChecked(settings.path_style)
        self.verify_tls.setChecked(settings.verify_ssl)

    def _save_named_profile(self) -> None:
        try:
            settings = self._settings_from_form()
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        suggested = str(self.profile_combo.currentData() or "")
        if not suggested:
            host = urlparse(settings.endpoint_url).netloc
            suggested = host or tr("fallback_profile")
        name, accepted = QInputDialog.getText(self, tr("save_connection_title"), tr("save_connection_label"), text=suggested)
        if not accepted:
            return
        try:
            cleaned = normalize_profile_name(name)
            if cleaned in list_profile_names(self._profiles_root) and cleaned != self.profile_combo.currentData():
                answer = QMessageBox.question(
                    self,
                    tr("replace_connection_title"),
                    tr("replace_connection_body", name=cleaned),
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            save_profile(self._profiles_root, cleaned, settings)
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        self._reload_profiles(select=cleaned)
        self._set_banner(None)
        self.statusBar().showMessage(tr("saved_connection_status", path=self._profiles_root))

    def _delete_named_profile(self) -> None:
        name = self.profile_combo.currentData()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            tr("remove_connection_title"),
            tr("remove_connection_body", name=name, path=config_dir_display()),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_profile(self._profiles_root, str(name))
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        self._reload_profiles(select="")
        self.statusBar().showMessage(tr("removed_connection", name=name))

    def _build_preview(self) -> None:
        self.preview_dock = QDockWidget("Dateivorschau", self)
        self.preview_dock.setObjectName("previewDock")
        self.preview_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.preview_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.preview_title = QLabel("Dateivorschau")
        self.preview_title.setObjectName("section")
        self.preview_badge = QLabel("")
        self.preview_badge.setObjectName("badge")
        self.preview_badge.hide()
        header.addWidget(self.preview_title, 1)
        header.addWidget(self.preview_badge)
        self.preview_meta = QLabel("")
        self.preview_meta.setObjectName("muted")
        self.preview_notice = QLabel("")
        self.preview_notice.setObjectName("notice")
        self.preview_notice.setWordWrap(True)
        self.preview_notice.hide()

        self.preview_text = CodeEditor()
        self.preview_text.setObjectName("preview")
        self.preview_text.setReadOnly(True)
        self.preview_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFont("DejaVu Sans Mono")
        mono.setPointSize(10)
        self.preview_text.setFont(mono)
        self.preview_text.textChanged.connect(self._on_preview_edited)
        self.highlighter = PreviewHighlighter(self.preview_text.document())
        self._preview_editable = False
        self._preview_dirty = False
        self._preview_save_type = "text/plain; charset=utf-8"

        self.preview_table = QTableWidget(0, 0)
        self.preview_table.verticalHeader().setVisible(True)
        self.preview_table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview_table.setWordWrap(False)
        self.preview_table.horizontalHeader().setHighlightSections(False)

        self.preview_message = QLabel(
            "Wähle eine Textdatei, CSV, JSON, YAML oder XML aus.\nDer Inhalt erscheint hier."
        )
        self.preview_message.setObjectName("previewMessage")
        self.preview_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_message.setWordWrap(True)

        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.preview_text)
        self.preview_stack.addWidget(self.preview_table)
        self.preview_message_page = QWidget()
        message_layout = QVBoxLayout(self.preview_message_page)
        message_layout.addStretch(1)
        message_layout.addWidget(self.preview_message)
        message_layout.addStretch(1)
        self.preview_stack.addWidget(self.preview_message_page)
        self.preview_image = FitImage()
        self.preview_image.setObjectName("tiffPreview")
        self.preview_image_page = QWidget()
        image_layout = QVBoxLayout(self.preview_image_page)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(self.preview_image)
        self.preview_stack.addWidget(self.preview_image_page)
        self.preview_stack.setCurrentWidget(self.preview_message_page)

        buttons = QHBoxLayout()
        self.copy_button = self._icon_button("edit-copy", QStyle.StandardPixmap.SP_FileDialogContentsView, "copy")
        self.copy_button.clicked.connect(self._copy_preview)
        self.save_edit_button = self._icon_button("document-save", QStyle.StandardPixmap.SP_DialogSaveButton, "save_edits_tip")
        self.save_edit_button.clicked.connect(self._save_preview_edits)
        self.save_edit_button.setEnabled(False)
        self.save_edit_button.hide()
        self.download_button = self._icon_button("folder-download", QStyle.StandardPixmap.SP_ArrowDown, "download_file_tip")
        self.download_button.clicked.connect(self._download)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.save_edit_button)
        buttons.addWidget(self.download_button)
        buttons.addStretch(1)

        layout.addLayout(header)
        layout.addWidget(self.preview_meta)
        layout.addWidget(self.preview_notice)
        layout.addWidget(self.preview_stack, 1)
        layout.addLayout(buttons)
        self.preview_dock.setWidget(body)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.preview_dock)
        self.preview_dock.setMinimumWidth(340)

    def _apply_shortcuts(self) -> None:
        refresh = QShortcut(QKeySequence(Qt.Key.Key_F5), self)
        refresh.activated.connect(self._refresh)
        find = QShortcut(QKeySequence.StandardKey.Find, self)
        find.activated.connect(self.filter_edit.setFocus)
        go_up = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self.object_table)
        go_up.setContext(Qt.ShortcutContext.WidgetShortcut)
        go_up.activated.connect(self._go_up)
        activate = QShortcut(QKeySequence(Qt.Key.Key_Return), self.object_table)
        activate.setContext(Qt.ShortcutContext.WidgetShortcut)
        activate.activated.connect(self._activate_selected)
        activate_enter = QShortcut(QKeySequence(Qt.Key.Key_Enter), self.object_table)
        activate_enter.setContext(Qt.ShortcutContext.WidgetShortcut)
        activate_enter.activated.connect(self._activate_selected)

    def _qsettings(self) -> QSettings:
        if self._settings_path:
            return QSettings(self._settings_path, QSettings.Format.IniFormat)
        return QSettings(str(settings_ini_path()), QSettings.Format.IniFormat)

    def _restore_settings(self) -> None:
        settings = self._qsettings()
        self.endpoint.setText(str(settings.value("endpoint", "") or ""))
        self.access_key.setText(str(settings.value("access_key", "") or ""))
        region = str(settings.value("region", "us-east-1") or "us-east-1")
        self._set_region(region)
        self.bucket_edit.setText(str(settings.value("bucket", "") or ""))
        signature = str(settings.value("signature", "s3v4") or "s3v4")
        index = self.signature.findData(signature)
        if index >= 0:
            self.signature.setCurrentIndex(index)
        self.path_style.setChecked(_as_bool(settings.value("path_style"), True))
        self.verify_tls.setChecked(_as_bool(settings.value("verify_ssl"), True))
        self._set_connection_collapsed(_as_bool(settings.value("connection_collapsed"), False))
        set_language(str(settings.value("language", "de") or "de"))
        self._dark = _as_bool(settings.value("dark_mode"), False)
        self.dark_button.blockSignals(True)
        self.dark_button.setChecked(self._dark)
        self.dark_button.blockSignals(False)
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = settings.value("window_state")
        if state:
            self.restoreState(state)
            self._restored_state = True

    def _save_settings(self) -> None:
        settings = self._qsettings()
        settings.setValue("endpoint", self.endpoint.text().strip())
        settings.setValue("access_key", self.access_key.text().strip())
        settings.setValue("region", self.region.currentText().strip())
        settings.setValue("bucket", self.bucket_edit.text().strip())
        settings.setValue("signature", self.signature.currentData() or "s3v4")
        settings.setValue("path_style", "1" if self.path_style.isChecked() else "0")
        settings.setValue("verify_ssl", "1" if self.verify_tls.isChecked() else "0")
        settings.setValue("connection_collapsed", "1" if self._connection_collapsed else "0")
        settings.setValue("language", language())
        settings.setValue("dark_mode", "1" if self._dark else "0")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("window_state", self.saveState())
        settings.remove("secret_key")
        settings.remove("secret")
        settings.sync()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt-API
        super().showEvent(event)
        if self._did_initial_dock or self._restored_state:
            self._did_initial_dock = True
            return
        self._did_initial_dock = True
        self.resizeDocks([self.preview_dock], [440], Qt.Orientation.Horizontal)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt-API
        self._closing = True
        self._save_settings()
        self.tasks.drop_callbacks()
        self.tasks.pool.clear()
        self.tasks.pool.waitForDone(2000)
        session = self.session
        self.session = None
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
        super().closeEvent(event)

    def _toggle_secret(self, visible: bool) -> None:
        self.secret_key.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        icon_name = "view-hidden" if visible else "view-visible"
        fallback = QStyle.StandardPixmap.SP_DialogCancelButton if visible else QStyle.StandardPixmap.SP_FileDialogInfoView
        icon = QIcon.fromTheme(icon_name)
        if icon.isNull():
            icon = self.style().standardIcon(fallback)
        self.reveal_button.setIcon(icon)
        self.reveal_button.setToolTip(tr("hide_secret") if visible else tr("show_secret"))

    def _set_region(self, name: str) -> None:
        chosen = (name or "").strip() or "us-east-1"
        index = self.region.findText(chosen)
        if index < 0:
            self.region.addItem(chosen)
            index = self.region.findText(chosen)
        self.region.setCurrentIndex(index)

    def _settings_from_form(self) -> ConnectionSettings:
        return validate_settings(
            self.endpoint.text(),
            self.access_key.text(),
            self.secret_key.text(),
            self.region.currentText(),
            self.bucket_edit.text(),
            self.path_style.isChecked(),
            self.verify_tls.isChecked(),
            self.signature.currentData() or "s3v4",
        )

    def _connect(self) -> None:
        try:
            settings = self._settings_from_form()
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        self._set_banner(None)
        self._save_settings()
        self.conn_epoch += 1
        epoch = self.conn_epoch
        self._connecting = True
        old = self.session
        self.session = None
        self._clear_browser()
        self._sync_buttons()
        self.statusBar().showMessage(tr("connecting"))
        self._set_busy(True)

        def work() -> tuple[S3Session, Connected]:
            if old is not None:
                old.close()
            session = self._session_factory(settings)
            try:
                connected = session.establish()
            except Exception:
                session.close()
                raise
            return session, connected

        def ok(payload: object) -> None:
            self._set_busy(False)
            self._connecting = False
            session, connected = payload  # type: ignore[misc]
            if self._closing or epoch != self.conn_epoch:
                session.close()
                self._sync_buttons()
                return
            self._apply_connection(session, connected)

        def err(message: str) -> None:
            self._set_busy(False)
            self._connecting = False
            self._sync_buttons()
            if self._closing or epoch != self.conn_epoch:
                return
            self._set_banner(message)
            self.statusBar().showMessage(tr("not_connected"))

        self.tasks.submit(work, ok, err)

    def _disconnect(self) -> None:
        self.conn_epoch += 1
        session = self.session
        self.session = None
        self._connecting = False
        if session is not None:
            self.tasks.submit(lambda: _close_quietly(session), lambda _result: None, lambda _message: None)
        self._clear_browser()
        self._set_banner(None)
        self._sync_buttons()
        self.setWindowTitle(APP_TITLE)
        self.statusBar().showMessage(tr("not_connected"))

    def _apply_connection(self, session: S3Session, connected: Connected) -> None:
        self.session = session
        buckets = sorted(connected.buckets, key=lambda bucket: bucket.name.casefold())
        self._fill_buckets(buckets)
        host = urlparse(session.settings.endpoint_url).netloc
        self.setWindowTitle(f"{APP_TITLE} — {host}")
        self._sync_buttons()
        if connected.notice:
            self.statusBar().showMessage(connected.notice)
        elif not buckets:
            self.statusBar().showMessage(tr("no_buckets"))
            self._set_banner(tr("no_bucket_list"))
        else:
            self._set_banner(None)
            self.statusBar().showMessage(tr("bucket_count", count=len(buckets)))
        target = session.settings.direct_bucket
        if target and any(bucket.name == target for bucket in buckets):
            self._select_bucket_item(target)
            self._open_bucket(target)
        elif len(buckets) == 1:
            self._select_bucket_item(buckets[0].name)
            self._open_bucket(buckets[0].name)

    def _fill_buckets(self, buckets: list[BucketInfo]) -> None:
        self.bucket_list.clear()
        for bucket in buckets:
            item = QListWidgetItem(bucket.name)
            item.setData(Qt.ItemDataRole.UserRole, bucket.name)
            item.setIcon(self.icon_bucket)
            if bucket.created:
                item.setToolTip(tr("created", when=format_dt(bucket.created)))
            self.bucket_list.addItem(item)
        self._apply_bucket_filter()

    def _select_bucket_item(self, name: str) -> None:
        for index in range(self.bucket_list.count()):
            item = self.bucket_list.item(index)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
                self.bucket_list.setCurrentRow(index)
                return

    def _on_bucket_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if not name:
            return
        if name == self.bucket_name and self.prefix == "":
            return
        self._open_bucket(str(name))

    def _open_bucket(self, name: str) -> None:
        self.bucket_name = name
        self.files_title.setText(name)
        self._select_bucket_item(name)
        self._open_prefix("")

    def _open_prefix(self, prefix: str) -> None:
        if self.session is None or not self.bucket_name:
            return
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        self._nav_guard_until = monotonic() + NAV_GUARD_SECONDS
        self.prefix = prefix
        self._gen["preview"] = self._gen.get("preview", 0) + 1
        self._inflight_key = None
        self._current_entry = None
        self.filter_edit.blockSignals(True)
        self.filter_edit.clear()
        self.filter_edit.blockSignals(False)
        self._fill_objects([], False)
        self.file_stack.setCurrentWidget(self.object_table)
        self._render_path()
        self._show_message_preview(tr("preview"), tr("loading_folder"))
        self._sync_buttons()
        session = self.session
        bucket = self.bucket_name
        self.statusBar().showMessage(tr("loading_folder"))
        self._submit(
            "list",
            lambda: session.list_folder(bucket, prefix),
            self._on_listed,
            self._on_list_error,
        )

    def _on_listed(self, payload: object) -> None:
        entries, capped = payload  # type: ignore[misc]
        self._fill_objects(entries, capped)
        self._set_banner(None)
        folders = sum(1 for entry in entries if entry.is_folder)
        files = len(entries) - folders
        if not entries:
            message = tr("folder_empty") if self.prefix else tr("bucket_empty")
        else:
            message = tr("counts", folders=folders, files=files)
        if capped:
            message += tr("list_capped", limit=MAX_LISTED)
        self.statusBar().showMessage(message)

    def _on_list_error(self, message: str) -> None:
        self._set_banner(message)
        self.statusBar().showMessage(tr("folder_failed"))

    def _fill_objects(self, entries: list[ObjectEntry], capped: bool) -> None:
        del capped
        rows = [BrowserRow(entry=None, is_up=True)] if self.prefix else []
        rows.extend(BrowserRow(entry=entry) for entry in sort_entries(entries))
        self._rows = rows
        table = self.object_table
        table.blockSignals(True)
        table.clearContents()
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            if row.is_up:
                name = QTableWidgetItem("..")
                name.setIcon(self.icon_up)
                name.setToolTip(tr("parent_folder"))
                table.setItem(index, 0, name)
                table.setItem(index, 1, QTableWidgetItem(""))
                table.setItem(index, 2, QTableWidgetItem(""))
                continue
            entry = row.entry
            assert entry is not None
            name = QTableWidgetItem(entry.name)
            name.setIcon(self.icon_folder if entry.is_folder else self.icon_file)
            name.setToolTip(entry.key)
            table.setItem(index, 0, name)
            size = QTableWidgetItem("" if entry.is_folder else format_size(entry.size))
            size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(index, 1, size)
            modified = QTableWidgetItem("" if entry.is_folder else format_dt(entry.last_modified))
            table.setItem(index, 2, modified)
        table.clearSelection()
        table.blockSignals(False)
        self._apply_filter()
        self._sync_buttons()

    def _render_path(self) -> None:
        while self.path_layout.count():
            item = self.path_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if not self.bucket_name:
            self.path_layout.addStretch(1)
            return
        parts = [part for part in self.prefix.split("/") if part]
        self._add_crumb(self.bucket_name, "", current=not parts)
        walked = ""
        for index, part in enumerate(parts):
            walked += part + "/"
            self._add_crumb(part, walked, current=index == len(parts) - 1)
        self.path_layout.addStretch(1)

    def _add_crumb(self, label: str, prefix: str, current: bool) -> None:
        if self.path_layout.count():
            separator = QLabel("/")
            separator.setObjectName("crumbSep")
            self.path_layout.addWidget(separator)
        button = QPushButton(label)
        button.setObjectName("crumbCurrent" if current else "crumb")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, prefix=prefix: self._on_crumb(prefix))
        self.path_layout.addWidget(button)

    def _on_crumb(self, prefix: str) -> None:
        if monotonic() < self._nav_guard_until:
            return
        self._open_prefix(prefix)

    def _go_up(self) -> None:
        if not self.prefix or monotonic() < self._nav_guard_until:
            return
        trimmed = self.prefix.rstrip("/")
        parent = ""
        if "/" in trimmed:
            parent = trimmed.rsplit("/", 1)[0] + "/"
        self._open_prefix(parent)

    def _refresh(self) -> None:
        if self.session is not None and self.bucket_name:
            self._nav_guard_until = 0
            self._open_prefix(self.prefix)
            return
        if self.session is None:
            return
        session = self.session

        def ok(buckets: object) -> None:
            self._fill_buckets(sorted(buckets, key=lambda bucket: bucket.name.casefold()))  # type: ignore[arg-type]
            self.statusBar().showMessage(tr("buckets_refreshed"))

        self._submit("buckets", session.list_buckets, ok, self._on_list_error)

    def _on_current_cell(self, row: int, _column: int, _previous_row: int, _previous_column: int) -> None:
        self._activate(row, navigate=False)

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        self._activate(row, navigate=False)

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        self._activate(row, navigate=True)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt-API
        if watched is self.object_table and event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.SelectAll):
                self._select_visible_rows()
                return True
            if event.matches(QKeySequence.StandardKey.Copy):
                self._copy_files()
                return True
            if event.matches(QKeySequence.StandardKey.Paste):
                self._paste_files()
                return True
            if event.key() == Qt.Key.Key_Delete:
                self._delete_selected()
                return True
        return super().eventFilter(watched, event)

    def _select_visible_rows(self) -> None:
        selection = self.object_table.selectionModel()
        if selection is None:
            return
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        selection.clearSelection()
        for index, row in enumerate(self._rows):
            if row.is_up or self.object_table.isRowHidden(index):
                continue
            selection.select(self.object_table.model().index(index, 0), flags)

    def _activate_selected(self) -> None:
        self._activate(self.object_table.currentRow(), navigate=True)

    def _activate(self, index: int, navigate: bool) -> None:
        if index < 0 or index >= len(self._rows):
            return
        if navigate and monotonic() < self._nav_guard_until:
            return
        row = self._rows[index]
        if row.is_up:
            if navigate:
                self._go_up()
            return
        entry = row.entry
        if entry is None:
            return
        if entry.is_folder:
            if navigate:
                self._open_prefix(entry.key)
            else:
                self._show_message_preview(entry.name, tr("open_folder"))
            return
        self._load_preview(entry)

    def _apply_bucket_filter(self) -> None:
        query = self.bucket_filter.text().casefold().strip()
        visible = 0
        total = self.bucket_list.count()
        for index in range(total):
            item = self.bucket_list.item(index)
            if item is None:
                continue
            hidden = bool(query) and query not in item.text().casefold()
            item.setHidden(hidden)
            if not hidden:
                visible += 1
        if not total:
            self.bucket_count.setText("")
        elif query:
            self.bucket_count.setText(f"{visible} / {total}")
        else:
            self.bucket_count.setText(str(total))

    def _apply_filter(self) -> None:
        query = self.filter_edit.text().casefold().strip()
        matched = 0
        listed = 0
        for index, row in enumerate(self._rows):
            if row.is_up or not query:
                self.object_table.setRowHidden(index, False)
                if not row.is_up:
                    listed += 1
                    matched += 1
                continue
            name = row.entry.name.casefold() if row.entry is not None else ""
            hidden = query not in name
            self.object_table.setRowHidden(index, hidden)
            listed += 1
            if not hidden:
                matched += 1
        self.file_count.setText(f"{matched} / {listed}" if query and listed else "")

    def _load_preview(self, entry: ObjectEntry) -> None:
        if self._preview_dirty and (self._current_entry is None or entry.key != self._current_entry.key):
            answer = QMessageBox.question(
                self,
                tr("discard_title"),
                tr("discard_body"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._reselect_current_entry()
                return
            self._preview_dirty = False
        if entry.key == self._inflight_key or self.session is None:
            return
        self._inflight_key = entry.key
        self._current_entry = entry
        self.preview_title.setText(entry.name)
        self._set_badge("…")
        self.preview_meta.setText("" if entry.size is None else format_size(entry.size))
        self.preview_notice.hide()
        self._show_message_preview(entry.name, tr("loading_preview"))
        self._set_badge("…")
        self.download_button.setEnabled(True)
        self.copy_button.setEnabled(False)
        self.preview_dock.setWindowTitle(tr("preview_named", name=entry.name))
        session = self.session
        bucket = self.bucket_name
        key = entry.key

        def work() -> Preview:
            limit = TIFF_PREVIEW_BYTE_LIMIT if is_tiff(key) else PREVIEW_BYTE_LIMIT
            fetched = session.fetch(bucket, key, limit)
            if is_tiff(key, fetched.content_type) and fetched.truncated and limit < TIFF_PREVIEW_BYTE_LIMIT:
                fetched = session.fetch(bucket, key, TIFF_PREVIEW_BYTE_LIMIT)
            if is_tiff(key, fetched.content_type):
                return build_preview(
                    key,
                    fetched.data,
                    content_type=fetched.content_type or "image/tiff",
                    size=fetched.size,
                    truncated=fetched.truncated,
                )
            return build_preview(
                key,
                fetched.data,
                content_type=fetched.content_type,
                size=fetched.size,
                truncated=fetched.truncated,
            )

        def ok(preview: object) -> None:
            if self._inflight_key != key:
                return
            self._show_preview(preview, entry)  # type: ignore[arg-type]

        def err(message: str) -> None:
            if self._inflight_key != key:
                return
            self._inflight_key = None
            self._set_badge("")
            self._show_message_preview(entry.name, message)

        self._submit("preview", work, ok, err)

    def _show_preview(self, preview: Preview, entry: ObjectEntry) -> None:
        self._current_entry = entry
        self.preview_title.setText(preview.filename)
        self.preview_dock.setWindowTitle(tr("preview_named", name=preview.filename))
        self._set_badge(_badge_for(preview.kind))
        meta_parts = [format_size(preview.size)]
        if preview.content_type:
            meta_parts.append(preview.content_type)
        self.preview_meta.setText(" · ".join(part for part in meta_parts if part and part != "—"))
        self._preview_text_cache = preview.text
        if preview.notice and preview.kind not in {"binary", "empty"}:
            self.preview_notice.setText(preview.notice)
            self.preview_notice.show()
        else:
            self.preview_notice.hide()
        self.download_button.setEnabled(True)
        if preview.kind != "tiff":
            self.preview_image.set_source(QPixmap())
        editable = preview.kind in EDITABLE_KINDS and not preview.truncated and bool(preview.text or preview.kind == "empty")
        if preview.kind not in EDITABLE_KINDS or preview.truncated:
            self._set_text_editor("", editable=False, language="")
        if preview.kind in {"csv", "tsv"} and preview.headers:
            self._fill_preview_table(preview)
            self.preview_stack.setCurrentWidget(self.preview_table)
            self.copy_button.setEnabled(bool(preview.text))
            return
        if preview.kind in {"binary", "empty"}:
            self.copy_button.setEnabled(False)
            self._show_message_preview(preview.filename, preview.notice or tr("no_preview"))
            self._set_badge(_badge_for(preview.kind))
            return
        if preview.kind == "tiff":
            self.copy_button.setEnabled(False)
            pixmap = QPixmap()
            if preview.image and pixmap.loadFromData(preview.image, "PNG"):
                self.preview_image.set_source(pixmap)
                self.preview_stack.setCurrentWidget(self.preview_image_page)
                return
            self._show_message_preview(preview.filename, preview.notice or tr("no_tiff"))
            self._set_badge("TIFF")
            return
        self._preview_save_type = content_type_for_save(preview.kind, preview.content_type)
        self._set_text_editor(preview.text, editable=editable, language=highlight_language(preview.kind))
        self.preview_stack.setCurrentWidget(self.preview_text)
        self.copy_button.setEnabled(bool(preview.text))

    def _fill_preview_table(self, preview: Preview) -> None:
        table = self.preview_table
        table.clear()
        table.setColumnCount(len(preview.headers))
        table.setHorizontalHeaderLabels(preview.headers)
        table.setRowCount(len(preview.rows))
        numbers = preview.row_numbers or list(range(1, len(preview.rows) + 1))
        table.setVerticalHeaderLabels([str(number) for number in numbers])
        for row_index, row in enumerate(preview.rows):
            for column, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                table.setItem(row_index, column, item)
        header = table.horizontalHeader()
        if len(preview.headers) <= 6:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)
        table.verticalHeader().setVisible(True)

    def _show_message_preview(self, title: str, message: str) -> None:
        self.preview_title.setText(title)
        self.preview_message.setText(message)
        self.preview_stack.setCurrentWidget(self.preview_message_page)
        self._preview_text_cache = ""
        self._set_text_editor("", editable=False, language="")
        self.copy_button.setEnabled(False)

    def _set_badge(self, text: str) -> None:
        self.preview_badge.setText(text)
        self.preview_badge.setVisible(bool(text) and text != "…")

    def _copy_preview(self) -> None:
        if self.preview_stack.currentWidget() is self.preview_text:
            text = self.preview_text.toPlainText()
        else:
            text = self._preview_text_cache
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage(tr("copied"), 3000)

    def _set_text_editor(self, text: str, *, editable: bool, language: str) -> None:
        self._preview_editable = editable
        self.preview_text.blockSignals(True)
        self.highlighter.set_language(language)
        self.preview_text.setPlainText(text)
        self.preview_text.setReadOnly(not editable)
        self.preview_text.blockSignals(False)
        self._preview_dirty = False
        self.save_edit_button.setVisible(editable)
        self.save_edit_button.setEnabled(False)

    def _on_preview_edited(self) -> None:
        if not self._preview_editable:
            return
        self._preview_dirty = self.preview_text.toPlainText() != self._preview_text_cache
        self.save_edit_button.setEnabled(self._preview_dirty and self.session is not None and self._current_entry is not None)

    def _reselect_current_entry(self) -> None:
        if self._current_entry is None:
            return
        for index, row in enumerate(self._rows):
            if row.entry is not None and row.entry.key == self._current_entry.key:
                self.object_table.blockSignals(True)
                self.object_table.selectRow(index)
                self.object_table.blockSignals(False)
                return

    def _save_preview_edits(self) -> None:
        entry = self._current_entry
        if entry is None or entry.is_folder or self.session is None or not self._preview_dirty:
            return
        text = self.preview_text.toPlainText()
        data = text.encode("utf-8")
        content_type = self._preview_save_type
        session = self.session
        bucket = self.bucket_name
        key = entry.key
        self.statusBar().showMessage(tr("writing", name=entry.name))

        def work() -> str:
            session.put_text(bucket, key, data, content_type)
            return key

        def done(_key: object) -> None:
            if self._current_entry is not None and self._current_entry.key == key:
                self._preview_text_cache = text
                if self.preview_text.toPlainText() == text:
                    self._preview_dirty = False
                    self.save_edit_button.setEnabled(False)
                else:
                    self._on_preview_edited()
            self._set_banner(None)
            self.statusBar().showMessage(tr("written", key=key))

        self._submit("save-text", work, done, self._set_banner)

    def _download(self) -> None:
        entry = self._current_entry
        if entry is None or entry.is_folder or self.session is None:
            return
        self._download_entries([entry])

    def _download_selected(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        self._download_entries(entries)

    def _delete_selected(self) -> None:
        entries = self._selected_entries()
        if self.session is None or not entries or not self.bucket_name:
            return
        names = [entry.name for entry in entries]
        visible = names[:12]
        more = tr("replace_more", count=len(names) - 12) if len(names) > 12 else ""
        body = tr("delete_body", names="\n".join(visible) + more)
        if any(entry.is_folder for entry in entries):
            body += tr("delete_folders")
        answer = QMessageBox.question(self, tr("delete_title"), body)
        if answer != QMessageBox.StandardButton.Yes:
            return
        session = self.session
        bucket = self.bucket_name
        folder = self.prefix
        self._set_banner(None)
        self._download_cancel = None
        self._begin_transfer(0, kind="delete")

        def work() -> tuple[int, bool]:
            keys, capped = _keys_for_delete(session, bucket, entries)
            self._transfer_signals.planned.emit(max(len(keys), 1))
            count = session.delete_keys(
                bucket,
                keys,
                progress=lambda amount: self._transfer_signals.advanced.emit(int(amount)),
            )
            return count, capped

        def done(payload: object) -> None:
            count, capped = payload  # type: ignore[misc]
            self._set_banner(None)
            message = tr("deleted_one") if count == 1 else tr("deleted_many", count=count)
            if capped:
                message += tr("list_capped", limit=MAX_LISTED)
            self.statusBar().showMessage(message)
            if self.session is not None and self.bucket_name == bucket and self.prefix == folder:
                self._nav_guard_until = 0
                self._current_entry = None
                self._open_prefix(folder)

        self._submit("delete", work, done, self._set_banner, track_transfer=True)

    def _show_file_menu(self, pos) -> None:
        index = self.object_table.indexAt(pos)
        if index.isValid():
            selected = {item.row() for item in self.object_table.selectionModel().selectedRows()}
            if index.row() not in selected:
                self.object_table.selectRow(index.row())
        entries = self._selected_entries()
        menu = QMenu(self)
        copy_path = menu.addAction(tr("copy_path"))
        copy_name = menu.addAction(tr("copy_name"))
        menu.addSeparator()
        copy_files = menu.addAction(tr("copy_files"))
        paste_files = menu.addAction(tr("paste_files"))
        menu.addSeparator()
        delete_files = menu.addAction(tr("delete"))
        has_entries = bool(entries)
        copy_path.setEnabled(has_entries)
        copy_name.setEnabled(has_entries)
        copy_files.setEnabled(has_entries)
        paste_files.setEnabled(bool(self._file_clipboard) and self.session is not None and bool(self.bucket_name))
        delete_files.setEnabled(has_entries)
        chosen = menu.exec(self.object_table.viewport().mapToGlobal(pos))
        if chosen is copy_path:
            self._copy_paths()
        elif chosen is copy_name:
            self._copy_names()
        elif chosen is copy_files:
            self._copy_files()
        elif chosen is paste_files:
            self._paste_files()
        elif chosen is delete_files:
            self._delete_selected()

    def _copy_paths(self) -> None:
        entries = self._selected_entries()
        if not entries or not self.bucket_name:
            return
        QApplication.clipboard().setText("\n".join(f"{self.bucket_name}/{entry.key}" for entry in entries))
        self.statusBar().showMessage(tr("copied_path"))

    def _copy_names(self) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        QApplication.clipboard().setText("\n".join(entry.name for entry in entries))
        self.statusBar().showMessage(tr("copied_name"))

    def _copy_files(self) -> None:
        entries = self._selected_entries()
        if not entries or not self.bucket_name:
            return
        self._file_clipboard = [
            CopiedObject(bucket=self.bucket_name, key=entry.key, name=entry.name, is_folder=entry.is_folder)
            for entry in entries
        ]
        count = len(self._file_clipboard)
        message = tr("copied_files_one") if count == 1 else tr("copied_files_many", count=count)
        self.statusBar().showMessage(message)

    def _paste_files(self) -> None:
        if self.session is None or not self.bucket_name or not self._file_clipboard:
            return
        session = self.session
        bucket = self.bucket_name
        folder = self.prefix
        items = list(self._file_clipboard)

        def work() -> int:
            pairs: list[tuple[str, str, str]] = []
            for item in items:
                nested: list[str] = []
                if item.is_folder:
                    nested, _capped = session.list_object_keys(item.bucket, item.key)
                pairs.extend(paste_pairs(item, folder, nested))
            copied = 0
            self._transfer_signals.planned.emit(max(len(pairs), 1))
            for source_bucket, source_key, dest_key in pairs:
                if source_bucket == bucket and source_key == dest_key:
                    continue
                session.copy_key(source_bucket, source_key, bucket, dest_key)
                copied += 1
                self._transfer_signals.advanced.emit(1)
            return copied

        def done(count: object) -> None:
            self._set_banner(None)
            amount = int(count)  # type: ignore[arg-type]
            if amount == 0:
                self.statusBar().showMessage(tr("paste_same"))
            elif amount == 1:
                self.statusBar().showMessage(tr("pasted_one"))
            else:
                self.statusBar().showMessage(tr("pasted_many", count=amount))
            if self.session is not None and self.bucket_name == bucket and self.prefix == folder:
                self._nav_guard_until = 0
                self._open_prefix(folder)

        self._download_cancel = None
        self._begin_transfer(0, kind="copy")
        self._submit("paste", work, done, self._set_banner, track_transfer=True)

    def _selected_entries(self) -> list[ObjectEntry]:
        selected: list[ObjectEntry] = []
        seen: set[str] = set()
        for index in self.object_table.selectionModel().selectedRows():
            row_index = index.row()
            if row_index < 0 or row_index >= len(self._rows) or self.object_table.isRowHidden(row_index):
                continue
            row = self._rows[row_index]
            entry = row.entry
            if row.is_up or entry is None or entry.key in seen:
                continue
            seen.add(entry.key)
            selected.append(entry)
        return selected

    def _download_entries(self, entries: list[ObjectEntry]) -> None:
        if self.session is None or not entries:
            return
        session = self.session
        bucket = self.bucket_name
        prefix = self.prefix
        single_file = len(entries) == 1 and not entries[0].is_folder
        if single_file:
            destination, _selected = QFileDialog.getSaveFileName(self, tr("save_one"), entries[0].name)
            if not destination:
                return
            self.statusBar().showMessage(tr("saving", name=entries[0].name))
            size = int(entries[0].size or 0)
            self._download_cancel = CancelFlag()
            self._begin_transfer(size if size > 0 else 1, kind="download")

            def work_one() -> str:
                self._ensure_download_continues()
                if size > 0:
                    self._transfer_one(
                        size,
                        lambda progress: session.download(
                            bucket,
                            entries[0].key,
                            destination,
                            progress=progress,
                            cancel=self._download_cancel,
                        ),
                    )
                else:
                    session.download(bucket, entries[0].key, destination, cancel=self._download_cancel)
                    self._transfer_signals.advanced.emit(1)
                return destination

            self._submit(
                "download",
                work_one,
                lambda path: self.statusBar().showMessage(tr("saved_at", path=path)),
                self._on_download_error,
                track_transfer=True,
            )
            return

        directory = QFileDialog.getExistingDirectory(self, tr("choose_download_dir"))
        if not directory:
            return
        self.statusBar().showMessage(tr("saving_files"))
        self._download_cancel = CancelFlag()
        self._begin_transfer(0, kind="download")

        def work_many() -> tuple[list[str], bool]:
            self._ensure_download_continues()
            capped = False
            jobs: list[tuple[str, str, int]] = []
            for entry in entries:
                found, entry_capped = _files_for_entry(session, bucket, prefix, entry)
                capped = capped or entry_capped
                jobs.extend(found)
            self._ensure_download_continues()
            total = sum(size for _key, _relative, size in jobs)
            use_bytes = total > 0
            self._transfer_signals.planned.emit(total if use_bytes else len(jobs))
            saved: list[str] = []
            for key, relative, size in jobs:
                self._ensure_download_continues()
                target = unique_path(destination_for(Path(directory), relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                if use_bytes:
                    self._transfer_one(
                        size,
                        lambda progress, key=key, target=target: session.download(
                            bucket,
                            key,
                            str(target),
                            progress=progress,
                            cancel=self._download_cancel,
                        ),
                    )
                else:
                    session.download(bucket, key, str(target), cancel=self._download_cancel)
                    self._transfer_signals.advanced.emit(1)
                saved.append(str(target))
            return saved, capped

        def done(payload: object) -> None:
            saved, capped = payload  # type: ignore[misc]
            if not saved:
                self._set_banner(tr("no_files_to_save"))
                self.statusBar().showMessage(tr("no_files_saved"))
                return
            self._set_banner(None)
            self.statusBar().showMessage(saved_message(len(saved), directory, capped, MAX_LISTED))

        self._submit("download", work_many, done, self._on_download_error, track_transfer=True)

    def _upload_files(self) -> None:
        if self.session is None or not self.bucket_name:
            return
        paths, _selected = QFileDialog.getOpenFileNames(self, tr("choose_upload_files"))
        if not paths:
            return
        try:
            plan = upload_plan(self.prefix, paths)
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        self._upload_plan(plan)

    def _upload_folder(self) -> None:
        if self.session is None or not self.bucket_name:
            return
        directory = QFileDialog.getExistingDirectory(self, tr("choose_upload_folder"))
        if not directory:
            return
        try:
            plan = folder_upload_plan(self.prefix, directory)
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        self._upload_plan(plan)

    def _create_folder(self) -> None:
        if self.session is None or not self.bucket_name:
            return
        name, accepted = QInputDialog.getText(self, tr("new_folder_title"), tr("new_folder_label"))
        if not accepted:
            return
        try:
            key = folder_marker_key(self.prefix, name)
        except ValueError as exc:
            self._set_banner(str(exc))
            return
        folder_name = key.rstrip("/").rsplit("/", 1)[-1]
        exists = any(
            row.entry is not None and row.entry.is_folder and row.entry.name == folder_name
            for row in self._rows
        )
        if exists:
            self._set_banner(tr("new_folder_exists", name=folder_name))
            return
        session = self.session
        bucket = self.bucket_name
        folder = self.prefix
        self._set_banner(None)

        def work() -> str:
            session.create_folder(bucket, key)
            return key

        def done(_key: object) -> None:
            self._set_banner(None)
            if self.session is not None and self.bucket_name == bucket and self.prefix == folder:
                self._nav_guard_until = 0
                self._open_prefix(folder)
            self.statusBar().showMessage(tr("new_folder_created", name=folder_name))

        self._submit("upload", work, done, self._set_banner)

    def _upload_plan(self, plan: list[tuple[str, str]]) -> None:
        if not self._confirm_existing_uploads(plan):
            return
        destination = upload_destination_label(self.bucket_name, self.prefix)
        count = len(plan)
        noun = tr("noun_file") if count == 1 else tr("noun_files")
        session = self.session
        bucket = self.bucket_name
        folder = self.prefix
        sizes = [Path(source).stat().st_size for source, _key in plan]
        total = sum(sizes)
        use_bytes = total > 0
        self.statusBar().showMessage(tr("uploading", count=count, noun=noun, destination=destination))
        self._download_cancel = None
        self._begin_transfer(total if use_bytes else count, kind="upload")

        def work() -> int:
            for (source, key), size in zip(plan, sizes, strict=True):
                if use_bytes:
                    self._transfer_one(
                        size,
                        lambda progress, source=source, key=key: session.upload(
                            bucket, key, source, progress=progress
                        ),
                    )
                else:
                    session.upload(bucket, key, source)
                    self._transfer_signals.advanced.emit(1)
            return count

        def done(_count: object) -> None:
            self._set_banner(None)
            self.statusBar().showMessage(uploaded_message(count, destination))
            if self.session is not None and self.bucket_name == bucket and self.prefix == folder:
                self._nav_guard_until = 0
                self._open_prefix(folder)

        self._submit("upload", work, done, self._set_banner, track_transfer=True)

    def _confirm_existing_uploads(self, plan: list[tuple[str, str]]) -> bool:
        existing = {
            row.entry.key
            for row in self._rows
            if row.entry is not None and not row.is_up and not row.entry.is_folder
        }
        folder_keys = {
            row.entry.key
            for row in self._rows
            if row.entry is not None and row.entry.is_folder
        }
        current = self.prefix or ""
        if current and not current.endswith("/"):
            current += "/"
        remote_folders: set[str] = set()
        for _source, key in plan:
            if not key.startswith(current):
                continue
            remainder = key[len(current) :]
            if "/" not in remainder:
                continue
            folder_key = current + remainder.split("/", 1)[0] + "/"
            if folder_key in folder_keys:
                remote_folders.add(folder_key)
        if remote_folders and self.session is not None:
            self.statusBar().showMessage(tr("checking_files"))
            QApplication.processEvents()
            for folder_key in remote_folders:
                try:
                    remote_keys, _capped = self.session.list_file_keys(self.bucket_name, folder_key)
                except Exception as exc:
                    self._set_banner(str(exc))
                    return False
                existing.update(remote_keys)
        collisions = colliding_keys(plan, existing)
        if not collisions:
            return True
        visible = [key.rsplit("/", 1)[-1] for key in collisions[:12]]
        more = tr("replace_more", count=len(collisions) - 12) if len(collisions) > 12 else ""
        answer = QMessageBox.question(
            self,
            tr("replace_title"),
            tr("replace_body", names="\n".join(visible) + more),
        )
        return answer == QMessageBox.StandardButton.Yes

    def _clear_browser(self) -> None:
        self.bucket_name = ""
        self.prefix = ""
        self._rows = []
        self._current_entry = None
        self._inflight_key = None
        self.bucket_list.clear()
        self.bucket_count.setText("")
        self.object_table.setRowCount(0)
        self.files_title.setText(tr("files"))
        self.file_placeholder.setText(tr("files_placeholder"))
        self.file_stack.setCurrentWidget(self.file_placeholder)
        self._render_path()
        self._show_idle_preview()

    def _show_idle_preview(self) -> None:
        self.preview_dock.setWindowTitle(tr("preview"))
        self._set_badge("")
        self.preview_meta.setText("")
        self.preview_notice.hide()
        self._show_message_preview(tr("preview"), tr("preview_idle"))
        self.download_button.setEnabled(False)

    def _set_banner(self, text: str | None) -> None:
        if not text:
            self.banner.hide()
            self.banner.clear()
            return
        self.banner.setText(text)
        self.banner.show()

    def _sync_buttons(self) -> None:
        connected = self.session is not None
        self.connect_button.setEnabled(not self._connecting)
        self.connect_button.setToolTip(tr("connecting") if self._connecting else tr("connect"))
        self._set_connect_connected(connected)
        self._apply_connection_labels()
        self.disconnect_button.setEnabled(connected and not self._connecting)
        self.up_button.setEnabled(connected and bool(self.prefix))
        self.refresh_button.setEnabled(connected)
        selected = connected and bool(self._selected_entries())
        self.save_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)
        self.upload_button.setEnabled(connected and bool(self.bucket_name))
        self.upload_folder_button.setEnabled(connected and bool(self.bucket_name))
        self.new_folder_button.setEnabled(connected and bool(self.bucket_name))
        file_selected = self._current_entry is not None and not self._current_entry.is_folder
        self.download_button.setEnabled(file_selected)

    def _set_connect_connected(self, connected: bool) -> None:
        button = self.connect_button
        if button.property("connected") is connected:
            return
        button.setProperty("connected", connected)
        button.style().unpolish(button)
        button.style().polish(button)

    def _begin_transfer(self, total: int, *, kind: str) -> None:
        self._transfer_kind = kind
        self._transfer_active = True
        self._transfer_done = 0
        self._transfer_total = max(0, int(total))
        self._transfer_peak = 0
        self.transfer_label.setText(
            tr("transfer_download")
            if kind == "download"
            else tr("transfer_delete")
            if kind == "delete"
            else tr("transfer_copy")
            if kind == "copy"
            else tr("transfer_upload")
        )
        self.cancel_download_button.setVisible(kind == "download")
        self.cancel_download_button.setEnabled(kind == "download")
        self._show_transfer_value()
        self.transfer_row.show()
        self.busy_bar.hide()

    def _show_transfer_value(self) -> None:
        total = self._transfer_total
        done = self._transfer_done
        if total > 0:
            shown = min(done, total)
            self.progress.setRange(0, total)
            self.progress.setValue(shown)
            self.progress.setTextVisible(True)
            self.progress.setFormat("%p%")
            self.transfer_amount.setText(f"{format_size(shown)} / {format_size(total)}")
            self.progress.setToolTip(self.transfer_amount.text())
            return
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFormat("")
        self.transfer_amount.setText("")
        self.progress.setToolTip("")

    def _on_transfer_planned(self, total: int) -> None:
        if not self._transfer_active:
            return
        self._transfer_total = max(0, int(total))
        self._show_transfer_value()

    def _on_bytes_advanced(self, amount: int) -> None:
        if not self._transfer_active or amount <= 0:
            return
        self._transfer_done += amount
        self._transfer_peak = max(self._transfer_peak, self._transfer_done)
        if self._transfer_total > 0:
            shown = min(self._transfer_done, self._transfer_total)
            self.progress.setValue(shown)
            self.transfer_amount.setText(f"{format_size(shown)} / {format_size(self._transfer_total)}")
            self.progress.setToolTip(self.transfer_amount.text())

    def _transfer_one(self, expected: int, action: Callable[[Callable[[int], None]], None]) -> None:
        sent = 0

        def on_bytes(amount: int) -> None:
            nonlocal sent
            amount = max(0, int(amount))
            sent += amount
            if amount:
                self._transfer_signals.advanced.emit(amount)

        action(on_bytes)
        if sent < expected:
            self._transfer_signals.advanced.emit(expected - sent)

    def _cancel_download(self) -> None:
        flag = self._download_cancel
        if flag is None:
            return
        flag.cancel()
        self.cancel_download_button.setEnabled(False)
        self.statusBar().showMessage(tr("download_cancelling"))

    def _ensure_download_continues(self) -> None:
        flag = self._download_cancel
        if flag is not None and flag.cancelled:
            raise DownloadCancelled()

    def _on_download_error(self, message: str) -> None:
        if message == tr("download_cancelled"):
            self._set_banner(None)
            self.statusBar().showMessage(tr("download_cancelled"))
            return
        self._set_banner(message)

    def _finish_transfer(self) -> None:
        if not self._transfer_active:
            return
        self._transfer_active = False
        self._download_cancel = None
        self.progress.setRange(0, 0)
        self.progress.setValue(0)
        self.progress.setFormat("")
        self.progress.setToolTip("")
        self.transfer_amount.setText("")
        self.transfer_row.hide()

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self._busy += 1
        else:
            self._busy = max(0, self._busy - 1)
        self.busy_bar.setVisible(self._busy > 0 and not self._transfer_active)

    def _submit(
        self,
        channel: str,
        fn: Callable[[], object],
        on_ok: Callable,
        on_err: Callable,
        track_transfer: bool = False,
    ) -> None:
        epoch = self.conn_epoch
        self._gen[channel] = self._gen.get(channel, 0) + 1
        generation = self._gen[channel]
        self._set_busy(True)

        def ok(result: object, epoch: int = epoch, generation: int = generation) -> None:
            if track_transfer:
                self._finish_transfer()
            self._set_busy(False)
            if self._closing or epoch != self.conn_epoch or generation != self._gen[channel]:
                return
            on_ok(result)

        def err(message: str, epoch: int = epoch, generation: int = generation) -> None:
            if track_transfer:
                self._finish_transfer()
            self._set_busy(False)
            if self._closing or epoch != self.conn_epoch or generation != self._gen[channel]:
                return
            on_err(message)

        self.tasks.submit(fn, ok, err)


def _keys_for_delete(session: S3Session, bucket: str, entries: list[ObjectEntry]) -> tuple[list[str], bool]:
    keys: list[str] = []
    capped = False
    lister = getattr(session, "list_object_keys", None)
    for entry in entries:
        if entry.is_folder:
            if lister is not None:
                found, entry_capped = lister(bucket, entry.key)
            else:
                found, entry_capped = session.list_file_keys(bucket, entry.key)
            capped = capped or entry_capped
            keys.extend(found)
            marker = entry.key if entry.key.endswith("/") else f"{entry.key}/"
            keys.append(marker)
        else:
            keys.append(entry.key)
    unique: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique, capped


def _files_for_entry(
    session: S3Session,
    bucket: str,
    prefix: str,
    entry: ObjectEntry,
) -> tuple[list[tuple[str, str, int]], bool]:
    if not entry.is_folder:
        return [(entry.key, entry.name, int(entry.size or 0))], False
    list_files = getattr(session, "list_files", None)
    if list_files is not None:
        records, capped = list_files(bucket, entry.key)
        return [(key, relative_name(prefix, key), int(size)) for key, size in records], capped
    keys, capped = session.list_file_keys(bucket, entry.key)
    return [(key, relative_name(prefix, key), 0) for key in keys], capped


def _painted_icon(draw, color: QColor) -> QPixmap:
    side = 64
    pixmap = QPixmap(side, side)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    draw(painter)
    painter.end()
    return pixmap


def _themed_icon(draw, color: QColor, muted: QColor) -> QIcon:
    icon = QIcon()
    normal = _painted_icon(draw, color)
    quiet = _painted_icon(draw, muted)
    icon.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(quiet, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(normal, QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(normal, QIcon.Mode.Selected, QIcon.State.Off)
    return icon


def _draw_plug(painter: QPainter) -> None:
    painter.drawRoundedRect(16, 16, 26, 32, 6, 6)
    painter.drawLine(42, 26, 56, 26)
    painter.drawLine(42, 38, 56, 38)
    painter.drawLine(8, 32, 16, 32)


def _draw_upload(painter: QPainter) -> None:
    painter.drawLine(32, 36, 32, 10)
    painter.drawLine(18, 24, 32, 10)
    painter.drawLine(46, 24, 32, 10)
    painter.drawLine(14, 40, 14, 54)
    painter.drawLine(14, 54, 50, 54)
    painter.drawLine(50, 54, 50, 40)


def _draw_folder_outline(painter: QPainter, left: int, top: int, width: int, height: int) -> None:
    tab = max(10, width // 3)
    painter.drawLine(left, top + 8, left + tab, top + 8)
    painter.drawLine(left + tab, top + 8, left + tab + 6, top + 14)
    painter.drawLine(left + tab + 6, top + 14, left + width, top + 14)
    painter.drawLine(left + width, top + 14, left + width, top + height)
    painter.drawLine(left + width, top + height, left, top + height)
    painter.drawLine(left, top + height, left, top + 8)


def _draw_folder_upload(painter: QPainter) -> None:
    pen = painter.pen()
    pen.setWidth(4)
    painter.setPen(pen)
    _draw_folder_outline(painter, 4, 16, 34, 42)
    painter.drawLine(48, 40, 48, 12)
    painter.drawLine(40, 20, 48, 12)
    painter.drawLine(56, 20, 48, 12)


def _draw_folder_new(painter: QPainter) -> None:
    pen = painter.pen()
    pen.setWidth(4)
    painter.setPen(pen)
    _draw_folder_outline(painter, 4, 14, 36, 42)
    painter.drawLine(40, 34, 58, 34)
    painter.drawLine(49, 23, 49, 45)


def _draw_trash(painter: QPainter) -> None:
    pen = painter.pen()
    pen.setWidth(4)
    painter.setPen(pen)
    painter.drawLine(14, 16, 50, 16)
    painter.drawLine(26, 16, 28, 10)
    painter.drawLine(28, 10, 36, 10)
    painter.drawLine(36, 10, 38, 16)
    painter.drawLine(18, 22, 22, 54)
    painter.drawLine(22, 54, 42, 54)
    painter.drawLine(42, 54, 46, 22)
    painter.drawLine(28, 28, 30, 46)
    painter.drawLine(36, 28, 34, 46)


_MODE_ICONS: dict[bool, QIcon] = {}


def _mode_icon(sun: bool) -> QIcon:
    cached = _MODE_ICONS.get(sun)
    if cached is not None:
        return cached
    side = 64
    pixmap = QPixmap(side, side)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = QColor("#e39b12")
    if sun:
        painter.translate(side / 2, side / 2)
        painter.setPen(QPen(color, 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for _step in range(8):
            painter.drawLine(0, -16, 0, -28)
            painter.rotate(45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(-12, -12, 24, 24)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        body = QPainterPath()
        body.addEllipse(12, 10, 40, 40)
        cut = QPainterPath()
        cut.addEllipse(26, 6, 36, 36)
        painter.fillPath(body.subtracted(cut), color)
    painter.end()
    icon = QIcon(pixmap)
    _MODE_ICONS[sun] = icon
    return icon


def format_size(size: int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{int(size)} B"


def format_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        return value.strftime("%d.%m.%Y %H:%M")
    return value.astimezone().strftime("%d.%m.%Y %H:%M")


def _badge_for(kind: str) -> str:
    return {
        "json": "JSON",
        "ndjson": "NDJSON",
        "yaml": "YAML",
        "xml": "XML",
        "html": "HTML",
        "svg": "SVG",
        "csv": "CSV",
        "tsv": "TSV",
        "text": "Text",
        "tiff": "TIFF",
        "empty": "Leer",
        "binary": "Datei",
    }.get(kind, "")


def _as_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _close_quietly(session: S3Session) -> bool:
    try:
        session.close()
    except Exception:
        return False
    return True
