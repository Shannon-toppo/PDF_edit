@echo off
rem === PDFedit デバッグ起動 ===
rem コンソールを開いたまま起動し、エラーや print 出力を確認できます。
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo [エラー] uv が見つかりません。 https://docs.astral.sh/uv/ を参照してください。
    pause
    exit /b 1
)

uv sync
echo.
echo === 起動します（終了するとログがここに残ります） ===
uv run python main.py

echo.
echo === 終了しました ===
pause
