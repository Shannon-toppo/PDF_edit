@echo off
rem === PDFedit スタンドアロン EXE をビルド（PyInstaller / onefile・GUI） ===
rem 生成物: dist\PDFedit.exe（Python も uv も無い PC で動く単体実行ファイル）
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo [エラー] uv が必要です。 https://docs.astral.sh/uv/ を参照してください。
    pause
    exit /b 1
)

echo 依存（PyInstaller を含む）を同期しています...
uv sync
if errorlevel 1 ( echo [エラー] uv sync に失敗しました & pause & exit /b 1 )

echo ビルド中です（数分かかります）...
uv run pyinstaller --noconfirm --clean --onefile --windowed --name PDFedit --version-file version_info.txt main.py
if errorlevel 1 ( echo [エラー] ビルドに失敗しました & pause & exit /b 1 )

echo.
echo 完了しました: dist\PDFedit.exe
pause
