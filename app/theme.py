"""システム/ライト/ダークテーマの適用（Fusion スタイル + QPalette）。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# テーマモード（QSettings の "theme/mode" に保存する値）
THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"


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


def _set_color_scheme(app: QApplication, scheme) -> None:
    """Qt のカラースキームを指定（Qt 6.8+）。古い Qt では無視。"""
    try:
        app.styleHints().setColorScheme(scheme)
    except (AttributeError, TypeError):
        pass


def _system_is_dark(app: QApplication) -> bool:
    """OS のカラースキームがダークかどうか（Qt 6.5+）。判定不能なら False。"""
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except (AttributeError, TypeError):
        return False


def apply_theme(app: QApplication, mode: str) -> None:
    """テーマを適用する。mode は THEME_SYSTEM / THEME_LIGHT / THEME_DARK。"""
    app.setStyle("Fusion")
    if mode == THEME_DARK:
        _set_color_scheme(app, Qt.ColorScheme.Dark)
        dark = True
    elif mode == THEME_LIGHT:
        # 明示ライト: OS がダークでも Fusion の標準パレットをライトに固定する
        _set_color_scheme(app, Qt.ColorScheme.Light)
        dark = False
    else:  # THEME_SYSTEM
        _set_color_scheme(app, Qt.ColorScheme.Unknown)  # OS に追従
        dark = _system_is_dark(app)

    if dark:
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())
