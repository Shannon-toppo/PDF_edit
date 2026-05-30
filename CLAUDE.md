# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

PDFedit — 軽量な GUI PDF エディター（Python + PyMuPDF + PySide6）。コメント・UI 文言は日本語。

## Commands

依存は [uv](https://docs.astral.sh/uv/) で管理（`pyproject.toml` + `uv.lock`）。

```powershell
uv sync                         # .venv 作成・依存同期
uv run python main.py           # アプリ起動（uv run python main.py file.pdf でファイル指定）
uv run python smoke_test.py     # コアロジックのヘッドレステスト
uv run python gui_smoke.py      # GUI 結線テスト（要 QT_QPA_PLATFORM=offscreen）
.\build-exe.bat                 # PyInstaller で dist\PDFedit.exe を生成（onefile・windowed）
```

- **GUI テストは必ずオフスクリーンで**: 実行前に環境変数 `QT_QPA_PLATFORM=offscreen` を設定する（CI/ヘッドレスで MainWindow を生成・操作するため）。pytest は未導入。検証はこの 2 つのスモークスクリプトで行う。
- 個別の検証は `uv run python -c "..."` でオフスクリーン QApplication を立て、`MainWindow` のハンドラ（`_open_path`, `_apply_text_edit`, `_search_next` 等）を直接呼ぶのが定石（`gui_smoke.py` 参照）。
- 依存を変更したら pip 互換の `requirements.txt` を再生成: `uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt`（これは生成物。手書きしない）。
- `pyproject.toml` は `[tool.uv] package = false`（アプリ構成のため自身はパッケージ化しない）。PyInstaller は dev 依存。

## Architecture

**レイヤ分離が中心原則**: `core/` は **Qt 非依存**（`fitz`=PyMuPDF と標準ライブラリのみ）、`app/` が PySide6 GUI。Qt に依存する処理は `core/` に置かない（例: フォントのファミリ名解決は Qt が要るため `app/font_cache.py` に置いている）。

- `core/document.py` — `PdfDocument`: 開いている `fitz.Document` を保持するモデル。
- `core/{page_ops,images,text_edit,annots,search,fonts,render}.py` — 各機能の純ロジック。
- `app/main_window.py` — 3 ペイン構成（左=サムネイル / 中央=ページ表示 / 右=コンテキストパネル）と全機能の結線。メニュー・ツールバー・検索バー・設定の入口。
- `app/page_view.py` — `QGraphicsView` でページ画像＋オーバーレイ（文字スパン / 画像 / 注釈ラバーバンド / 検索ハイライト）を描画。操作モードは `MODE_TEXT/IMAGE/ANNOT/PAN`。
- `app/panels/{pages,text,images,annot}_panel.py` — 右ペインは `QStackedWidget`（0=text, 1=images, 2=annot）でモードに同期切替。

### 必ず守るパターン

1. **変更前にスナップショット**: ドキュメントを書き換える操作は、`page_ops`/`annots`/`text_edit` を呼ぶ *直前* に `self.doc.snapshot()` を呼ぶ（スナップショット方式の Undo/Redo）。その後 `_refresh_page()` と `self.pages.refresh(...)` で再描画し、`_update_actions()` を呼ぶ。
2. **Undo/Redo は `fitz.Document` オブジェクトを差し替える**（`document.py` の `_reload` が `tobytes()`→`fitz.open(stream=...)`）。そのため undo/redo 後は `self.pages.set_document(self.doc)` / `self.images_panel.set_document(self.doc)` で各パネルの参照を貼り直す（`_refresh_all_after_history` 参照）。古い `fitz.Page` 参照は無効になる前提で扱う。
3. **保存は `tobytes()` 経由**（`document.py` の `save`）。開いているファイル自身への上書きでも `incremental` 制約を避けるためバイト列にしてから書き出す。
4. **座標系**: PyMuPDF は左上原点 (pt)。画面ピクセル = PDF pt × zoom。`page_view` のヒットテストは scene 座標 / zoom で pt に戻す（`_bbox_to_scene` が逆変換）。
5. **`doc.move_page` / `fullcopy_page` / `new_page` の末尾位置は `to=-1`**。`to == page_count` は `ValueError`（`page_ops.py` でガード済み）。

### 文字編集の方式（重要な制約）
PDF は文字を「配置済みグリフ」として持つため自由編集は不可。`core/text_edit.py` は **redaction で元グリフ除去 → span の `origin`（baseline）に `insert_text` で再描画** する方式。文字数増で折り返しがずれる、複雑背景で塗りつぶし色推定が外れる、回転ページで座標がずれる、という既知の制約がある（UI にも明示）。

### その他
- **設定の永続化**: `QSettings`（`main.py` で org=`LightPDF` / app=`PdfEditor`、Windows ではレジストリ）。`MainWindow.closeEvent`→`_save_settings`、起動時 `_restore_settings`。右ペインは最大幅でキャップして保存値が大きくても収める。
- **フォント**: `core/fonts.py` が返すのはファイル名 stem。実ファミリ名への解決と「パス→ファミリ名」のディスクキャッシュは `app/font_cache.py`（mtime/size で無効化）。
- **ライセンス**: PyMuPDF は **AGPL-3.0**。配布（EXE 含む）時はソース提供義務に注意。個人・社内利用前提。
- **バージョン表記**: 実行時の単一の出どころは `app/__init__.py` の `__version__`（`package = false` のため `importlib.metadata` は使えない）。`main.py` が `setApplicationVersion` に渡し、`main_window.py` がタイトルバーと「ヘルプ → バージョン情報」ダイアログに表示。**バージョン更新時は 3 箇所を手で揃える**: ① `app/__init__.py` の `__version__`、② `pyproject.toml` の `version`、③ `version_info.txt`（`filevers`/`prodvers`/`FileVersion`/`ProductVersion`、EXE のプロパティに埋め込まれる）。各ファイルに同期注意のコメントあり。
