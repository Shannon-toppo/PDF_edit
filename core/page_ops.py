"""ページの結合・分離・並べ替え・削除・PNG 書き出し。"""
from __future__ import annotations

import os

import fitz


def export_png(doc: fitz.Document, page_indices, out_dir: str,
               dpi: int = 150, prefix: str = "page") -> list[str]:
    """指定ページを PNG として out_dir に書き出し、生成パス一覧を返す。"""
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i in page_indices:
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        p = os.path.join(out_dir, f"{prefix}_{i + 1:04d}.png")
        pix.save(p)
        paths.append(p)
    return paths


def merge_pdf(doc: fitz.Document, other_path: str) -> int:
    """別 PDF を末尾に結合し、追加されたページ数を返す。"""
    src = fitz.open(other_path)
    added = src.page_count
    doc.insert_pdf(src)
    src.close()
    return added


def split_pages(doc: fitz.Document, from_idx: int, to_idx: int, out_path: str) -> None:
    """from_idx〜to_idx（両端含む）を新規 PDF として保存する。"""
    new = fitz.open()
    new.insert_pdf(doc, from_page=from_idx, to_page=to_idx)
    new.save(out_path, garbage=4, deflate=True)
    new.close()


def move_page(doc: fitz.Document, src_idx: int, dst_idx: int) -> None:
    """src_idx のページを dst_idx の位置へ移動する。"""
    if src_idx == dst_idx:
        return
    # fitz.move_page(pno, to): pno を to の *前* に挿入する仕様。
    # to の有効範囲は -1..page_count-1（末尾へ送るには -1 を使う）。
    to = dst_idx if dst_idx < src_idx else dst_idx + 1
    if to >= doc.page_count:
        to = -1
    doc.move_page(src_idx, to)


def delete_page(doc: fitz.Document, idx: int) -> None:
    doc.delete_page(idx)
