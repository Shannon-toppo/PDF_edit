"""PDF 内画像の列挙・抽出・保存。"""
from __future__ import annotations

import os

import fitz


def list_images(page: fitz.Page) -> list[dict]:
    """ページ上の画像を列挙する。各要素に xref / ext / サイズ / ページ上の矩形を含む。"""
    doc = page.parent
    out = []
    seen = set()
    for info in page.get_images(full=True):
        xref = info[0]
        if xref in seen:
            continue
        seen.add(xref)
        try:
            rects = list(page.get_image_rects(xref))
        except Exception:
            rects = []
        try:
            d = doc.extract_image(xref)
        except Exception:
            continue
        out.append({
            "xref": xref,
            "ext": d.get("ext", "png"),
            "width": d.get("width"),
            "height": d.get("height"),
            "size": len(d.get("image", b"")),
            "rects": rects,
            "name": info[7] if len(info) > 7 and info[7] else f"image_{xref}",
        })
    return out


def extract_thumbnail(doc: fitz.Document, xref: int, max_px: int = 96):
    """画像のサムネイル用 bytes(PNG) を返す。失敗時 None。"""
    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha >= 4:  # CMYK 等は RGB へ変換
            pix = fitz.Pixmap(fitz.csRGB, pix)
        scale = max_px / max(pix.width, pix.height or 1)
        if scale < 1:
            pix = fitz.Pixmap(pix, 0)  # alpha 落とし
        return pix.tobytes("png")
    except Exception:
        return None


def save_image(doc: fitz.Document, xref: int, out_path_noext: str) -> str:
    """元バイト列をそのまま（再エンコードせず）保存し、拡張子付きパスを返す。"""
    d = doc.extract_image(xref)
    ext = d.get("ext", "png")
    path = f"{out_path_noext}.{ext}"
    with open(path, "wb") as f:
        f.write(d["image"])
    return path
