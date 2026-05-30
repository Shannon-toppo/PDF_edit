"""ヘッドレスでコアロジックを検証する簡易スモークテスト。"""
import os
import tempfile

import fitz

from core import images as imglib
from core import page_ops, text_edit
from core.document import PdfDocument


def make_sample(path, text="Hello PDF 編集テスト"):
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 100), text, fontsize=18)
    # 簡単な画像を埋め込む
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40))
    pix.set_rect(pix.irect, (200, 60, 30))
    img_bytes = pix.tobytes("png")
    page.insert_image(fitz.Rect(250, 50, 350, 150), stream=img_bytes)
    doc.save(path)
    doc.close()


def main():
    tmp = tempfile.mkdtemp(prefix="pdf_smoke_")
    a = os.path.join(tmp, "a.pdf")
    b = os.path.join(tmp, "b.pdf")
    make_sample(a, "Page A 本文")
    make_sample(b, "Page B 本文")

    d = PdfDocument()
    d.open(a)
    assert d.page_count == 1, d.page_count

    # --- 結合 ---
    d.snapshot()
    added = page_ops.merge_pdf(d.doc, b)
    assert added == 1
    assert d.page_count == 2, d.page_count
    print("OK merge ->", d.page_count, "pages")

    # --- Undo / Redo ---
    assert d.undo() and d.page_count == 1
    assert d.redo() and d.page_count == 2
    print("OK undo/redo")

    # --- 並べ替え / 削除 ---
    d.snapshot()
    page_ops.move_page(d.doc, 0, 1)
    page_ops.delete_page(d.doc, 1)
    assert d.page_count == 1
    print("OK move/delete ->", d.page_count)

    # --- PNG 書き出し ---
    pngs = page_ops.export_png(d.doc, [0], tmp, dpi=150)
    assert pngs and os.path.getsize(pngs[0]) > 0
    print("OK png ->", os.path.basename(pngs[0]), os.path.getsize(pngs[0]), "bytes")

    # --- 画像列挙 / 保存 ---
    d.open(a)
    imgs = imglib.list_images(d.page(0))
    assert imgs, "画像が見つからない"
    saved = imglib.save_image(d.doc, imgs[0]["xref"], os.path.join(tmp, "extracted"))
    assert os.path.getsize(saved) > 0
    print("OK image extract ->", os.path.basename(saved), imgs[0]["ext"])

    # --- 文字編集（再描画） ---
    spans = text_edit.get_spans(d.page(0))
    assert spans, "スパンが取れない"
    sp = spans[0]
    fonts = __import__("core.fonts", fromlist=["list_fonts", "default_font"])
    fmap = fonts.list_fonts()
    label = fonts.default_font(fmap)
    fontfile = fmap.get(label) if label else None
    print("using font:", label, fontfile)
    d.snapshot()
    text_edit.apply_text_edit(
        d.page(0), sp["bbox"], sp.get("origin", (sp["bbox"][0], sp["bbox"][3])),
        "編集後テキスト", fontfile, 20.0, (1, 0, 0), (1, 1, 1), overlay=False)
    new_spans = text_edit.get_spans(d.page(0))
    joined = " ".join(s["text"] for s in new_spans)
    assert "編集後テキスト" in joined, joined
    print("OK text edit ->", joined)

    # --- 保存して再オープン ---
    out = os.path.join(tmp, "out.pdf")
    d.save(out)
    d.open(out)
    assert "編集後テキスト" in d.page(0).get_text()
    print("OK save/reopen, text persisted")

    print("\nALL SMOKE TESTS PASSED. tmp dir:", tmp)


if __name__ == "__main__":
    main()
