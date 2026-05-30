"""右ペイン: 現在ページの画像一覧と抽出保存。"""
from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from core import images as imglib


class ImagesPanel(QWidget):
    saveSelected = Signal(int)   # xref
    saveAll = Signal()
    imageHighlighted = Signal(int)  # xref（一覧で選択した画像を本文側で強調）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._images: list[dict] = []

        self.info = QLabel("このページの画像")
        self.list = QListWidget()
        self.list.setIconSize(QSize(72, 72))
        self.list.currentRowChanged.connect(self._on_row)

        self.btn_save = QPushButton("選択画像を保存")
        self.btn_save_all = QPushButton("すべて保存")
        self.btn_save.clicked.connect(self._save_selected)
        self.btn_save_all.clicked.connect(lambda: self.saveAll.emit())

        btns = QHBoxLayout()
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_save_all)

        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        layout.addWidget(self.list, 1)
        layout.addLayout(btns)

    def set_document(self, doc) -> None:
        self._doc = doc

    def set_images(self, images: list[dict]) -> None:
        self._images = images
        self.list.blockSignals(True)
        self.list.clear()
        for img in images:
            label = (f"{img['name']}  ({img['width']}x{img['height']}, "
                     f"{img['ext']}, {img['size'] // 1024}KB)")
            item = QListWidgetItem(label)
            item.setData(256, img["xref"])  # Qt.UserRole
            thumb = imglib.extract_thumbnail(self._doc.doc, img["xref"], 72) if self._doc else None
            if thumb:
                qi = QImage.fromData(thumb)
                item.setIcon(QIcon(QPixmap.fromImage(qi)))
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.info.setText(f"このページの画像: {len(images)} 件")

    def select_xref(self, xref: int) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(256) == xref:
                self.list.setCurrentRow(i)
                break

    def _current_xref(self) -> int:
        item = self.list.currentItem()
        return item.data(256) if item else -1

    def _on_row(self, _row: int):
        xref = self._current_xref()
        if xref >= 0:
            self.imageHighlighted.emit(xref)

    def _save_selected(self):
        xref = self._current_xref()
        if xref >= 0:
            self.saveSelected.emit(xref)
