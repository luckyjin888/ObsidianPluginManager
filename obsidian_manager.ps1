# ObsidianPluginManager 0.4.3 launcher (Windows PowerShell)
$ErrorActionPreference = "Stop"
$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) {
    & py -3 "$PSScriptRoot\obsidian_manager.py" @args
    exit $LASTEXITCODE
}
$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    & python "$PSScriptRoot\obsidian_manager.py" @args
    exit $LASTEXITCODE
}
Write-Host "需要 Python 3.10 或更高版本。请从 https://www.python.org/downloads/ 安装。" -ForegroundColor Yellow
exit 1
