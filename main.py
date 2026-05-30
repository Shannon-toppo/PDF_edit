"""PDFedit エントリポイント"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("LightPDF")
    app.setApplicationName("PdfEditor")
    app.setApplicationDisplayName("PDF_edit")
    window = MainWindow()
    window.show()
    # 引数で PDF パスが渡されたら開く
    if len(sys.argv) > 1:
        window._open_path(sys.argv[1])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
