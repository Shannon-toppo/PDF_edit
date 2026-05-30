"""中央のページ表示。QGraphicsView 上にページ画像とスパン/画像のオーバーレイを描く。

座標系: scene 座標 = ページ画像のピクセル座標 = PDF ポイント x zoom。
ヒットテストは scene 座標を zoom で割って PDF ポイントに戻して判定する。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsView)

MODE_TEXT = "text"
MODE_IMAGE = "image"
MODE_PAN = "pan"


class PageView(QGraphicsView):
    spanSelected = Signal(int)     # self._spans のインデックス
    imageSelected = Signal(int)    # xref
    nextPageRequested = Signal()   # 下端でさらに下スクロール
    prevPageRequested = Signal()   # 上端でさらに上スクロール

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setBackgroundBrush(QBrush(QColor(90, 90, 90)))
        self.setDragMode(QGraphicsView.NoDrag)

        self._pixitem: QGraphicsPixmapItem | None = None
        self._zoom = 1.0
        self._spans: list[dict] = []
        self._images: list[dict] = []
        self._mode = MODE_TEXT
        self._hover_item: QGraphicsRectItem | None = None
        self._sel_item: QGraphicsRectItem | None = None
        self.setMouseTracking(True)

    # ---- 表示更新 ------------------------------------------------------
    def set_page_image(self, image: QImage, zoom: float) -> None:
        self._zoom = zoom
        self._scene.clear()
        self._pixitem = self._scene.addPixmap(QPixmap.fromImage(image))
        self._pixitem.setZValue(0)
        self._scene.setSceneRect(QRectF(image.rect()))
        self._hover_item = None
        self._sel_item = None

    def set_spans(self, spans: list[dict]) -> None:
        self._spans = spans

    def set_images(self, images: list[dict]) -> None:
        self._images = images

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._clear_hover()
        if mode == MODE_PAN:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.NoDrag)

    def clear_selection_marker(self) -> None:
        if self._sel_item is not None:
            self._scene.removeItem(self._sel_item)
            self._sel_item = None

    def mark_selection(self, bbox) -> None:
        """選択中スパンの矩形を強調表示する。"""
        self.clear_selection_marker()
        rect = self._bbox_to_scene(bbox)
        item = QGraphicsRectItem(rect)
        item.setPen(QPen(QColor(220, 40, 40), 1.5))
        item.setBrush(QBrush(QColor(220, 40, 40, 40)))
        item.setZValue(20)
        self._scene.addItem(item)
        self._sel_item = item

    # ---- スクロール ----------------------------------------------------
    def scroll_to_top(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.minimum())

    def scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def wheelEvent(self, event):
        # 下端でさらに下へ / 上端でさらに上へスクロールしたら隣のページへ送る
        if self._pixitem is not None:
            bar = self.verticalScrollBar()
            dy = event.angleDelta().y()
            if dy < 0 and bar.value() >= bar.maximum():
                self.nextPageRequested.emit()
                event.accept()
                return
            if dy > 0 and bar.value() <= bar.minimum():
                self.prevPageRequested.emit()
                event.accept()
                return
        super().wheelEvent(event)

    # ---- 内部ヘルパ ----------------------------------------------------
    def _bbox_to_scene(self, bbox) -> QRectF:
        x0, y0, x1, y1 = bbox
        z = self._zoom
        return QRectF(x0 * z, y0 * z, (x1 - x0) * z, (y1 - y0) * z)

    def _clear_hover(self) -> None:
        if self._hover_item is not None:
            self._scene.removeItem(self._hover_item)
            self._hover_item = None

    def _hit_span(self, px, py) -> int:
        for i, sp in enumerate(self._spans):
            x0, y0, x1, y1 = sp["bbox"]
            if x0 <= px <= x1 and y0 <= py <= y1:
                return i
        return -1

    def _hit_image(self, px, py) -> tuple[int, object]:
        for img in self._images:
            for r in img["rects"]:
                if r.x0 <= px <= r.x1 and r.y0 <= py <= r.y1:
                    return img["xref"], r
        return -1, None

    # ---- マウス --------------------------------------------------------
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self._mode == MODE_PAN or self._pixitem is None:
            return
        sp = self.mapToScene(event.position().toPoint())
        px, py = sp.x() / self._zoom, sp.y() / self._zoom
        rect = None
        if self._mode == MODE_TEXT:
            i = self._hit_span(px, py)
            if i >= 0:
                rect = self._bbox_to_scene(self._spans[i]["bbox"])
        elif self._mode == MODE_IMAGE:
            xref, r = self._hit_image(px, py)
            if xref >= 0:
                rect = self._bbox_to_scene((r.x0, r.y0, r.x1, r.y1))
        self._clear_hover()
        if rect is not None:
            item = QGraphicsRectItem(rect)
            item.setPen(QPen(QColor(40, 120, 220), 1.0))
            item.setBrush(QBrush(QColor(40, 120, 220, 35)))
            item.setZValue(10)
            self._scene.addItem(item)
            self._hover_item = item
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if self._mode == MODE_PAN or self._pixitem is None:
            super().mousePressEvent(event)
            return
        sp = self.mapToScene(event.position().toPoint())
        px, py = sp.x() / self._zoom, sp.y() / self._zoom
        if self._mode == MODE_TEXT:
            i = self._hit_span(px, py)
            if i >= 0:
                self.spanSelected.emit(i)
        elif self._mode == MODE_IMAGE:
            xref, _ = self._hit_image(px, py)
            if xref >= 0:
                self.imageSelected.emit(xref)
        super().mousePressEvent(event)
