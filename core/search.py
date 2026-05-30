"""文書全体のテキスト検索。"""
from __future__ import annotations

import fitz


def search_document(doc: fitz.Document, query: str) -> list[tuple[int, fitz.Rect]]:
    """全ページを検索し、(ページ番号, ヒット矩形) の一覧を返す。"""
    results: list[tuple[int, fitz.Rect]] = []
    if not query:
        return results
    for i in range(doc.page_count):
        try:
            for r in doc[i].search_for(query):
                results.append((i, r))
        except Exception:
            continue
    return results
