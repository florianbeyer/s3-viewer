"""Helles und dunkles Erscheinungsbild."""

from __future__ import annotations


def stylesheet(dark: bool) -> str:
    if dark:
        colors = {
            "bg": "#1b2430",
            "card": "#243041",
            "text": "#e5e7eb",
            "muted": "#94a3b8",
            "line": "#3d4d63",
            "input": "#1b2430",
            "hover": "#2c3b50",
            "section": "#99f6e4",
            "selection": "#134e4a",
            "selection_text": "#ccfbf1",
            "header": "#1e293b",
            "header_text": "#94a3b8",
            "alt": "#202b3a",
            "crumb": "#5eead4",
            "crumb_current": "#e5e7eb",
            "disabled": "#64748b",
            "disabled_bg": "#1e293b",
            "fold_hover": "#134e4a",
            "icon_hover": "#134e4a",
            "banner_bg": "#3f1d24",
            "banner_text": "#fecdd3",
            "banner_line": "#9f1239",
            "notice": "#fdba74",
            "badge_bg": "#134e4a",
            "badge_text": "#ccfbf1",
        }
    else:
        colors = {
            "bg": "#eef2f5",
            "card": "#ffffff",
            "text": "#1f2933",
            "muted": "#627083",
            "line": "#d5dee8",
            "input": "#ffffff",
            "hover": "#f8fafc",
            "section": "#12312e",
            "selection": "#ccfbf1",
            "selection_text": "#134e4a",
            "header": "#f8fafc",
            "header_text": "#526174",
            "alt": "#f8fafc",
            "crumb": "#0f766e",
            "crumb_current": "#1f2933",
            "disabled": "#94a3b8",
            "disabled_bg": "#f1f5f9",
            "fold_hover": "#e6f4f1",
            "icon_hover": "#e6f4f1",
            "banner_bg": "#fde8e8",
            "banner_text": "#9f1239",
            "banner_line": "#fecdd3",
            "notice": "#9a3412",
            "badge_bg": "#ccfbf1",
            "badge_text": "#115e59",
        }
    return _TEMPLATE.format(**colors)


_TEMPLATE = """
QMainWindow, QWidget#root, QDockWidget, QDockWidget > QWidget {{
    background: {bg};
    color: {text};
}}
QFrame#connCard {{
    background: {card};
    border: 1px solid {line};
    border-radius: 12px;
}}
QPushButton#fold, QPushButton#langButton {{
    background: transparent;
    color: {text};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 13px;
    font-weight: 700;
    min-width: 28px;
}}
QPushButton#fold:hover, QPushButton#langButton:hover, QPushButton#iconButton:hover {{
    background: {fold_hover};
}}
QPushButton#iconButton {{
    background: {card};
    color: {text};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 4px;
}}
QPushButton#iconButton:disabled {{
    background: {disabled_bg};
    color: {disabled};
}}
QPushButton#iconButton:checked {{
    background: #0f766e;
    border-color: #0f766e;
}}
QLabel#section {{
    font-size: 15px;
    font-weight: 700;
    color: {section};
}}
QLabel#hint, QLabel#muted, QLabel#crumbSep {{
    color: {muted};
}}
QLabel#banner {{
    background: {banner_bg};
    color: {banner_text};
    border: 1px solid {banner_line};
    border-radius: 8px;
    padding: 8px 10px;
}}
QLabel#notice {{
    color: {notice};
}}
QLabel#badge {{
    background: {badge_bg};
    color: {badge_text};
    border-radius: 8px;
    padding: 2px 8px;
    font-weight: 700;
}}
QLabel#placeholder, QLabel#previewMessage {{
    color: {muted};
    font-size: 14px;
}}
QLineEdit, QComboBox {{
    background: {input};
    color: {text};
    border: 1px solid {line};
    border-radius: 7px;
    padding: 6px 8px;
    min-height: 20px;
    selection-background-color: #99f6e4;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid #0f766e;
}}
QComboBox QLineEdit {{
    background: transparent;
    color: {text};
    border: none;
    padding: 0;
    min-height: 0;
    selection-background-color: #99f6e4;
}}
QComboBox QAbstractItemView {{
    background: {card};
    color: {text};
    selection-background-color: {selection};
    selection-color: {selection_text};
}}
QPushButton {{
    background: {card};
    color: {text};
    border: 1px solid {line};
    border-radius: 7px;
    padding: 6px 12px;
}}
QPushButton:hover {{
    background: {hover};
}}
QPushButton:disabled {{
    color: {disabled};
    background: {disabled_bg};
}}
QPushButton#crumb, QPushButton#crumbCurrent {{
    border: none;
    background: transparent;
    padding: 2px 2px;
    font-weight: 650;
}}
QPushButton#crumb {{
    color: {crumb};
}}
QPushButton#crumbCurrent {{
    color: {crumb_current};
}}
QListWidget, QTableWidget {{
    background: {card};
    color: {text};
    border: 1px solid {line};
    border-radius: 10px;
    alternate-background-color: {alt};
}}
QListWidget::item {{
    padding: 7px 8px;
    border-radius: 6px;
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {selection};
    color: {selection_text};
}}
QHeaderView::section {{
    background: {header};
    color: {header_text};
    border: none;
    border-bottom: 1px solid {line};
    padding: 6px 8px;
    font-weight: 650;
}}
QTableWidget {{
    gridline-color: transparent;
}}
QPlainTextEdit#preview {{
    background: #111827;
    color: #e5e7eb;
    border: 1px solid {line};
    border-radius: 10px;
    padding: 8px;
    selection-background-color: #134e4a;
    selection-color: #ecfeff;
}}
QLabel#tiffPreview {{
    background: #1f2937;
    border-radius: 10px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QCheckBox {{
    spacing: 6px;
    color: {text};
}}
QSplitter::handle {{
    background: transparent;
}}
QWidget#transferRow {{
    background: {card};
    border: 1px solid {line};
    border-radius: 10px;
}}
QLabel#transferLabel {{
    font-weight: 700;
    color: {text};
}}
QPushButton#cancelTransfer {{
    background: {card};
    color: {text};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 4px 12px;
    font-weight: 700;
}}
QPushButton#cancelTransfer:hover {{
    background: {fold_hover};
}}
QPushButton#cancelTransfer:disabled {{
    color: {disabled};
    background: {disabled_bg};
}}
QProgressBar#transfer {{
    background: {input};
    color: {text};
    border: 1px solid {line};
    border-radius: 6px;
    text-align: center;
    min-height: 22px;
    max-height: 22px;
    font-weight: 700;
}}
QProgressBar#transfer::chunk {{
    background: #0f766e;
    border-radius: 5px;
}}
QToolTip {{
    background: {card};
    color: {text};
    border: 1px solid {line};
}}
"""
