"""文字の再描画方式による編集。

PDF は文字を「配置済みグリフ」として持つため自由編集は不可。ここでは
  1. 対象スパンの矩形を redaction で塗りつぶして元グリフを除去
  2. 同じ baseline (origin) に新しいフォント・色・サイズ・文字で再描画
という方式を取る。
"""
from __future__ import annotations

import re

import fitz

_REDACT_IMAGE_NONE = getattr(fitz, "PDF_REDACT_IMAGE_NONE", 0)


def get_spans(page: fitz.Page) -> list[dict]:
    """ページ内のテキストスパンを順に返す。各 span は fitz の dict 形式。"""
    spans = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:  # 0=テキスト, 1=画像
            continue
        for line in block.get("lines", []):
            for sp in line.get("spans", []):
                if sp.get("text", "").strip() == "":
                    continue
                spans.append(sp)
    return spans


def int_to_rgb01(color: int) -> tuple[float, float, float]:
    """get_text が返す sRGB 整数を 0..1 の (r,g,b) に変換する。"""
    return ((color >> 16 & 255) / 255.0,
            (color >> 8 & 255) / 255.0,
            (color & 255) / 255.0)


def rgb01_to_int(rgb: tuple[float, float, float]) -> int:
    r, g, b = (max(0, min(255, round(c * 255))) for c in rgb)
    return (r << 16) | (g << 8) | b


def sample_background(page: fitz.Page, bbox) -> tuple[float, float, float]:
    """スパンの左隣を 1px サンプリングして背景色を推定する。失敗時は白。"""
    r = fitz.Rect(bbox)
    sx = max(r.x0 - 2.0, 0.0)
    sy = (r.y0 + r.y1) / 2.0
    clip = fitz.Rect(sx, sy - 0.5, sx + 1.0, sy + 0.5)
    try:
        pix = page.get_pixmap(alpha=False, clip=clip)
        if pix.width and pix.height:
            px = pix.pixel(0, 0)
            return (px[0] / 255.0, px[1] / 255.0, px[2] / 255.0)
    except Exception:
        pass
    return (1.0, 1.0, 1.0)


def _font_alias(fontfile: str) -> str:
    """fitz に登録するための ASCII 別名を生成する。"""
    base = re.sub(r"[^A-Za-z0-9]", "", fontfile.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
    return "F" + (base[:16] or str(abs(hash(fontfile)) % 100000))


def apply_text_edit(page: fitz.Page, span_bbox, origin, text: str,
                    fontfile: str | None, fontsize: float,
                    color_rgb01: tuple[float, float, float],
                    fill_rgb01: tuple[float, float, float],
                    overlay: bool = False) -> None:
    """1 スパンを再描画方式で編集する。

    overlay=True の場合は元テキストを残したまま上書き描画する。
    """
    if not overlay:
        page.add_redact_annot(fitz.Rect(span_bbox), fill=fill_rgb01)
        page.apply_redactions(images=_REDACT_IMAGE_NONE)

    point = fitz.Point(origin[0], origin[1])
    if fontfile:
        alias = _font_alias(fontfile)
        page.insert_text(point, text, fontsize=fontsize, fontname=alias,
                         fontfile=fontfile, color=color_rgb01)
    else:
        page.insert_text(point, text, fontsize=fontsize,
                         fontname="helv", color=color_rgb01)
