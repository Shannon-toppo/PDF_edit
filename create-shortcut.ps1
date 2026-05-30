# デスクトップに PDFedit のショートカットを作成する（コンソールを出さずに起動）。
# 事前に run.bat か `uv sync` を一度実行して .venv を用意しておくこと。
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pyw)) {
    Write-Host '先に run.bat（または uv sync）を実行して .venv を作成してください。'
    exit 1
}
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop 'PDFedit.lnk'
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = $pyw
$sc.Arguments = 'main.py'
$sc.WorkingDirectory = $root
$sc.IconLocation = $pyw
$sc.Description = 'PDFedit - 軽量PDFエディター'
$sc.Save()
Write-Host "ショートカットを作成しました: $lnk"
