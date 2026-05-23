# Start DB Allocation Utility locally on Windows (PostgreSQL, API, frontend).
# Usage:
#   .\scripts\start-local.ps1              # local PostgreSQL (default)
#   .\scripts\start-local-postgres.cmd       # same as above
#   .\scripts\start-local.ps1 -Docker        # Postgres via Docker instead
#   .\scripts\start-local.ps1 -SkipDeps
param(
    [switch]$Docker,
    [switch]$LocalPostgres,
    [switch]$SkipDeps,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $RootDir 'backend'
$FrontendDir = Join-Path $RootDir 'frontend'
$RunDir = Join-Path $RootDir '.local'
$LogDir = Join-Path $RunDir 'logs'
$PidFile = Join-Path $RunDir 'pids'

. (Join-Path $PSScriptRoot 'lib\windows-postgres.ps1')

function Show-Help {
    @"
Usage: .\scripts\start-local.ps1 [options]

Starts PostgreSQL, runs migrations, then the FastAPI backend and React frontend.

Options:
  -LocalPostgres   Use local PostgreSQL on port 5432 (default when -Docker is not set)
  -Docker          Start Postgres via docker compose (host port 5433)
  -SkipDeps        Skip uv sync / yarn install (faster restarts)
  -Help            Show this help

Local PostgreSQL (Windows):
  First time:  scripts\setup-local-postgres.cmd
  Then:        scripts\start-local-postgres.cmd

URLs (default ports from backend\.env):
  App:      http://localhost:3000
  API:      http://localhost:8080
  API docs: http://localhost:8080/docs

Stop with: .\scripts\stop-local.ps1
"@
}

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Die "Missing required command: $Name. Install it and ensure it is on your PATH."
    }
}

function Load-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { return }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        Set-Item -Path "env:$key" -Value $val
    }
}

function Get-ShellExe {
    if (Get-Command pwsh -ErrorAction SilentlyContinue) { return 'pwsh' }
    return 'powershell'
}

function Start-DockerPostgres {
    Require-Command docker
    $env:DB_PORT = '5433'
    Write-Log "Starting PostgreSQL with docker compose (host port $($env:DB_PORT))..."
    Push-Location $RootDir
    try {
        docker compose up -d db
        if ($LASTEXITCODE -ne 0) { Write-Die 'docker compose up failed' }
    } finally {
        Pop-Location
    }
    $hostName = if ($env:DB_HOST) { $env:DB_HOST } else { 'localhost' }
    Wait-LocalPostgres -HostName $hostName -Port ([int]$env:DB_PORT) -User $(if ($env:DB_USER) { $env:DB_USER } else { 'postgres' })
}

function Setup-Backend {
    Require-Command uv
    Push-Location $BackendDir
    try {
        if (-not $SkipDeps) {
            Write-Log 'Installing backend dependencies (uv sync)...'
            uv sync
            if ($LASTEXITCODE -ne 0) { Write-Die 'uv sync failed' }
        }
        Write-Log 'Applying database migrations...'
        uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Write-Die 'alembic upgrade failed' }
    } finally {
        Pop-Location
    }
}

function Setup-Frontend {
    Require-Command yarn
    Push-Location $FrontendDir
    try {
        $nodeModules = Join-Path $FrontendDir 'node_modules'
        if (-not $SkipDeps -or -not (Test-Path $nodeModules)) {
            Write-Log 'Installing frontend dependencies (yarn)...'
            yarn install --frozen-lockfile 2>$null
            if ($LASTEXITCODE -ne 0) {
                yarn install
                if ($LASTEXITCODE -ne 0) { Write-Die 'yarn install failed' }
            }
        }
    } finally {
        Pop-Location
    }
}

function Start-AppProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$RunCommand
    )
    $logPath = Join-Path $LogDir "$Name.log"
    Write-Log "Starting $Name..."
    $shell = Get-ShellExe
    $title = "DB-Alloc-$Name"
    $wd = $WorkingDirectory.Replace("'", "''")
    $log = $logPath.Replace("'", "''")
    $inner = @"
`$host.UI.RawUI.WindowTitle = '$title'
Set-Location -LiteralPath '$wd'
Write-Host '==> $Name started — logging to .local\logs\$Name.log'
$RunCommand *>&1 | Tee-Object -FilePath '$log' -Append
Read-Host 'Process ended. Press Enter to close this window'
"@
    $proc = Start-Process -FilePath $shell -ArgumentList @('-NoExit', '-NoProfile', '-Command', $inner) -PassThru -WindowStyle Normal
    Add-Content -LiteralPath $PidFile -Value "$($proc.Id) $Name"
    Write-Log "$Name started (pid $($proc.Id), log: .local\logs\$Name.log)"
}

if ($Help) { Show-Help; exit 0 }

foreach ($a in $args) {
    switch -Regex ($a) {
        '^--?docker$' { $Docker = $true }
        '^--?local-postgres$' { $LocalPostgres = $true }
        '^--?skip-deps$' { $SkipDeps = $true }
        '^--?help$' { Show-Help; exit 0 }
    }
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
if (Test-Path $PidFile) { Remove-Item -LiteralPath $PidFile -Force }

$uvLocal = Join-Path $env:USERPROFILE '.local\bin'
if (Test-Path $uvLocal) { $env:Path = "$uvLocal;$env:Path" }

$envFile = Join-Path $BackendDir '.env'
if (-not (Test-Path $envFile)) {
    $example = Join-Path $BackendDir '.env.example'
    if (Test-Path $example) {
        Write-Log 'Creating backend\.env from .env.example'
        Copy-Item -LiteralPath $example -Destination $envFile
        Write-Warn 'Set DB_PASSWORD in backend\.env to your postgres password, or run: scripts\setup-local-postgres.cmd'
    } else {
        Write-Die 'backend\.env not found and no .env.example to copy'
    }
}

Load-EnvFile -Path $envFile
if (-not $env:DB_HOST) { $env:DB_HOST = 'localhost' }
if (-not $env:DB_PORT) { $env:DB_PORT = '5432' }
if (-not $env:DB_USER) { $env:DB_USER = 'postgres' }
if (-not $env:DB_PASSWORD) { $env:DB_PASSWORD = 'nagarro' }
if (-not $env:DB_NAME) { $env:DB_NAME = 'db_allocation' }
if (-not $env:API_PORT) { $env:API_PORT = '8080' }
if (-not $env:FRONTEND_PORT) { $env:FRONTEND_PORT = '3000' }

if ($Docker) {
    Start-DockerPostgres
    Ensure-PostgresDatabase
} else {
    # Default: local PostgreSQL (no automatic Docker fallback)
    if (-not $LocalPostgres) { $LocalPostgres = $true }
    Initialize-LocalPostgresWindows
}

Setup-Backend
Setup-Frontend

$apiPort = $env:API_PORT
$fePort = $env:FRONTEND_PORT
$beCmd = "uv run uvicorn app.main:app --reload --host 127.0.0.1 --port $apiPort"
$feCmd = "yarn dev --host 127.0.0.1 --port $fePort"

Start-AppProcess -Name 'backend' -WorkingDirectory $BackendDir -RunCommand $beCmd
Start-AppProcess -Name 'frontend' -WorkingDirectory $FrontendDir -RunCommand $feCmd

Start-Sleep -Seconds 2

Write-Host ''
Write-Log 'DB Allocation Utility is running'
Write-Host "  Frontend:  http://localhost:$fePort"
Write-Host "  Backend:   http://localhost:$apiPort"
Write-Host "  API docs:  http://localhost:$apiPort/docs"
Write-Host "  Postgres:  $($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)"
Write-Host ''
Write-Log 'Stop with: .\scripts\stop-local.ps1 (or close the Backend / Frontend windows)'
Write-Host ''
