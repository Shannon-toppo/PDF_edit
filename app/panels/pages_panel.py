"""左ペイン: ページのサムネイル一覧と並べ替え/削除操作。"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

from core.render import render_thumbnail


class PagesPanel(QWidget):
    pageActivated = Signal(int)            # サムネイルを選択して表示要求
    moveRequested = Signal(int, int)       # (src, dst)
    deleteRequested = Signal(int)          # 削除要求

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(120, 160))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(6)
        self.list.currentRowChanged.connect(self._on_row_changed)

        self.btn_up = QPushButton("↑ 上へ")
        self.btn_down = QPushButton("↓ 下へ")
        self.btn_del = QPushButton("🗑 削除")
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)
        self.btn_del.clicked.connect(self._delete)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.btn_up)
        layout.addWidget(self.btn_down)
        layout.addWidget(self.btn_del)

    def set_document(self, doc) -> None:
        self._doc = doc
        self.refresh()

    def current_index(self) -> int:
        return self.list.currentRow()

    def set_current_index(self, idx: int) -> None:
        if 0 <= idx < self.list.count():
            self.list.setCurrentRow(idx)

    def refresh(self, keep_row: int | None = None) -> None:
        row = keep_row if keep_row is not None else self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        if self._doc and self._doc.is_open:
            for i in range(self._doc.page_count):
                img: QImage = render_thumbnail(self._doc.page(i), 150)
                icon = QIcon(QPixmap.fromImage(img))
                item = QListWidgetItem(icon, f"{i + 1}")
                item.setTextAlignment(Qt.AlignHCenter)
                self.list.addItem(item)
        self.list.blockSignals(False)
        if self.list.count():
            row = max(0, min(row, self.list.count() - 1))
            self.list.setCurrentRow(row)

    def refresh_one(self, idx: int) -> None:
        """指定 1 ページのサムネイルだけを再生成する（回転など単一変更用）。"""
        if not (self._doc and self._doc.is_open):
            return
        if 0 <= idx < self.list.count():
            img: QImage = render_thumbnail(self._doc.page(idx), 150)
            self.list.item(idx).setIcon(QIcon(QPixmap.fromImage(img)))

    # ---- ボタン操作 ----------------------------------------------------
    def _on_row_changed(self, row: int):
        if row >= 0:
            self.pageActivated.emit(row)

    def _move_up(self):
        row = self.list.currentRow()
        if row > 0:
            self.moveRequested.emit(row, row - 1)

    def _move_down(self):
        row = self.list.currentRow()
        if 0 <= row < self.list.count() - 1:
            self.moveRequested.emit(row, row + 1)

    def _delete(self):
        row = self.list.currentRow()
        if row >= 0:
            self.deleteRequested.emit(row)
