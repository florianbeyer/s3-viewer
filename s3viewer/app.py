"""Startet das S3-Viewer-Fenster."""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from s3viewer.window import MainWindow


def main() -> None:
    os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
    app = QApplication(sys.argv)
    app.setApplicationName("s3viewer")
    app.setApplicationDisplayName("S3 Viewer")
    app.setOrganizationName("s3viewer")
    app.setDesktopFileName("s3-viewer")
    app.setStyle("Fusion")
    font = QFont("Ubuntu")
    font.setPointSize(11)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
