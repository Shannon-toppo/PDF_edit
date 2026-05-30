"""小さな入力ダイアログ群。"""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QSpinBox)


class ExportPngDialog(QDialog):
    """PNG 書き出しの範囲と DPI を選ぶ。"""

    def __init__(self, page_count: int, current_index: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PNG 書き出し")

        self.combo_range = QComboBox()
        self.combo_range.addItems(["現在のページ", "全ページ"])
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(36, 600)
        self.spin_dpi.setValue(150)
        self.spin_dpi.setSingleStep(6)

        form = QFormLayout(self)
        form.addRow("範囲", self.combo_range)
        form.addRow("解像度 (DPI)", self.spin_dpi)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._page_count = page_count
        self._current = current_index

    def result_indices(self) -> list[int]:
        if self.combo_range.currentIndex() == 0:
            return [self._current]
        return list(range(self._page_count))

    def dpi(self) -> int:
        return self.spin_dpi.value()


class SplitDialog(QDialog):
    """分離するページ範囲（1 始まり）を選ぶ。"""

    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ページの分離（範囲を抽出）")

        self.spin_from = QSpinBox()
        self.spin_from.setRange(1, page_count)
        self.spin_to = QSpinBox()
        self.spin_to.setRange(1, page_count)
        self.spin_to.setValue(page_count)

        form = QFormLayout(self)
        form.addRow("開始ページ", self.spin_from)
        form.addRow("終了ページ", self.spin_to)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def range_zero_based(self) -> tuple[int, int]:
        a = self.spin_from.value() - 1
        b = self.spin_to.value() - 1
        return (min(a, b), max(a, b))
