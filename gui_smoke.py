"""オフスクリーンで MainWindow を生成・操作し、例外が出ないか検証する。"""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def make_sample(path):
    doc = fitz.open()
    p = doc.new_page(width=400, height=300)
    p.insert_text((50, 100), "GUI Test 本文", fontsize=18)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40))
    pix.set_rect(pix.irect, (10, 120, 200))
    p.insert_image(fitz.Rect(250, 50, 350, 150), stream=pix.tobytes("png"))
    doc.new_page(width=400, height=300).insert_text((50, 80), "2 page", fontsize=14)
    doc.save(path)
    doc.close()


def main():
    tmp = tempfile.mkdtemp(prefix="gui_smoke_")
    sample = os.path.join(tmp, "s.pdf")
    make_sample(sample)

    app = QApplication([])
    w = MainWindow()
    w.show()

    # 開く
    w.doc.open(sample)
    w.pages.set_document(w.doc)
    w.images_panel.set_document(w.doc)
    w._refresh_all()
    assert w.doc.page_count == 2
    assert w._spans, "spans empty"
    print("OK open, spans:", len(w._spans), "images:", len(w._page_images))

    # ページ移動 / ズーム
    w._goto_page(1)
    w._zoom_step(+1)
    w._fit_width()
    w._fit_page()
    w._goto_page(0)

    # スパン選択 → 編集適用
    w._on_span_selected(0)
    payload = {
        "span": w._spans[0],
        "text": "編集済み",
        "fontfile": None,
        "fontsize": 20.0,
        "color": (1.0, 0.0, 0.0),
        "fill": (1.0, 1.0, 1.0),
        "overlay": False,
        "auto_bg": True,
    }
    w._apply_text_edit(payload)
    print("OK text edit applied; can_undo:", w.doc.can_undo())

    # 画像クリック相当
    if w._page_images:
        w._on_image_clicked(w._page_images[0]["xref"])
        print("OK image select")

    # ページ削除 / undo
    w._delete_page(1)
    assert w.doc.page_count == 1
    w.undo()
    print("OK delete+undo, pages:", w.doc.page_count)

    # ページ回転 / 複製 / 空白挿入
    w._rotate(90)
    assert w.doc.page(w.current_index).rotation == 90
    n = w.doc.page_count
    w._duplicate_page()
    assert w.doc.page_count == n + 1
    w._insert_blank()
    assert w.doc.page_count == n + 2
    print("OK rotate/duplicate/blank, pages:", w.doc.page_count)

    # 注釈追加（ハイライト）
    from app.page_view import MODE_ANNOT
    w._set_mode(MODE_ANNOT)
    w.annot_panel.combo_kind.setCurrentIndex(0)
    before = len(list(w.doc.page(w.current_index).annots()))
    w._apply_annotation(40, 40, 200, 60)
    after = len(list(w.doc.page(w.current_index).annots()))
    assert after > before
    print("OK annotation:", before, "->", after)

    # 注釈の全削除（コアロジック; ハンドラは確認ダイアログを出すため直接検証）
    from core import annots as _annots
    pg = w.doc.page(w.current_index)
    assert _annots.count_annotations(pg) >= 1
    removed = _annots.clear_annotations(pg)
    assert removed >= 1 and _annots.count_annotations(pg) == 0
    print("OK clear annotations:", removed)

    # 未保存フラグ → タイトルに * が付く
    w._update_title()
    assert "*" in w.windowTitle(), w.windowTitle()
    print("OK dirty title:", w.windowTitle())

    # 検索
    w.search_edit.setText("page")
    w._search_next()
    assert w._search_results, "no search results"
    print("OK search:", len(w._search_results), "hits")
    w._focus_search()
    w._goto_via_panel(0)

    # テーマ / 設定
    from app import theme as _theme
    w._set_theme(_theme.THEME_DARK)
    w._set_theme(_theme.THEME_LIGHT)
    w._set_theme(_theme.THEME_SYSTEM)
    w._save_settings()
    print("OK theme switch + settings save")

    # 保存
    out = os.path.join(tmp, "out.pdf")
    w.doc.save(out)
    assert os.path.getsize(out) > 0
    print("OK save:", os.path.getsize(out), "bytes")

    print("\nGUI SMOKE PASSED")


if __name__ == "__main__":
    main()
