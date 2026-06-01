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
    applyRequested = Signal(dict)        # 単一スパンの編集内容を main_window へ通知
    applyColorRequested = Signal(tuple)  # 複数選択時の文字色一括変更 (r,g,b) 0..1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fonts = fontlib.list_fonts()
        self._color = QColor(0, 0, 0)
        self._fill = QColor(255, 255, 255)
        self._span = None
        self._multi = False
        # ユーザーが色を明示指定したら、以降は選択スパンの色で上書きせず保持する
        self._color_user_set = False
        self._fill_user_set = False

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
        self.bg_box = bg_box

        note = QLabel("※ 再描画方式のため、長文化すると折り返しや位置が"
                      "ずれる場合があります。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #e07b00;")  # 明暗どちらのテーマでも読める橙

        # --- 単一編集 UI（複数選択時はまとめて隠す） ---
        self.single_box = QWidget()
        single_layout = QVBoxLayout(self.single_box)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.addLayout(form)
        single_layout.addWidget(bg_box)
        single_layout.addWidget(note)
        single_layout.addWidget(self.btn_apply)

        # --- 複数選択（文字色のみ一括変更） ---
        self.multi_box = QGroupBox("複数選択")
        multi_layout = QVBoxLayout(self.multi_box)
        self.lbl_multi = QLabel("")
        self.lbl_multi.setWordWrap(True)
        self.btn_multi_color = QPushButton("文字色を選択")
        self.btn_multi_color.clicked.connect(self._pick_color)
        self.btn_multi_apply = QPushButton("文字色を適用")
        self.btn_multi_apply.clicked.connect(self._emit_apply_color)
        multi_layout.addWidget(self.lbl_multi)
        multi_layout.addWidget(self.btn_multi_color)
        multi_layout.addWidget(self.btn_multi_apply)
        self.multi_box.setVisible(False)

        hint = QLabel("※ Ctrl+クリックで複数のテキストを選択できます。")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-style: italic;")  # 色はテーマに追従（パレット既定）

        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        layout.addWidget(hint)
        layout.addWidget(self.single_box)
        layout.addWidget(self.multi_box)
        layout.addStretch(1)
        self._update_color_buttons()

    # ---- 選択反映 ------------------------------------------------------
    def set_selection(self, spans: list[dict]) -> None:
        """選択スパン一覧を反映する。0/1 件は単一編集 UI、2 件以上は色一括 UI。"""
        if not spans:
            self._multi = False
            self.multi_box.setVisible(False)
            self._set_single_enabled(True)
            self.set_span(None)
            return
        if len(spans) == 1:
            self._multi = False
            self.multi_box.setVisible(False)
            self._set_single_enabled(True)
            self.set_span(spans[0])
            return
        # 複数選択: 文字色のみ一括変更
        self._multi = True
        self._span = None
        self._set_single_enabled(False)
        self.multi_box.setVisible(True)
        self.info.setText(f"{len(spans)} 個のテキストを選択中")
        self.lbl_multi.setText(
            f"{len(spans)} 個のテキストの文字色をまとめて変更します。"
            "（フォント・サイズ・文字内容は変更しません）")
        # 文字色の初期値: ユーザー指定済みなら保持、未指定なら先頭スパンの色
        if not self._color_user_set:
            r, g, b = int_to_rgb01(spans[0].get("color", 0))
            self._color = QColor(round(r * 255), round(g * 255), round(b * 255))
        self._update_color_buttons()

    def _set_single_enabled(self, enabled: bool) -> None:
        """単一編集 UI の表示/非表示を切り替える（複数選択時は隠す）。"""
        self.single_box.setVisible(enabled)

    def set_span(self, span: dict | None) -> None:
        self._span = span
        if span is None:
            if not self._multi:
                self.info.setText("テキストを選択してください")
            self.btn_apply.setEnabled(False)
            return
        self.btn_apply.setEnabled(True)
        self.info.setText(f"元フォント: {span.get('font', '?')} / "
                          f"サイズ {span.get('size', 0):.1f}pt")
        self.edit_text.setText(span.get("text", ""))
        self.spin_size.setValue(float(span.get("size", 11.0)))
        # ユーザーが文字色を指定済みならその色を保持し、未指定ならスパンの色を採用
        if not self._color_user_set:
            r, g, b = int_to_rgb01(span.get("color", 0))
            self._color = QColor(round(r * 255), round(g * 255), round(b * 255))
        self._update_color_buttons()

    def clear(self) -> None:
        self.set_selection([])

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
            self._color_user_set = True
            self._update_color_buttons()

    def _pick_fill(self):
        c = QColorDialog.getColor(self._fill, self, "塗りつぶし色")
        if c.isValid():
            self._fill = c
            self._fill_user_set = True
            self.chk_autobg.setChecked(False)
            self._update_color_buttons()

    # ---- 色設定の保存/復元（QSettings 連携） ----------------------------
    def current_prefs(self) -> dict:
        """保持すべき色設定を返す（main_window が QSettings に保存）。"""
        return {
            "color": self._color.name() if self._color_user_set else "",
            "fill": self._fill.name() if self._fill_user_set else "",
            "auto_bg": self.chk_autobg.isChecked(),
        }

    def restore_prefs(self, color_name: str, fill_name: str, auto_bg: bool) -> None:
        """前回ユーザー指定した色を復元する（指定があれば user_set 扱い）。"""
        if color_name:
            c = QColor(color_name)
            if c.isValid():
                self._color = c
                self._color_user_set = True
        if fill_name:
            c = QColor(fill_name)
            if c.isValid():
                self._fill = c
                self._fill_user_set = True
        self.chk_autobg.setChecked(bool(auto_bg))
        self._update_color_buttons()

    def _update_color_buttons(self):
        text_style = (f"background-color: {self._color.name()}; "
                      f"color: {'#fff' if self._color.lightness() < 128 else '#000'};")
        self.btn_color.setStyleSheet(text_style)
        self.btn_multi_color.setStyleSheet(text_style)
        self.btn_fill.setStyleSheet(f"background-color: {self._fill.name()};")

    def _emit_apply_color(self):
        if not self._multi:
            return
        self.applyColorRequested.emit(
            (self._color.redF(), self._color.greenF(), self._color.blueF()))

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
