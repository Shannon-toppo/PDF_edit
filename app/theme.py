"""ライト/ダークテーマの適用（Fusion スタイル + QPalette）。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _dark_palette() -> QPalette:
    p = QPalette()
    base = QColor(45, 45, 48)
    alt = QColor(38, 38, 40)
    text = QColor(220, 220, 220)
    disabled = QColor(120, 120, 120)
    highlight = QColor(58, 130, 210)

    p.setColor(QPalette.Window, base)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, alt)
    p.setColor(QPalette.AlternateBase, base)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, base)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, Qt.red)
    p.setColor(QPalette.Link, highlight)
    p.setColor(QPalette.Highlight, highlight)
    p.setColor(QPalette.HighlightedText, Qt.white)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, disabled)
    return p


def apply_theme(app: QApplication, dark: bool) -> None:
    app.setStyle("Fusion")
    if dark:
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())
