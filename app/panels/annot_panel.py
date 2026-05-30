"""右ペイン: 注釈の種別・色・テキストを選ぶ。ページ上のドラッグで適用される。"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QComboBox, QDoubleSpinBox,
                               QFormLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from core import annots

# 種別ごとの既定色
_DEFAULT_COLORS = {
    annots.HIGHLIGHT: QColor(255, 235, 0),
    annots.UNDERLINE: QColor(0, 90, 220),
    annots.STRIKEOUT: QColor(220, 30, 30),
    annots.RECT: QColor(220, 30, 30),
    annots.FREETEXT: QColor(0, 0, 0),
    annots.NOTE: QColor(255, 200, 0),
}


class AnnotPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(255, 235, 0)

        self.combo_kind = QComboBox()
        for key in (annots.HIGHLIGHT, annots.UNDERLINE, annots.STRIKEOUT,
                    annots.RECT, annots.FREETEXT, annots.NOTE):
            self.combo_kind.addItem(annots.LABELS[key], key)
        self.combo_kind.currentIndexChanged.connect(self._on_kind_changed)

        self.btn_color = QPushButton("色を選択")
        self.btn_color.clicked.connect(self._pick_color)

        self.edit_text = QLineEdit()
        self.edit_text.setPlaceholderText("フリーテキスト / 付箋の本文")
        self.spin_size = QDoubleSpinBox()
        self.spin_size.setRange(4.0, 200.0)
        self.spin_size.setValue(12.0)

        form = QFormLayout()
        form.addRow("種別", self.combo_kind)
        form.addRow(self.btn_color)
        form.addRow("本文", self.edit_text)
        form.addRow("文字サイズ", self.spin_size)

        note = QLabel("ページ上をドラッグして範囲を指定すると注釈を追加します。\n"
                      "付箋はドラッグ範囲の左上に配置されます。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #6a6a6a;")

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        self._update_color_button()

    def _on_kind_changed(self):
        self._color = QColor(_DEFAULT_COLORS.get(self.current_kind(),
                                                 QColor(255, 235, 0)))
        self._update_color_button()

    def current_kind(self) -> str:
        return self.combo_kind.currentData()

    def options(self) -> dict:
        return {
            "kind": self.current_kind(),
            "color": (self._color.redF(), self._color.greenF(), self._color.blueF()),
            "text": self.edit_text.text(),
            "fontsize": self.spin_size.value(),
        }

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "注釈の色")
        if c.isValid():
            self._color = c
            self._update_color_button()

    def _update_color_button(self):
        self.btn_color.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"color: {'#fff' if self._color.lightness() < 128 else '#000'};")
