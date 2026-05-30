"""軽量PDFエディター エントリポイント。"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("軽量PDFエディター")
    window = MainWindow()
    window.show()
    # 引数で PDF パスが渡されたら開く
    if len(sys.argv) > 1:
        try:
            window.doc.open(sys.argv[1])
            window.pages.set_document(window.doc)
            window.images_panel.set_document(window.doc)
            window._refresh_all()
        except Exception:
            pass
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
