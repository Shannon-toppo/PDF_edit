"""メインウィンドウ: 3 ペイン構成と全機能の結線。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, QSettings, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QSplitter, QStackedWidget, QToolBar, QWidget)

from core import annots, fonts as fontlib, images as imglib
from core import page_ops, search, text_edit
from core.document import PdfDocument
from core.render import render_page

from . import __version__, theme
from .dialogs import ExportPngDialog, SplitDialog
from .page_view import (MODE_ANNOT, MODE_IMAGE, MODE_PAN, MODE_TEXT, PageView,
                        first_pdf_url)
from .panels.annot_panel import AnnotPanel
from .panels.images_panel import ImagesPanel
from .panels.pages_panel import PagesPanel
from .panels.text_panel import TextPanel

ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]


class _SearchLineEdit(QLineEdit):
    """Enter で「次へ」、Shift+Enter で「前へ」を発火する検索入力欄。"""
    searchNext = Signal()
    searchPrev = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                self.searchPrev.emit()
            else:
                self.searchNext.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PDFedit v{__version__}")
        self.resize(1280, 860)
        self.setAcceptDrops(True)

        self.settings = QSettings()
        self.doc = PdfDocument()
        self.current_index = 0
        self._zoom_idx = 2  # 1.0
        self._export_dpi = int(self.settings.value("export/dpi", 150))
        self._search_results: list[tuple[int, object]] = []
        self._search_idx = -1
        self._search_query = ""
        self._sel_spans: list[int] = []        # 選択中スパンのインデックス
        self._fonts_map: dict[str, str] | None = None
        self._family_to_path: dict[str, str] | None = None

        # --- 中央ビュー ---
        self.view = PageView()
        self.view.spanSelected.connect(self._on_span_selected)
        self.view.spanToggled.connect(self._on_span_toggled)
        self.view.imageSelected.connect(self._on_image_clicked)
        self.view.nextPageRequested.connect(self._scroll_to_next_page)
        self.view.prevPageRequested.connect(self._scroll_to_prev_page)
        self.view.annotRectDrawn.connect(self._apply_annotation)
        self.view.pdfDropped.connect(self._open_path)

        # --- 左 ---
        self.pages = PagesPanel()
        self.pages.set_document(self.doc)
        self.pages.pageActivated.connect(self._goto_page)
        self.pages.moveRequested.connect(self._move_page)
        self.pages.deleteRequested.connect(self._delete_page)

        # --- 右 ---
        self.text_panel = TextPanel()
        self.text_panel.applyRequested.connect(self._apply_text_edit)
        self.text_panel.applyColorRequested.connect(self._apply_color_multi)
        self.images_panel = ImagesPanel()
        self.images_panel.set_document(self.doc)
        self.images_panel.saveSelected.connect(self._save_one_image)
        self.images_panel.saveAll.connect(self._save_all_images)
        self.images_panel.imageHighlighted.connect(self._highlight_image)
        self.annot_panel = AnnotPanel()
        self.right = QStackedWidget()
        self.right.addWidget(self.text_panel)     # index 0
        self.right.addWidget(self.images_panel)   # index 1
        self.right.addWidget(self.annot_panel)    # index 2
        self.right.setMinimumWidth(180)
        self.right.setMaximumWidth(280)

        self.splitter = QSplitter(Qt.Horizontal)
        left_holder = QWidget()
        lh = QHBoxLayout(left_holder)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.addWidget(self.pages)
        self.splitter.addWidget(left_holder)
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(self.right)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([190, 850, 240])
        self.setCentralWidget(self.splitter)

        self._spans: list[dict] = []
        self._page_images: list[dict] = []
        self._build_actions()
        self._build_toolbar()
        self._build_search_toolbar()
        self._build_menubar()
        self.statusBar().showMessage("ファイルを開いてください")
        self._update_actions()
        self._restore_settings()

    # ================= アクション / ツールバー =================
    def _build_actions(self):
        self.act_open = QAction("開く", self, shortcut=QKeySequence.Open)
        self.act_open.triggered.connect(self.open_file)
        self.act_save = QAction("保存", self, shortcut=QKeySequence.Save)
        self.act_save.triggered.connect(self.save_file)
        self.act_saveas = QAction("名前を付けて保存", self,
                                  shortcut=QKeySequence.SaveAs)
        self.act_saveas.triggered.connect(self.save_file_as)
        self.act_merge = QAction("結合用に追加", self)
        self.act_merge.triggered.connect(self.merge_file)
        self.act_split = QAction("分離（範囲抽出）", self)
        self.act_split.triggered.connect(self.split_file)
        self.act_png = QAction("PNG書き出し", self)
        self.act_png.triggered.connect(self.export_png)

        self.act_undo = QAction("元に戻す", self, shortcut=QKeySequence.Undo)
        self.act_undo.triggered.connect(self.undo)
        self.act_redo = QAction("やり直し", self, shortcut=QKeySequence.Redo)
        self.act_redo.triggered.connect(self.redo)

        self.act_zoom_in = QAction("拡大", self, shortcut=QKeySequence.ZoomIn)
        self.act_zoom_in.triggered.connect(lambda: self._zoom(+1))
        self.act_zoom_out = QAction("縮小", self, shortcut=QKeySequence.ZoomOut)
        self.act_zoom_out.triggered.connect(lambda: self._zoom(-1))

        # ページ編集
        self.act_rot_cw = QAction("右に90°回転", self)
        self.act_rot_cw.triggered.connect(lambda: self._rotate(90))
        self.act_rot_ccw = QAction("左に90°回転", self)
        self.act_rot_ccw.triggered.connect(lambda: self._rotate(-90))
        self.act_dup = QAction("ページを複製", self)
        self.act_dup.triggered.connect(self._duplicate_page)
        self.act_blank = QAction("空白ページを挿入", self)
        self.act_blank.triggered.connect(self._insert_blank)
        self.act_del = QAction("ページを削除", self)
        self.act_del.triggered.connect(lambda: self._delete_page(self.current_index))

        # テーマ
        self.act_theme = QAction("ダークテーマ", self, checkable=True)
        self.act_theme.triggered.connect(self._toggle_theme)

        # 選択モード
        self.act_mode_text = QAction("文字選択", self, checkable=True)
        self.act_mode_image = QAction("画像選択", self, checkable=True)
        self.act_mode_annot = QAction("注釈", self, checkable=True)
        self.act_mode_pan = QAction("移動", self, checkable=True)
        self.act_mode_text.setChecked(True)
        grp = QActionGroup(self)
        for a in (self.act_mode_text, self.act_mode_image, self.act_mode_annot,
                  self.act_mode_pan):
            grp.addAction(a)
        self.act_mode_text.triggered.connect(lambda: self._set_mode(MODE_TEXT))
        self.act_mode_image.triggered.connect(lambda: self._set_mode(MODE_IMAGE))
        self.act_mode_annot.triggered.connect(lambda: self._set_mode(MODE_ANNOT))
        self.act_mode_pan.triggered.connect(lambda: self._set_mode(MODE_PAN))

    def _build_toolbar(self):
        tb = QToolBar("メイン")
        tb.setMovable(False)
        self.addToolBar(tb)
        for a in (self.act_open, self.act_save, self.act_saveas):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_merge)
        tb.addAction(self.act_split)
        tb.addAction(self.act_png)
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        tb.addAction(self.act_mode_text)
        tb.addAction(self.act_mode_image)
        tb.addAction(self.act_mode_annot)
        tb.addAction(self.act_mode_pan)
        tb.addSeparator()
        tb.addAction(self.act_zoom_out)
        tb.addAction(self.act_zoom_in)

    def _build_search_toolbar(self):
        tb = QToolBar("検索")
        tb.setMovable(False)
        self.addToolBarBreak()
        self.addToolBar(tb)
        tb.addWidget(QLabel(" 検索: "))
        self.search_edit = _SearchLineEdit()
        self.search_edit.setPlaceholderText("文書全体を検索（Enter:次へ / Shift+Enter:前へ）")
        self.search_edit.setMaximumWidth(280)
        self.search_edit.searchNext.connect(self._search_next)
        self.search_edit.searchPrev.connect(self._search_prev)
        tb.addWidget(self.search_edit)
        self.btn_search_prev = QPushButton("前へ")
        self.btn_search_next = QPushButton("次へ")
        self.btn_search_prev.clicked.connect(self._search_prev)
        self.btn_search_next.clicked.connect(self._search_next)
        tb.addWidget(self.btn_search_prev)
        tb.addWidget(self.btn_search_next)
        self.search_label = QLabel("  0 件")
        tb.addWidget(self.search_label)

    def _build_menubar(self):
        mb = self.menuBar()
        m_file = mb.addMenu("ファイル")
        for a in (self.act_open, self.act_save, self.act_saveas):
            m_file.addAction(a)
        m_file.addSeparator()
        m_file.addAction(self.act_merge)
        m_file.addAction(self.act_split)
        m_file.addAction(self.act_png)

        m_edit = mb.addMenu("編集")
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)

        m_page = mb.addMenu("ページ")
        for a in (self.act_rot_cw, self.act_rot_ccw, self.act_dup,
                  self.act_blank, self.act_del):
            m_page.addAction(a)

        m_view = mb.addMenu("表示")
        m_view.addAction(self.act_zoom_in)
        m_view.addAction(self.act_zoom_out)
        m_view.addSeparator()
        for a in (self.act_mode_text, self.act_mode_image, self.act_mode_annot,
                  self.act_mode_pan):
            m_view.addAction(a)
        m_view.addSeparator()
        m_view.addAction(self.act_theme)

        m_help = mb.addMenu("ヘルプ")
        act_about = QAction("バージョン情報", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

    def _show_about(self):
        """バージョン情報ダイアログ（アプリ版・ライセンス・依存ライブラリ版）。"""
        try:
            import fitz
            mupdf_ver = fitz.version[0]
        except Exception:
            mupdf_ver = "?"
        try:
            from PySide6 import __version__ as pyside_ver
        except Exception:
            pyside_ver = "?"
        repo_url = "https://github.com/Shannon-toppo/PDF_edit"
        QMessageBox.about(
            self,
            "PDFedit について",
            f"<h3>PDFedit v{__version__}</h3>"
            "<p>軽量な GUI PDF エディター（PyMuPDF + PySide6）</p>"
            f"<p>PyMuPDF {mupdf_ver} / PySide6 {pyside_ver}</p>"
            "<p>ライセンス: <b>AGPL-3.0-or-later</b><br>"
            "本ソフトは PyMuPDF（AGPL-3.0）を利用しており、全体が AGPL-3.0 で頒布されます。<br>"
            f"対応ソース: <a href=\"{repo_url}\">{repo_url}</a></p>",
        )

    # ================= ファイル操作 =================
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF を開く", "",
                                              "PDF ファイル (*.pdf)")
        if path:
            self._open_path(path)

    def _open_path(self, path: str) -> bool:
        """指定パスの PDF を開く（ダイアログ / D&D / CLI 引数で共用）。"""
        try:
            self.doc.open(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"開けませんでした:\n{e}")
            return False
        self.current_index = 0
        self.pages.set_document(self.doc)
        self.images_panel.set_document(self.doc)
        self._refresh_all()
        self.setWindowTitle(f"PDFedit v{__version__} - {os.path.basename(path)}")
        return True

    # ---- ドラッグ＆ドロップ（ウィンドウ全体） -------------------------
    def dragEnterEvent(self, event):
        if first_pdf_url(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if first_pdf_url(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = first_pdf_url(event.mimeData())
        if path:
            event.acceptProposedAction()
            self._open_path(path)
        else:
            event.ignore()

    def save_file(self):
        if not self._require_doc():
            return
        if self.doc.path is None:
            self.save_file_as()
            return
        try:
            self.doc.save()
            self.statusBar().showMessage(f"保存しました: {self.doc.path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")

    def save_file_as(self):
        if not self._require_doc():
            return
        path, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", "",
                                              "PDF ファイル (*.pdf)")
        if not path:
            return
        try:
            self.doc.save(path)
            self.setWindowTitle(f"軽量PDFエディター - {os.path.basename(path)}")
            self.statusBar().showMessage(f"保存しました: {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")

    def merge_file(self):
        if not self._require_doc():
            return
        path, _ = QFileDialog.getOpenFileName(self, "結合する PDF を選択", "",
                                              "PDF ファイル (*.pdf)")
        if not path:
            return
        try:
            self.doc.snapshot()
            added = page_ops.merge_pdf(self.doc.doc, path)
            self._refresh_all()
            self.statusBar().showMessage(f"{added} ページを結合しました", 4000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"結合に失敗しました:\n{e}")

    def split_file(self):
        if not self._require_doc():
            return
        dlg = SplitDialog(self.doc.page_count, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        a, b = dlg.range_zero_based()
        path, _ = QFileDialog.getSaveFileName(self, "抽出先 PDF", "",
                                              "PDF ファイル (*.pdf)")
        if not path:
            return
        try:
            page_ops.split_pages(self.doc.doc, a, b, path)
            self.statusBar().showMessage(
                f"{a + 1}〜{b + 1} ページを {os.path.basename(path)} に保存しました", 5000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"分離に失敗しました:\n{e}")

    def export_png(self):
        if not self._require_doc():
            return
        dlg = ExportPngDialog(self.doc.page_count, self.current_index,
                              self._export_dpi, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "PNG の保存先フォルダ")
        if not out_dir:
            return
        self._export_dpi = dlg.dpi()
        try:
            paths = page_ops.export_png(self.doc.doc, dlg.result_indices(),
                                        out_dir, dlg.dpi())
            self.statusBar().showMessage(
                f"{len(paths)} 枚の PNG を書き出しました", 5000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"書き出しに失敗しました:\n{e}")

    # ================= ページ操作 =================
    def _goto_page(self, idx: int):
        if 0 <= idx < self.doc.page_count:
            self.current_index = idx
            self._refresh_page()

    def _scroll_to_next_page(self):
        if self.doc.is_open and self.current_index < self.doc.page_count - 1:
            # サムネイル選択を更新すると pageActivated 経由で再描画される
            self.pages.set_current_index(self.current_index + 1)
            self.view.scroll_to_top()

    def _scroll_to_prev_page(self):
        if self.doc.is_open and self.current_index > 0:
            self.pages.set_current_index(self.current_index - 1)
            # 再描画でスクロール範囲が確定した後に末尾へ移動する
            QTimer.singleShot(0, self.view.scroll_to_bottom)

    def _move_page(self, src: int, dst: int):
        self.doc.snapshot()
        page_ops.move_page(self.doc.doc, src, dst)
        self.current_index = dst
        self.pages.refresh(keep_row=dst)
        self._refresh_page()
        self._update_actions()

    def _delete_page(self, idx: int):
        if self.doc.page_count <= 1:
            QMessageBox.information(self, "情報", "最後の 1 ページは削除できません")
            return
        self.doc.snapshot()
        page_ops.delete_page(self.doc.doc, idx)
        self.current_index = min(idx, self.doc.page_count - 1)
        self.pages.refresh(keep_row=self.current_index)
        self._refresh_page()
        self._update_actions()

    def _rotate(self, delta: int):
        if not self._require_doc():
            return
        self.doc.snapshot()
        page_ops.rotate_page(self.doc.doc, self.current_index, delta)
        self.pages.refresh(keep_row=self.current_index)
        self._refresh_page()
        self._update_actions()

    def _duplicate_page(self):
        if not self._require_doc():
            return
        self.doc.snapshot()
        page_ops.duplicate_page(self.doc.doc, self.current_index)
        self.current_index += 1
        self.pages.refresh(keep_row=self.current_index)
        self._refresh_page()
        self._update_actions()
        self.statusBar().showMessage("ページを複製しました", 4000)

    def _insert_blank(self):
        if not self._require_doc():
            return
        self.doc.snapshot()
        page_ops.insert_blank(self.doc.doc, self.current_index)
        self.current_index += 1
        self.pages.refresh(keep_row=self.current_index)
        self._refresh_page()
        self._update_actions()
        self.statusBar().showMessage("空白ページを挿入しました", 4000)

    # ================= 注釈 =================
    def _apply_annotation(self, x0: float, y0: float, x1: float, y1: float):
        if not self._require_doc():
            return
        opts = self.annot_panel.options()
        try:
            self.doc.snapshot()
            page = self.doc.page(self.current_index)
            annots.add_annotation(page, opts["kind"], (x0, y0, x1, y1),
                                  color=opts["color"], text=opts["text"],
                                  fontsize=opts["fontsize"])
            self._refresh_page()
            self.pages.refresh(keep_row=self.current_index)
            self.statusBar().showMessage(
                f"{annots.LABELS[opts['kind']]}を追加しました", 4000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"注釈の追加に失敗しました:\n{e}")
        self._update_actions()

    # ================= 検索 =================
    def _run_search(self, query: str):
        self._search_query = query
        self._search_results = search.search_document(self.doc.doc, query) \
            if self.doc.is_open else []
        self._search_idx = -1
        self.search_label.setText(f"  {len(self._search_results)} 件")

    def _search_step(self, step: int):
        if not self.doc.is_open:
            return
        query = self.search_edit.text().strip()
        if query != self._search_query or not self._search_results:
            self._run_search(query)
        if not self._search_results:
            self.search_label.setText("  0 件")
            self.view.clear_search_highlights()
            return
        self._search_idx = (self._search_idx + step) % len(self._search_results)
        page_idx, rect = self._search_results[self._search_idx]
        if page_idx != self.current_index:
            self.current_index = page_idx
            self.pages.set_current_index(page_idx)
        else:
            self._highlight_search_on_page()
        QTimer.singleShot(0, lambda: self.view.scroll_to_rect(
            (rect.x0, rect.y0, rect.x1, rect.y1)))
        self.search_label.setText(
            f"  {self._search_idx + 1} / {len(self._search_results)} 件")

    def _search_next(self):
        self._search_step(+1)

    def _search_prev(self):
        self._search_step(-1)

    def _highlight_search_on_page(self):
        rects = [r for (p, r) in self._search_results if p == self.current_index]
        current = None
        if 0 <= self._search_idx < len(self._search_results):
            p, r = self._search_results[self._search_idx]
            if p == self.current_index:
                current = r
        self.view.set_search_highlights(rects, current)

    # ================= 文字編集 =================
    def _on_span_selected(self, span_idx: int):
        """通常クリック: 単一選択（既存の選択は置き換え）。"""
        if 0 <= span_idx < len(self._spans):
            self._sel_spans = [span_idx]
            self._sync_selection_ui()
            self.right.setCurrentIndex(0)

    def _on_span_toggled(self, span_idx: int):
        """Ctrl+クリック: 選択へ追加/除去（複数選択）。"""
        if not (0 <= span_idx < len(self._spans)):
            return
        if span_idx in self._sel_spans:
            self._sel_spans.remove(span_idx)
        else:
            self._sel_spans.append(span_idx)
        self._sync_selection_ui()
        self.right.setCurrentIndex(0)

    def _sync_selection_ui(self):
        """選択状態を右ペインとオーバーレイへ反映する。"""
        spans = [self._spans[i] for i in self._sel_spans
                 if 0 <= i < len(self._spans)]
        self.text_panel.set_selection(spans)
        self.view.mark_selections([sp["bbox"] for sp in spans])

    def _apply_text_edit(self, payload: dict):
        if not self._require_doc():
            return
        span = payload["span"]
        page = self.doc.page(self.current_index)
        fill = payload["fill"]
        if payload.get("auto_bg") and not payload["overlay"]:
            fill = text_edit.sample_background(page, span["bbox"])
        try:
            self.doc.snapshot()
            page = self.doc.page(self.current_index)  # snapshot 後に取り直す
            text_edit.apply_text_edit(
                page,
                span_bbox=span["bbox"],
                origin=span.get("origin", (span["bbox"][0], span["bbox"][3])),
                text=payload["text"],
                fontfile=payload["fontfile"],
                fontsize=payload["fontsize"],
                color_rgb01=payload["color"],
                fill_rgb01=fill,
                overlay=payload["overlay"],
            )
            self._refresh_page()
            self.pages.refresh(keep_row=self.current_index)
            self.text_panel.clear()
            self.view.clear_selection_marker()
            self.statusBar().showMessage("テキストを更新しました", 4000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"テキスト編集に失敗しました:\n{e}")
        self._update_actions()

    def _apply_color_multi(self, color_rgb01: tuple):
        """複数選択したスパンの文字色をまとめて変更する。

        各スパンの文字・サイズ・（推定できる範囲で）元フォントは保ったまま、
        色だけを差し替える。1 回のスナップショットで undo できる。
        """
        if not self._require_doc() or not self._sel_spans:
            return
        spans = [self._spans[i] for i in self._sel_spans
                 if 0 <= i < len(self._spans)]
        if not spans:
            return
        try:
            self.doc.snapshot()
            page = self.doc.page(self.current_index)  # snapshot 後に取り直す
            for sp in spans:
                bbox = sp["bbox"]
                fill = text_edit.sample_background(page, bbox)
                text_edit.apply_text_edit(
                    page,
                    span_bbox=bbox,
                    origin=sp.get("origin", (bbox[0], bbox[3])),
                    text=sp.get("text", ""),
                    fontfile=self._resolve_span_fontfile(sp),
                    fontsize=float(sp.get("size", 11.0)),
                    color_rgb01=color_rgb01,
                    fill_rgb01=fill,
                    overlay=False,
                )
            self._refresh_page()
            self.pages.refresh(keep_row=self.current_index)
            self.statusBar().showMessage(
                f"{len(spans)} 個のテキストの文字色を変更しました", 4000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"文字色の変更に失敗しました:\n{e}")
        self._update_actions()

    # ---- 元フォントの推定（複数選択の色変更で見た目を保つため） --------
    @staticmethod
    def _norm_family(name: str) -> str:
        """フォント名を比較用に正規化（subset 接頭辞除去・英数字小文字化）。"""
        if "+" in name:               # 例: "ABCDEF+MSGothic" の subset 接頭辞
            name = name.split("+", 1)[1]
        return "".join(c for c in name.lower() if c.isalnum())

    def _font_index(self) -> dict[str, str]:
        """{正規化ファミリ名: フォントファイルパス} を遅延構築・キャッシュ。"""
        if self._family_to_path is None:
            from .font_cache import resolve_families
            self._fonts_map = fontlib.list_fonts()
            families = resolve_families(self._fonts_map)  # label -> family
            idx: dict[str, str] = {}
            for label, family in families.items():
                idx.setdefault(self._norm_family(family), self._fonts_map[label])
                idx.setdefault(self._norm_family(label), self._fonts_map[label])
            self._family_to_path = idx
        return self._family_to_path

    def _resolve_span_fontfile(self, span: dict) -> str | None:
        """スパンの元フォント名から埋め込み用フォントファイルを推定する。

        見つからなければ既定の日本語フォント、それも無ければ None（helv）。
        """
        idx = self._font_index()
        key = self._norm_family(span.get("font", ""))
        if key and key in idx:
            return idx[key]
        for k, path in idx.items():   # 部分一致フォールバック
            if key and (key in k or k in key):
                return path
        default = fontlib.default_font(self._fonts_map or {})
        return (self._fonts_map or {}).get(default) if default else None

    # ================= 画像 =================
    def _on_image_clicked(self, xref: int):
        self.right.setCurrentIndex(1)
        self.images_panel.select_xref(xref)
        self._highlight_image(xref)

    def _highlight_image(self, xref: int):
        for img in self._page_images:
            if img["xref"] == xref and img["rects"]:
                r = img["rects"][0]
                self.view.mark_selection((r.x0, r.y0, r.x1, r.y1))
                return

    def _save_one_image(self, xref: int):
        path, _ = QFileDialog.getSaveFileName(
            self, "画像を保存", f"image_{xref}",
            "画像 (*.png *.jpg *.jpeg);;すべて (*.*)")
        if not path:
            return
        noext = os.path.splitext(path)[0]
        try:
            saved = imglib.save_image(self.doc.doc, xref, noext)
            self.statusBar().showMessage(f"保存しました: {saved}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"画像保存に失敗しました:\n{e}")

    def _save_all_images(self):
        if not self._page_images:
            QMessageBox.information(self, "情報", "このページに画像はありません")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "画像の保存先フォルダ")
        if not out_dir:
            return
        count = 0
        for img in self._page_images:
            try:
                base = os.path.join(out_dir,
                                    f"p{self.current_index + 1}_x{img['xref']}")
                imglib.save_image(self.doc.doc, img["xref"], base)
                count += 1
            except Exception:
                pass
        self.statusBar().showMessage(f"{count} 枚の画像を保存しました", 5000)

    # ================= Undo / Redo =================
    def undo(self):
        if self.doc.undo():
            self.current_index = min(self.current_index, self.doc.page_count - 1)
            self._refresh_all_after_history()

    def redo(self):
        if self.doc.redo():
            self.current_index = min(self.current_index, self.doc.page_count - 1)
            self._refresh_all_after_history()

    def _refresh_all_after_history(self):
        # undo/redo で doc オブジェクトが差し替わるため参照を貼り直す
        self.pages.set_document(self.doc)
        self.images_panel.set_document(self.doc)
        self._refresh_all()

    # ================= 表示更新 =================
    def _set_mode(self, mode: str):
        self.view.set_mode(mode)
        self.view.clear_selection_marker()
        if mode == MODE_TEXT:
            self.right.setCurrentIndex(0)
        elif mode == MODE_IMAGE:
            self.right.setCurrentIndex(1)
        elif mode == MODE_ANNOT:
            self.right.setCurrentIndex(2)

    def _zoom(self, delta: int):
        self._zoom_idx = max(0, min(len(ZOOM_STEPS) - 1, self._zoom_idx + delta))
        self._refresh_page()

    def _refresh_all(self):
        self.pages.refresh(keep_row=self.current_index)
        self._refresh_page()
        self._update_actions()

    def _refresh_page(self):
        if not self.doc.is_open:
            return
        self.current_index = max(0, min(self.current_index, self.doc.page_count - 1))
        page = self.doc.page(self.current_index)
        zoom = ZOOM_STEPS[self._zoom_idx]
        self.view.set_page_image(render_page(page, zoom), zoom)

        self._spans = text_edit.get_spans(page)
        self._sel_spans = []
        self.view.set_spans(self._spans)
        self._page_images = imglib.list_images(page)
        self.view.set_images(self._page_images)
        self.images_panel.set_images(self._page_images)
        self.text_panel.clear()

        # 検索中なら、このページのヒットを再ハイライト
        if self._search_query and self._search_results:
            self._highlight_search_on_page()

        self.statusBar().showMessage(
            f"ページ {self.current_index + 1} / {self.doc.page_count}  "
            f"(拡大 {int(zoom * 100)}%)")

    def _update_actions(self):
        ok = self.doc.is_open
        for a in (self.act_save, self.act_saveas, self.act_merge, self.act_split,
                  self.act_png, self.act_zoom_in, self.act_zoom_out,
                  self.act_mode_text, self.act_mode_image, self.act_mode_annot,
                  self.act_mode_pan, self.act_rot_cw, self.act_rot_ccw,
                  self.act_dup, self.act_blank, self.act_del):
            a.setEnabled(ok)
        self.act_undo.setEnabled(ok and self.doc.can_undo())
        self.act_redo.setEnabled(ok and self.doc.can_redo())

    # ================= テーマ / 設定 =================
    def _toggle_theme(self, checked: bool):
        theme.apply_theme(QApplication.instance(), checked)
        self.settings.setValue("theme/dark", checked)

    def _restore_settings(self):
        dark = self.settings.value("theme/dark", False, type=bool)
        self.act_theme.setChecked(dark)
        theme.apply_theme(QApplication.instance(), dark)

        geom = self.settings.value("ui/geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        sizes = self.settings.value("ui/splitterSizes")
        if sizes:
            try:
                self.splitter.setSizes([int(x) for x in sizes])
            except (TypeError, ValueError):
                pass
        self._zoom_idx = int(self.settings.value("view/zoomIndex", self._zoom_idx))
        self._zoom_idx = max(0, min(len(ZOOM_STEPS) - 1, self._zoom_idx))

        # 前回ユーザー指定した文字色・塗りつぶし色を復元
        self.text_panel.restore_prefs(
            self.settings.value("text/color", "", type=str),
            self.settings.value("text/fill", "", type=str),
            self.settings.value("text/autoBg", True, type=bool))

    def _save_settings(self):
        self.settings.setValue("theme/dark", self.act_theme.isChecked())
        self.settings.setValue("ui/geometry", self.saveGeometry())
        self.settings.setValue("ui/splitterSizes", self.splitter.sizes())
        self.settings.setValue("view/zoomIndex", self._zoom_idx)
        self.settings.setValue("export/dpi", self._export_dpi)
        prefs = self.text_panel.current_prefs()
        self.settings.setValue("text/color", prefs["color"])
        self.settings.setValue("text/fill", prefs["fill"])
        self.settings.setValue("text/autoBg", prefs["auto_bg"])

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    # ================= 補助 =================
    def _require_doc(self) -> bool:
        if not self.doc.is_open:
            QMessageBox.information(self, "情報", "先に PDF を開いてください")
            return False
        return True
