# Dot-source windows-postgres-helpers.ps1 safely (paths with spaces, e.g. OneDrive folders).
param([string]$ScriptsRoot = $PSScriptRoot)

$helperPath = Join-Path -Path $ScriptsRoot -ChildPath 'windows-postgres-helpers.ps1'
if (-not (Test-Path -LiteralPath $helperPath)) {
    Write-Host "xx> Missing helper script:" -ForegroundColor Red
    Write-Host "    $helperPath" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    Run 'git pull' to get scripts\windows-postgres-helpers.ps1 from the repo." -ForegroundColor Yellow
    Write-Host "    (Older copies used scripts\lib\ which is not in git.)" -ForegroundColor Yellow
    exit 1
}

. (Get-Item -LiteralPath $helperPath).FullName
