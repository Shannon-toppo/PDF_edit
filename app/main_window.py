"""メインウィンドウ: 3 ペイン構成と全機能の結線。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QSplitter, QStackedWidget, QToolBar,
                               QWidget)

from core import images as imglib
from core import page_ops, text_edit
from core.document import PdfDocument
from core.render import render_page

from .dialogs import ExportPngDialog, SplitDialog
from .page_view import MODE_IMAGE, MODE_PAN, MODE_TEXT, PageView
from .panels.images_panel import ImagesPanel
from .panels.pages_panel import PagesPanel
from .panels.text_panel import TextPanel

ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("軽量PDFエディター")
        self.resize(1280, 860)

        self.doc = PdfDocument()
        self.current_index = 0
        self._zoom_idx = 2  # 1.0

        # --- 中央ビュー ---
        self.view = PageView()
        self.view.spanSelected.connect(self._on_span_selected)
        self.view.imageSelected.connect(self._on_image_clicked)
        self.view.nextPageRequested.connect(self._scroll_to_next_page)
        self.view.prevPageRequested.connect(self._scroll_to_prev_page)

        # --- 左 ---
        self.pages = PagesPanel()
        self.pages.set_document(self.doc)
        self.pages.pageActivated.connect(self._goto_page)
        self.pages.moveRequested.connect(self._move_page)
        self.pages.deleteRequested.connect(self._delete_page)

        # --- 右 ---
        self.text_panel = TextPanel()
        self.text_panel.applyRequested.connect(self._apply_text_edit)
        self.images_panel = ImagesPanel()
        self.images_panel.set_document(self.doc)
        self.images_panel.saveSelected.connect(self._save_one_image)
        self.images_panel.saveAll.connect(self._save_all_images)
        self.images_panel.imageHighlighted.connect(self._highlight_image)
        self.right = QStackedWidget()
        self.right.addWidget(self.text_panel)    # index 0
        self.right.addWidget(self.images_panel)   # index 1

        splitter = QSplitter(Qt.Horizontal)
        left_holder = QWidget()
        lh = QHBoxLayout(left_holder)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.addWidget(self.pages)
        splitter.addWidget(left_holder)
        splitter.addWidget(self.view)
        splitter.addWidget(self.right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([200, 760, 320])
        self.setCentralWidget(splitter)

        self._spans: list[dict] = []
        self._page_images: list[dict] = []
        self._build_actions()
        self._build_toolbar()
        self.statusBar().showMessage("ファイルを開いてください")
        self._update_actions()

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

        # 選択モード
        self.act_mode_text = QAction("文字選択", self, checkable=True)
        self.act_mode_image = QAction("画像選択", self, checkable=True)
        self.act_mode_pan = QAction("移動", self, checkable=True)
        self.act_mode_text.setChecked(True)
        grp = QActionGroup(self)
        for a in (self.act_mode_text, self.act_mode_image, self.act_mode_pan):
            grp.addAction(a)
        self.act_mode_text.triggered.connect(lambda: self._set_mode(MODE_TEXT))
        self.act_mode_image.triggered.connect(lambda: self._set_mode(MODE_IMAGE))
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
        tb.addAction(self.act_mode_pan)
        tb.addSeparator()
        tb.addAction(self.act_zoom_out)
        tb.addAction(self.act_zoom_in)

    # ================= ファイル操作 =================
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF を開く", "",
                                              "PDF ファイル (*.pdf)")
        if not path:
            return
        try:
            self.doc.open(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"開けませんでした:\n{e}")
            return
        self.current_index = 0
        self.pages.set_document(self.doc)
        self.images_panel.set_document(self.doc)
        self._refresh_all()
        self.setWindowTitle(f"軽量PDFエディター - {os.path.basename(path)}")

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
        dlg = ExportPngDialog(self.doc.page_count, self.current_index, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "PNG の保存先フォルダ")
        if not out_dir:
            return
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

    # ================= 文字編集 =================
    def _on_span_selected(self, span_idx: int):
        if 0 <= span_idx < len(self._spans):
            span = self._spans[span_idx]
            self.text_panel.set_span(span)
            self.view.mark_selection(span["bbox"])
            self.right.setCurrentIndex(0)

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
        if mode == MODE_IMAGE:
            self.right.setCurrentIndex(1)
        elif mode == MODE_TEXT:
            self.right.setCurrentIndex(0)

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
        self.view.set_spans(self._spans)
        self._page_images = imglib.list_images(page)
        self.view.set_images(self._page_images)
        self.images_panel.set_images(self._page_images)
        self.text_panel.clear()

        self.statusBar().showMessage(
            f"ページ {self.current_index + 1} / {self.doc.page_count}  "
            f"(拡大 {int(zoom * 100)}%)")

    def _update_actions(self):
        ok = self.doc.is_open
        for a in (self.act_save, self.act_saveas, self.act_merge, self.act_split,
                  self.act_png, self.act_zoom_in, self.act_zoom_out,
                  self.act_mode_text, self.act_mode_image, self.act_mode_pan):
            a.setEnabled(ok)
        self.act_undo.setEnabled(ok and self.doc.can_undo())
        self.act_redo.setEnabled(ok and self.doc.can_redo())

    # ================= 補助 =================
    def _require_doc(self) -> bool:
        if not self.doc.is_open:
            QMessageBox.information(self, "情報", "先に PDF を開いてください")
            return False
        return True
