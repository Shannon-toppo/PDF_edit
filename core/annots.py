"""注釈（ハイライト・下線・取り消し線・矩形・フリーテキスト・付箋）の追加。"""
from __future__ import annotations

import fitz

# 注釈タイプのキー（GUI と共有）
HIGHLIGHT = "highlight"
UNDERLINE = "underline"
STRIKEOUT = "strikeout"
RECT = "rect"
FREETEXT = "freetext"
NOTE = "note"

LABELS = {
    HIGHLIGHT: "ハイライト",
    UNDERLINE: "下線",
    STRIKEOUT: "取り消し線",
    RECT: "矩形",
    FREETEXT: "フリーテキスト",
    NOTE: "付箋（ノート）",
}


def _rect(r) -> fitz.Rect:
    return fitz.Rect(r)


def add_annotation(page: fitz.Page, kind: str, rect,
                   color=(1, 1, 0), text: str = "", fontsize: float = 12.0):
    """種別に応じた注釈を rect 範囲に追加する。"""
    r = _rect(rect)
    if kind == HIGHLIGHT:
        annot = page.add_highlight_annot(r)
        annot.set_colors(stroke=color)
        annot.update()
    elif kind == UNDERLINE:
        annot = page.add_underline_annot(r)
        annot.set_colors(stroke=color)
        annot.update()
    elif kind == STRIKEOUT:
        annot = page.add_strikeout_annot(r)
        annot.set_colors(stroke=color)
        annot.update()
    elif kind == RECT:
        annot = page.add_rect_annot(r)
        annot.set_colors(stroke=color)
        annot.set_border(width=1.5)
        annot.update()
    elif kind == FREETEXT:
        annot = page.add_freetext_annot(r, text or " ", fontsize=fontsize,
                                        text_color=color)
        annot.update()
    elif kind == NOTE:
        annot = page.add_text_annot(fitz.Point(r.x0, r.y0), text or "メモ")
    else:
        raise ValueError(f"未知の注釈種別: {kind}")
    return annot
