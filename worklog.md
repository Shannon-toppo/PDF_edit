# Worklog — 軽量PDFエディター

このプロジェクトの実装の流れ・試したこと・注意点を時系列で記録する。

---

## 0. 方針決定（プランニング）

要件: ページの結合/分離/PNG書き出し、画像抽出、選択文字の色・フォント変更、GUI、できるだけ軽量。

ユーザー確認のうえ確定した方針:

- **技術スタック**: Python + PyMuPDF (fitz) + PySide6
  - PyMuPDF 1 つで「結合/分離/描画/画像抽出/テキスト操作」をすべて賄えるため、依存を 2 本柱に抑えられ軽量。
- **利用形態**: 個人・社内利用のみ → PyMuPDF の **AGPL-3.0** をそのまま利用可。
- **文字編集の現実解**: PDF は文字を「配置済みグリフ」として持つため自由編集は不可能。
  実用上限として **「スパン選択 → redaction で元グリフ除去 → 同じ baseline に新フォント・色・サイズで再描画」** 方式を採用。

---

## 1. 初期実装（コア + GUI）

### 構成
- `core/`（GUI 非依存）: `document.py` / `render.py` / `page_ops.py` / `images.py` / `text_edit.py` / `fonts.py`
- `app/`（PySide6）: `main_window.py` / `page_view.py` / `dialogs.py` / `panels/{pages,text,images}_panel.py`
- `main.py`（エントリ）

### 設計上のポイント
- **Undo/Redo**: PyMuPDF にネイティブ Undo が無いため、変更直前に `doc.tobytes()` でスナップショットを退避するスタック方式（`core/document.py`）。
- **保存**: 開いているファイル自身への上書きで `incremental` 制約に当たるのを避けるため、`tobytes()` してから書き出す方式に。
- **座標系**: PyMuPDF は左上原点 (pt)。画面ピクセル = pt × zoom。逆変換は scene 座標 / zoom。`page_view` のヒットテストはこの逆変換で実装。
- **文字配置**: 再描画は span の `origin`（baseline）に `insert_text` することで元位置に一致させる。

### 試して分かったこと / バグ修正
- **`doc.move_page(pno, to)` の `to` の範囲**: 末尾へ送るには `to = -1`。`to = page_count` を渡すと `ValueError: bad page number(s)`。
  → 末尾判定で `-1` に変換する処理を追加（`core/page_ops.py`）。
- **`QListWidget.setMovement` の enum**: `QAbstractItemView.Static` は存在せず `AttributeError`。
  → `QListWidget.Static` を使用。

### 検証
- ヘッドレス `smoke_test.py`（コアロジック）と、オフスクリーン `gui_smoke.py`（`QT_QPA_PLATFORM=offscreen` で MainWindow を生成・操作）を用意。
- 日本語フォント（MS Gothic）での編集 → 保存 → 再オープンで反映を確認。
  - 注意: コンソール出力は文字化けして見えるが、これは PowerShell の表示エンコーディングの問題。PDF 内テキストはアサーションで一致を確認済み。

---

## 2. スクロールでのページ送り

- 中央ビューが**下端でさらに下スクロール → 次ページ**、**上端で上スクロール → 前ページ**。
- `page_view.py` で `wheelEvent` をオーバーライドし、スクロールバーが端にある時だけ `nextPageRequested` / `prevPageRequested` を emit。
- 注意点: 前ページへ移動した直後にスクロール末尾へ寄せる処理は、再描画でスクロール範囲が確定してから行う必要があるため `QTimer.singleShot(0, ...)` を使用。

---

## 3. ライセンス方針の確認

- PyMuPDF は **AGPL-3.0**（または Artifex の商用ライセンス）。PySide6 は LGPL。
- AGPL は伝播するため、**配布する場合は配布物全体が AGPL-3.0** になる（自分のコードだけ MIT 等にはできない）。
- 個人・社内利用のみなら「配布」に当たらず義務は発生しない。
- AGPL を避けたい場合は (a) PyMuPDF 商用ライセンス購入、(b) `pypdf`+`pypdfium2`+`pikepdf` 等へ置換（ただし文字編集が大幅に困難化）。
- `pyproject.toml` の license は `AGPL-3.0-or-later` と明記。

---

## 4. uv によるパッケージ管理へ移行

- `pyproject.toml` を作成。アプリ構成（`app/`・`core/` を持ち、自身はパッケージ化しない）のため **`[tool.uv] package = false`**。
- `uv sync` で `.venv` と `uv.lock` を生成。`uv python pin 3.12`。
- pip 互換のため `requirements.txt` は **`uv export` で uv.lock から自動生成**（手書きしない）。
- `.gitignore` 追加（`.venv/`, `__pycache__/` など）。
- 注意点: 依存を変えたら `uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt` で再生成する。

---

## 5. 機能追加: ページ編集 / 注釈 / 全文検索 + 設定永続化 + ダークテーマ

### ページ回転・複製・空白挿入（`core/page_ops.py`）
- `rotate_page` = `page.set_rotation`、`duplicate_page` = `doc.fullcopy_page`、`insert_blank` = `doc.new_page`。
- メニュー「ページ」から操作。複製/空白挿入は `fullcopy_page` / `new_page` の `to`/`pno` も末尾は `-1` に注意。

### 注釈（`core/annots.py` + `app/panels/annot_panel.py`）
- ハイライト/下線/取り消し線/矩形/フリーテキスト/付箋。`page.add_*_annot` + `set_colors` + `update()`。
- `page_view.py` に**ラバーバンド描画モード**（`MODE_ANNOT`）を追加。ドラッグで範囲指定 → `annotRectDrawn(x0,y0,x1,y1)`（PDF 座標）を emit → 右ペインで選んだ種別・色で適用。

### 全文検索（`core/search.py`）
- `page.search_for(query)` を全ページに適用し `(page, rect)` を収集。
- 2 段目ツールバーに検索欄＋前へ/次へ。ヒットを黄色オーバーレイ表示し、`scroll_to_rect` でスクロール。
- 注意点: ページ再描画で scene が clear されるとハイライトも消えるため、`_refresh_page` で検索中なら現在ページのヒットを再ハイライトする。

### 設定の永続化（`QSettings`）
- `main.py` で `setOrganizationName`/`setApplicationName` を設定（Windows ではレジストリ `LightPDF\PdfEditor`）。
- 保存項目: ウィンドウ位置、スプリッタ幅、ズーム、既定 DPI、テーマ。`closeEvent` で保存、起動時 `_restore_settings` で復元。

### ダークテーマ（`app/theme.py`）
- `Fusion` スタイル + ダーク `QPalette`。メニュー「表示 → ダークテーマ」でトグルし設定に保存。

### この回の整理
- メニューバー（ファイル/編集/ページ/表示）を新設し増えた操作を整理。
- `gui_smoke.py` に新機能の検証を追加。

---

## 6. フォント選択のプレビュー表示

- ドロップダウンの各項目を**そのフォント自身で描画**し、表示名も実ファミリ名にする（`app/panels/text_panel.py`）。
- 実装: `QFontDatabase.addApplicationFont(path)` で実ファミリ名を取得し、各項目の `Qt.FontRole` に `QFont(family)` を設定。閉じた状態の表示欄もコンボの font を選択フォントに変えてプレビュー。
- ファイルパスは `UserRole` に保持し、適用時は `currentData()` で取得 → PyMuPDF への埋め込みは従来どおり正しいパスを使用。
- 同名ファミリ（例: Yu Gothic の太さ違いファイル）は**ファイル名を併記**して区別（`Yu Gothic（YuGothR）`）。
- 注意点: `fonts.list_fonts()` が返すのはファイル名の stem であって実ファミリ名ではない（`msgothic` → `MS Gothic`）。表示には実ファミリ名を使う。

---

## 7. フォントプレビューのキャッシュ化（高速化）

### 計測（230 フォント）
- 「毎回全ファイル `addApplicationFont`」: コンボ構築 ~0.052s、TextPanel 全体 ~0.11s。
- **判明**: スキャン対象は全て OS インストール済み → 描画に `addApplicationFont` は不要で、パス→ファミリ名解決のためだけに毎回再パースしていた。

### 実装（`app/font_cache.py`）
- 「パス → ファミリ名」を JSON でディスクキャッシュ（Qt の `CacheLocation`、約 20KB）。
- ファイルの **mtime/size 一致なら再パースをスキップ**。追加・変更分のみ再解決、削除分のエントリは掃除。
- キャッシュヒット時は `QFontDatabase.families()` 確認も `addApplicationFont` も省略（キャッシュ時点でインストール済み＝`QFont(family)` で描画可能）。

### 効果（TextPanel 構築）
- 初回（キャッシュ生成）: ~0.11s
- **2 回目以降（キャッシュ利用）: ~0.017s**

### 注意点
- `core/` は Qt 非依存に保つため、Qt を使う解決＋キャッシュは **app 層**（`app/font_cache.py`）に置いた。
- フォントの追加/更新/削除はキャッシュが自動差分更新するため手動クリア不要。
- 体感差は小さい（~数十 ms）が、フォント数が多い・低速ストレージほど効果が大きいクリーンな改善。

---

## 8. 右ペインの幅調整

- 既定の分割幅を `[200, 760, 320]` → `[190, 850, 240]` に縮小。
- 右ペインに **最大幅 280px / 最小幅 180px** を設定。
- 注意点: スプリッタ幅は `QSettings` に保存・復元されるため、既定値の変更だけでは過去の保存値が残る。**最大幅の上限**を設けることで保存値が大きくても自動的に収まり、閉じる際に上限値が再保存されて自己補正される。

---

## 9. ドラッグ＆ドロップで開く

- ウィンドウ全体（`MainWindow`）と中央ペイン（`PageView`）の両方でドロップ受け入れ。
- 注意点: 中央は `QGraphicsView` がドラッグイベントを内部処理して親へ伝播しないため、`PageView` 側に `setAcceptDrops(True)` と `dropEvent` を実装し `pdfDropped` シグナルで通知。
- 判定は共通関数 `first_pdf_url(mime)`（`app/page_view.py`）に集約。

## 10. Windows ですぐ使える化 / スタンドアロン EXE

- `run.bat`: ダブルクリックで `uv sync` → `.venv\Scripts\pythonw.exe main.py` をコンソールを残さず起動。
  - 注意点: `uv run python` だとコンソールが残るため、同期後は venv の **pythonw** を `start` で直接起動。
- `run-debug.bat`: コンソールを表示したまま起動（エラー確認用）。
- `create-shortcut.ps1`: デスクトップショートカット作成（WScript.Shell）。
- **EXE 化**: `uv add --dev pyinstaller` → `build-exe.bat`（`pyinstaller --onefile --windowed --name PDFedit main.py`）。
  - 生成物 `dist\PDFedit.exe` 約 63MB。PySide6 / PyMuPDF とも PyInstaller の標準フックで追加設定なしにバンドル可能だった。
  - 起動確認: PDF を引数に渡しても常駐（fitz 読み込み・PDF オープン成功）。
  - 注意点: onefile は起動時に一時展開が入る。配布時は AGPL-3.0 のソース提供義務に注意。`build/` `dist/` `*.spec` は `.gitignore`。

## 11. バージョン表記

- **単一の出どころ**: `app/__init__.py` の `__version__`。`pyproject.toml` は `package = false` なので `importlib.metadata.version()` は実行時に使えない（インストールされたパッケージではない）ため、Python 定数を真実とした。
- `main.py` が `app.setApplicationVersion(__version__)` を設定。`main_window.py` でタイトルバーに `PDFedit v0.1.0`（ファイル名がある場合は `… - file.pdf`）、「ヘルプ → バージョン情報」ダイアログに版・PyMuPDF/PySide6 の版・AGPL-3.0・対応ソース URL を表示（`_show_about`）。
- **EXE のメタ情報**: `version_info.txt`（PyInstaller の VSVersionInfo）を `build-exe.bat` が `--version-file` で参照し、EXE のプロパティ（右クリック→詳細）にファイルバージョン等を埋め込む。
- **注意（バージョン更新時は 3 箇所を手で揃える）**:
  1. `app/__init__.py` の `__version__`
  2. `pyproject.toml` の `version`
  3. `version_info.txt` の `filevers` / `prodvers` / `FileVersion` / `ProductVersion`
  - `package = false` のため自動同期はできない。各ファイルに同期注意のコメントを記載済み。
- 依存版は実行時取得: PyMuPDF は `fitz.version[0]`、PySide6 は `from PySide6 import __version__`。

---

## 12. 複数選択での文字色一括変更

- **操作**: テキストモードで通常クリック=単一選択、**Ctrl+クリックで複数選択にトグル**（追加/除去）。選択中スパンは赤枠で全て強調。
- **page_view.py**: `spanToggled(int)` シグナルを追加。選択マーカーを単一 `_sel_item` から複数 `_sel_items` に一般化（`mark_selections(bboxes)` / `mark_selection` は委譲）。`mousePressEvent` で `Ctrl` 修飾時は `spanToggled`、通常は `spanSelected` を emit。
- **text_panel.py**: `set_selection(spans)` を追加。0/1 件は従来の単一編集 UI、2 件以上は単一フィールドを無効化し「複数選択」グループ（文字色選択＋適用）を表示。`applyColorRequested((r,g,b))` を emit。
- **main_window.py**: 選択インデックス `self._sel_spans` を保持。`_apply_color_multi` が **1 スナップショット内**で各スパンを「redaction→origin に再描画」しつつ、文字・サイズ・（推定できる範囲で）元フォントは保ったまま色だけ差し替える。
- **元フォントの推定**（色だけ変えたいので見た目維持が重要）: `_resolve_span_fontfile` がスパンの `font` 名（subset 接頭辞 `ABCDEF+` を除去・英数字小文字に正規化）を、`font_cache.resolve_families` で作った「正規化ファミリ名→パス」表と突き合わせる。完全一致→部分一致→既定日本語フォントの順でフォールバック。表は遅延構築してキャッシュ。
- **注意**: 色変更も再描画方式なので、長文や複雑背景・回転ページでは従来同様のずれが起こりうる（単一編集と同じ制約）。`_refresh_page` で `_sel_spans` をリセットする。
- 検証: 3 スパンの PDF で 2 つを選択→赤に一括変更し、選択分だけ赤・未選択は黒のまま、`can_undo` が立つこと、フォント推定（`ABCDEF+MSGothic`→`msgothic.ttc`）を offscreen で確認。

---

## 13. ユーザー指定した文字色・塗りつぶし色の保持

- 従来はスパンを選ぶたびに `set_span` が文字色をそのスパンの色で上書きしていたため、ユーザーが選んだ色がリセットされていた。
- **text_panel.py**: `_color_user_set` / `_fill_user_set` フラグを追加。`_pick_color`/`_pick_fill` で True にし、以降 `set_span` / `set_selection` ではユーザー指定済みなら**スパンの色で上書きしない**（未指定時のみスパン色を採用）。
- **起動間の保持**: `current_prefs()` / `restore_prefs()` を追加し、`main_window` の `_save_settings`/`_restore_settings` が QSettings の `text/color`・`text/fill`・`text/autoBg` に保存・復元。復元した色は「ユーザー指定済み」扱いにする。
- 注意: 一度色を指定するとスパンの元色には自動で戻らない（明示的に色を選び直す）。`restore_prefs` は `text_panel` 生成後（`__init__` 内の `_restore_settings`）に呼ばれる前提。
- 検証: 青スパン→赤を指定→黒スパン選択でも赤を保持、複数選択でも保持、保存/復元の往復で色と user_set フラグが残ることを offscreen で確認。

---

## 14. テーマを 3 択化（システム追従 / ライト / ダーク）

- **背景の不具合**: 従来は「ダークテーマ」のチェック 1 個で `apply_theme(app, dark: bool)` を呼び、オフ時は `app.style().standardPalette()` を適用していた。ところが **Qt 6.8 の Fusion はデフォルトで OS のカラースキームに追従する**ため、OS がダークだと「オフ」でも標準パレット自体がダークになり、オンにすると独自パレットの「少し違うダーク」になる、という状態だった。
- **対応**: 真偽値を 3 値モード（`THEME_SYSTEM` / `THEME_LIGHT` / `THEME_DARK`）に変更。初期値は **システム追従**。
- **theme.py**: `apply_theme(app, mode: str)` に変更。Qt のカラースキーム API（`QStyleHints.setColorScheme` / `colorScheme`, Qt 6.5/6.8+）を使用。
  - システム: `ColorScheme.Unknown` で OS に追従し、`colorScheme()==Dark` なら独自ダークパレット、それ以外は標準パレット。
  - ライト: `ColorScheme.Light` を明示し、**OS がダークでも標準（ライト）パレットに固定**（上記不具合の本修正点）。
  - ダーク: `ColorScheme.Dark` + 独自ダークパレット。
  - `setColorScheme` は古い Qt に無いので `try/except (AttributeError, TypeError)` でガード。
- **main_window.py**: 単一チェックの `act_theme` を排他 `QActionGroup` の 3 項目（`act_theme_system/light/dark`）に置換し、「表示 → テーマ」サブメニューに配置。`_toggle_theme` を `_set_theme(mode)` に、`_theme_action(mode)` ヘルパーを追加。
- **設定の保存/移行**: QSettings は `theme/mode` に保存。`_restore_settings` は `theme/mode` が無ければ旧 `theme/dark`（真偽値）から移行（True→dark / False→light）、それも無ければ system。
- 検証: offscreen で 3 モードの `_set_theme` 切替＋ `_save_settings` の往復が通ること（`gui_smoke.py` を 3 モード対応に更新）。実ウィンドウ表示でも正常動作を確認済み。

---

## 15. UI/UX 調査（指摘事項の棚卸し）

GUI 一式（`main_window.py` / `page_view.py` / `panels/*.py` / `document.py`）を読み、UI/UX の問題点を影響度順に整理した。番号は対応タスクの ID。

### 🔴 高: データ損失リスク
1. **未保存の変更があっても無警告で破棄**: `PdfDocument.dirty` フラグは実装済み（`snapshot`/`undo`/`redo`→True、`open`/`save`→False）なのに UI が未参照。`closeEvent`（設定保存のみ）・`_open_path`・`dropEvent` のいずれも保存確認を出さず、編集中に閉じる/別ファイルを開くと作業が消える。
2. **タイトルバーに未保存インジケータがない**: `dirty` を使えば `*` 等を出せるのに未表示。保存済みか判別できない（1 とセット）。

### 🟠 中: 操作性の欠落
3. **標準ショートカット不足**: Ctrl+F（検索バーへフォーカス）が無い。ページ操作（回転・複製・削除・空白挿入）とモード切替にショートカット無し。PageUp/PageDown・Home/End・「N ページへ移動」も無く、大きな文書はサムネイルスクロール頼み。
4. **ホイールズーム/フィットが無い**: ズームは離散ステップのボタン/ショートカットのみ。Ctrl+ホイールズーム・「幅/全体に合わせる」が無い。さらに端でのホイールが隣ページに飛ぶ挙動（`wheelEvent`）が、ズーム操作と相まって戸惑いやすい。
5. **空状態のガイドが無い**: 未読込時は中央が灰色一色（D&D は受けるのに「ここに PDF をドロップ」等の誘導が無い）。

### 🟡 テーマ整合（テーマ作業の延長）
6. **ハードコード注記色がダークで低コントラスト**: `text_panel.py`（`#a06000` / `#607080`）・`annot_panel.py`（`#6a6a6a`）は固定色で、ダーク背景 (45,45,48) では特に灰系がほぼ読めない。パレット由来の色に寄せる。

### 🟢 低: 一貫性・細かな点
7. **「名前を付けて保存」後にタイトルが旧名称**（実バグ）: `save_file_as` が `"軽量PDFエディター - …"` をセットし、他箇所の `PDFedit v{__version__}` と不一致＋バージョン消失。
8. **操作後フィードバックの不統一**: 複製・空白挿入・結合・注釈・保存は statusBar に出すが、回転・並べ替え・削除は無言。
9. **複数選択時の右ペインが冗長**: 無効化された単一編集の色ボタンと、複数選択ボックスの色ボタンが同時表示。背景ボックスや注記もグレーで残り視覚的にうるさい。複数選択時は単一 UI を隠すと明快。
10. **ツールバーが全部テキストでアイコン無し**: 横に長く密度が低い。`QStyle.standardIcon` 併用で視認性向上。
11. **ページ操作のたびに全サムネイル再生成**: `pages.refresh()` が毎回全ページ `render_thumbnail`。回転/削除/移動のたびに全再描画で大きな PDF で重い。差分更新が望ましい。
12. **既存注釈の選択・編集・削除ができない**: 注釈はドラッグ追加のみで、消すには Undo しかない。

→ 着手順は **1+2 → 7 → 6 → 3 → 4 → 5 → 8 → 9 → 10 → 11 → 12** とする（即効・低コスト順）。各項目の実装記録は以降に追記する。

---

## 16. UI/UX 改善の実装（項目 1〜12）

`feature/ux-improvements` ブランチで上記 12 項目を着手順に実装した。

- **1+2 未保存ガード＋タイトル `*`**: `_update_title()`（未保存時に先頭 `*`、`PdfDocument.dirty` 参照）と `_confirm_discard()`（保存/破棄/キャンセルの 3 択ダイアログ）を追加。`closeEvent` と `_open_path`（ダイアログ・D&D・CLI の共通入口なので 1 箇所で全経路をカバー）でガード。`_update_actions()` から `_update_title()` を呼び、保存成功時にも更新。
- **7 「名前を付けて保存」後のタイトル**: 旧名称 `軽量PDFエディター - …` の直書きを廃し `_update_title()` に統一（バージョンとファイル名が正しく出る）。
- **6 注記色のテーマ追従**: ハードコード色を是正。橙の警告は明暗どちらでも読める `#e07b00` に。灰のヒット系（`#607080`/`#6a6a6a`）は色指定をやめ `font-style: italic;` のみにしてパレット既定色（テーマ追従）に委ねた（`text_panel.py`/`annot_panel.py`）。
- **3 ショートカット**: Ctrl+F（検索バーへフォーカス＋全選択）、PageUp/PageDown（前/次ページ）、Ctrl+Home/End（最初/最後）、Ctrl+G（ページへ移動ダイアログ `QInputDialog`）、Ctrl+1〜4（モード切替）。モード切替は文字入力中の誤爆を避けるため**修飾キー付き**にした。各アクションはメニューにも追加。
- **4 ズーム改善**: ズームモデルを離散インデックス `_zoom_idx` から**自由倍率 float `_zoom`**（`ZOOM_MIN/MAX=0.2/6.0`）に変更。`_zoom_step(±1)` は `ZOOM_STEPS` の隣へ、`_fit_width`/`_fit_page` はビューポート実寸から倍率算出。`PageView` に `zoomRequested` シグナルを追加し **Ctrl+ホイールでズーム**（ページ送りより優先）。設定キーは `view/zoomIndex`→`view/zoom`。
  - 注意: メソッド名 `_zoom` と属性 `self._zoom` が衝突するため、メソッドを `_zoom_step` に改名（インスタンス属性がクラスメソッドを隠す事故を回避）。
- **5 空状態ガイド**: `PageView.show_placeholder()` を追加し、未読込時にシーン中央へ「PDF をここにドロップ…」を表示（背景の灰色 (90,90,90) 上で読める明色固定）。起動時に表示し、ファイルを開くと `set_page_image` が置き換える。
- **8 操作後フィードバック**: 回転・移動・削除に statusBar メッセージを追加（他操作と統一）。
- **9 複数選択 UI**: 単一編集ウィジェット群を `single_box`（`QWidget` ラッパ）にまとめ、複数選択時は**丸ごと非表示**に（従来は無効化して残置 → 色ボタン重複や灰色残りで雑然としていた）。`_set_single_enabled` は表示/非表示の切替に変更。
- **10 ツールバーのアイコン**: `_assign_icons()` で開く/保存/Undo/Redo/ズーム/前後ページに `QStyle.standardIcon` を付与、全アクションにショートカット併記のツールチップを設定。`ToolButtonTextBesideIcon` でテキストも維持。
- **11 サムネイル差分更新**: `PagesPanel.refresh_one(idx)` を追加し、**回転は当該 1 枚のみ再生成**（全再描画を回避）。削除/移動/複製/挿入はページ順・枚数が変わるため従来通り全再構築（正しさ優先）。
- **12 注釈の削除**: `core/annots.py` に `count_annotations` / `clear_annotations` を追加。注釈パネルに「このページの注釈を削除」ボタン（`clearAnnotsRequested` シグナル）を置き、`MainWindow._clear_annotations` が確認ダイアログ→スナップショット→全削除。個別注釈の選択・編集は未対応（ヒットテスト実装が大きいため見送り。Undo＋ページ単位削除で当面の「消せない」問題は解消）。
- **検証**: `smoke_test.py` 全通過、`gui_smoke.py` を更新（`_zoom_step`/`_fit_*`、注釈全削除のコア検証、未保存タイトル `*`、`_focus_search`/`_goto_via_panel`）し全通過。offscreen で MainWindow を生成・表示し、空状態プレースホルダ・ツールバー・テーマ切替に例外が出ないことを確認。

---

## 横断的な注意点・既知の制約

- **文字編集は再描画方式**: 文字数を増やすと折り返し・位置がずれる場合がある。複雑な背景では塗りつぶし色の推定が外れる（手動指定 or 上書きモードで回避）。
- **回転ページ**: `get_text` の座標と `insert_text` の座標系が回転で食い違うため、90/270 度ページでの文字編集は位置がずれる可能性。
- **PyMuPDF は AGPL-3.0**: 配布・商用時は要ライセンス検討。
- **Undo はスナップショット方式**: 大きな PDF ではメモリ消費に注意（上限件数あり）。
- **コンソールの日本語文字化け**: PowerShell の表示エンコーディングの問題で、PDF 内データには影響しない。
- **検証は offscreen が主**: 実ウィンドウ表示は手動確認。`QT_QPA_PLATFORM=offscreen` で `gui_smoke.py` が全機能の結線を網羅。

## テスト
```powershell
uv run python smoke_test.py   # コアロジック（ヘッドレス）
uv run python gui_smoke.py    # GUI 結線（オフスクリーン）
```
