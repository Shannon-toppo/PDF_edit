"""右ペイン: 選択スパンのフォント・色・サイズ・文字内容の編集 UI。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from ..font_cache import resolve_families

# Qt::ItemDataRole の独自割り当て
_PATH_ROLE = Qt.UserRole          # 埋め込み用フォントファイルのパス
_FAMILY_ROLE = Qt.UserRole + 1    # 解決済みファミリ名（プレビュー用）
_PREVIEW_PT = 12

from core import fonts as fontlib
from core.text_edit import int_to_rgb01


class TextPanel(QWidget):
    applyRequested = Signal(dict)   # 編集内容を main_window へ通知

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fonts = fontlib.list_fonts()
        self._color = QColor(0, 0, 0)
        self._fill = QColor(255, 255, 255)
        self._span = None

        self.info = QLabel("テキストを選択してください")
        self.info.setWordWrap(True)

        self.edit_text = QLineEdit()

        self.combo_font = QComboBox()
        self._build_font_combo()

        self.spin_size = QDoubleSpinBox()
        self.spin_size.setRange(1.0, 400.0)
        self.spin_size.setDecimals(1)
        self.spin_size.setValue(11.0)

        self.btn_color = QPushButton("文字色を選択")
        self.btn_color.clicked.connect(self._pick_color)

        self.chk_overlay = QCheckBox("上書きモード（元文字を消さず重ねる）")
        self.chk_autobg = QCheckBox("背景色を自動推定して塗りつぶす")
        self.chk_autobg.setChecked(True)
        self.btn_fill = QPushButton("塗りつぶし色を選択")
        self.btn_fill.clicked.connect(self._pick_fill)

        self.btn_apply = QPushButton("適用")
        self.btn_apply.clicked.connect(self._emit_apply)
        self.btn_apply.setEnabled(False)

        form = QFormLayout()
        form.addRow("文字内容", self.edit_text)
        form.addRow("フォント", self.combo_font)
        form.addRow("サイズ(pt)", self.spin_size)
        form.addRow(self.btn_color)

        bg_box = QGroupBox("背景の扱い")
        bg_layout = QVBoxLayout(bg_box)
        bg_layout.addWidget(self.chk_overlay)
        bg_layout.addWidget(self.chk_autobg)
        bg_layout.addWidget(self.btn_fill)

        note = QLabel("※ 再描画方式のため、長文化すると折り返しや位置が"
                      "ずれる場合があります。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #a06000;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        layout.addLayout(form)
        layout.addWidget(bg_box)
        layout.addWidget(note)
        layout.addWidget(self.btn_apply)
        layout.addStretch(1)
        self._update_color_buttons()

    # ---- 選択反映 ------------------------------------------------------
    def set_span(self, span: dict | None) -> None:
        self._span = span
        if span is None:
            self.info.setText("テキストを選択してください")
            self.btn_apply.setEnabled(False)
            return
        self.btn_apply.setEnabled(True)
        self.info.setText(f"元フォント: {span.get('font', '?')} / "
                          f"サイズ {span.get('size', 0):.1f}pt")
        self.edit_text.setText(span.get("text", ""))
        self.spin_size.setValue(float(span.get("size", 11.0)))
        r, g, b = int_to_rgb01(span.get("color", 0))
        self._color = QColor(round(r * 255), round(g * 255), round(b * 255))
        self._update_color_buttons()

    def clear(self) -> None:
        self.set_span(None)

    # ---- フォントプレビュー --------------------------------------------
    def _build_font_combo(self) -> None:
        """フォント名をそのフォント自身で描画する。ファミリ名解決はキャッシュ利用。"""
        families = resolve_families(self._fonts)  # label -> family（ディスクキャッシュ）
        seen: dict[str, int] = {}
        for label, path in self._fonts.items():
            family = families.get(label, label)
            # 同名ファミリ（太さ違いファイル等）はファイル名を併記して区別
            seen[family] = seen.get(family, 0) + 1
            display = family if seen[family] == 1 else f"{family}（{label}）"
            idx = self.combo_font.count()
            self.combo_font.addItem(display)
            self.combo_font.setItemData(idx, path, _PATH_ROLE)
            self.combo_font.setItemData(idx, family, _FAMILY_ROLE)
            # 一覧の各項目をそのフォントで描画（プレビュー）
            self.combo_font.setItemData(idx, QFont(family, _PREVIEW_PT), Qt.FontRole)
        self.combo_font.currentIndexChanged.connect(self._on_font_changed)

        default = fontlib.default_font(self._fonts)
        if default:
            i = self.combo_font.findData(self._fonts[default], _PATH_ROLE)
            if i >= 0:
                self.combo_font.setCurrentIndex(i)
        self._on_font_changed(self.combo_font.currentIndex())

    def _on_font_changed(self, idx: int) -> None:
        # 閉じた状態の表示も選択フォントでプレビューする
        family = self.combo_font.itemData(idx, _FAMILY_ROLE)
        if family:
            self.combo_font.setFont(QFont(family, 11))

    # ---- 内部 ----------------------------------------------------------
    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "文字色")
        if c.isValid():
            self._color = c
            self._update_color_buttons()

    def _pick_fill(self):
        c = QColorDialog.getColor(self._fill, self, "塗りつぶし色")
        if c.isValid():
            self._fill = c
            self.chk_autobg.setChecked(False)
            self._update_color_buttons()

    def _update_color_buttons(self):
        self.btn_color.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"color: {'#fff' if self._color.lightness() < 128 else '#000'};")
        self.btn_fill.setStyleSheet(f"background-color: {self._fill.name()};")

    def _emit_apply(self):
        if self._span is None:
            return
        payload = {
            "span": self._span,
            "text": self.edit_text.text(),
            "fontfile": self.combo_font.currentData(_PATH_ROLE),
            "fontsize": self.spin_size.value(),
            "color": (self._color.redF(), self._color.greenF(), self._color.blueF()),
            "fill": (self._fill.redF(), self._fill.greenF(), self._fill.blueF()),
            "overlay": self.chk_overlay.isChecked(),
            "auto_bg": self.chk_autobg.isChecked(),
        }
        self.applyRequested.emit(payload)
