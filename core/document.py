"""fitz.Document のラッパー。Undo/Redo をスナップショット方式で提供する。"""
from __future__ import annotations

import fitz


class PdfDocument:
    """開いている PDF を保持し、変更前スナップショットで Undo/Redo を実現するモデル。"""

    def __init__(self, undo_limit: int = 30):
        self.doc: fitz.Document | None = None
        self.path: str | None = None
        self._undo: list[bytes] = []
        self._redo: list[bytes] = []
        self._limit = undo_limit
        self.dirty = False

    # ---- 開く / 閉じる -------------------------------------------------
    def open(self, path: str) -> None:
        self.doc = fitz.open(path)
        self.path = path
        self._undo.clear()
        self._redo.clear()
        self.dirty = False

    def new_blank(self) -> None:
        self.doc = fitz.open()
        self.path = None
        self._undo.clear()
        self._redo.clear()
        self.dirty = False

    def close(self) -> None:
        if self.doc is not None:
            self.doc.close()
        self.doc = None
        self.path = None
        self._undo.clear()
        self._redo.clear()

    @property
    def is_open(self) -> bool:
        return self.doc is not None

    @property
    def page_count(self) -> int:
        return self.doc.page_count if self.doc else 0

    def page(self, index: int) -> fitz.Page:
        return self.doc[index]

    # ---- スナップショット式 Undo/Redo ---------------------------------
    def snapshot(self) -> None:
        """変更を加える *直前* に呼ぶ。現在の状態を Undo スタックへ退避する。"""
        if self.doc is None:
            return
        self._undo.append(self.doc.tobytes())
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()
        self.dirty = True

    def _reload(self, data: bytes) -> None:
        if self.doc is not None:
            self.doc.close()
        self.doc = fitz.open(stream=data, filetype="pdf")

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.doc.tobytes())
        self._reload(self._undo.pop())
        self.dirty = True
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.doc.tobytes())
        self._reload(self._redo.pop())
        self.dirty = True
        return True

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    # ---- 保存 ----------------------------------------------------------
    def save(self, path: str | None = None) -> str:
        """temp バイト列を経由して書き出し、開いているファイル自身にも上書き可能にする。"""
        target = path or self.path
        if target is None:
            raise ValueError("保存先が指定されていません")
        data = self.doc.tobytes(garbage=4, deflate=True)
        with open(target, "wb") as f:
            f.write(data)
        self.path = target
        self.dirty = False
        return target
