"""fitz.Page を Qt の QImage に変換する。座標系は PDF と同じ左上原点 (pt)。

画面ピクセル = PDF ポイント x zoom。逆変換は scene 座標 / zoom。
"""
from __future__ import annotations

import fitz
from PySide6.QtGui import QImage


def render_page(page: fitz.Page, zoom: float = 1.0) -> QImage:
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
    # pix のバッファから切り離して所有権を Qt 側に持たせる
    return img.copy()


def render_thumbnail(page: fitz.Page, max_px: int = 160) -> QImage:
    rect = page.rect
    longest = max(rect.width, rect.height) or 1.0
    zoom = max_px / longest
    return render_page(page, zoom)
