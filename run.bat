@echo off
rem === PDFedit 通常起動（ダブルクリックで実行） ===
rem 依存関係を同期し、コンソールを残さず GUI を起動します。
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo [エラー] uv が見つかりません。
    echo   https://docs.astral.sh/uv/ を参照してインストールしてください。
    echo   例: winget install astral-sh.uv
    pause
    exit /b 1
)

echo 依存関係を確認しています（初回はダウンロードに数分かかる場合があります）...
uv sync
if errorlevel 1 (
    echo [エラー] 依存関係の同期に失敗しました。
    pause
    exit /b 1
)

rem GUI を切り離して起動（このウィンドウは閉じても本体は動き続けます）
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0
