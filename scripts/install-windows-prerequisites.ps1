# Install Windows prerequisites for DB Allocation Utility.
#
# Usage (run PowerShell as Administrator for best results):
#   .\scripts\install-windows-prerequisites.ps1
#   .\scripts\install-windows-prerequisites.ps1 -Database docker
#   .\scripts\install-windows-prerequisites.ps1 -All -Database postgres
#
param(
    [ValidateSet('ask', 'postgres', 'docker', 'none')]
    [string]$Database = 'ask',
    [switch]$All,
    [switch]$SkipNode,
    [switch]$SkipPython,
    [switch]$SkipUv,
    [switch]$SkipDatabase,
    [switch]$SkipPowerShell7,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

function Show-Help {
    @"
Install prerequisites on Windows for DB Allocation Utility.

Usage:
  .\scripts\install-windows-prerequisites.ps1 [options]

Options:
  -Database <ask|postgres|docker|none>  Which database stack to install (default: ask)
  -All                                  Install missing components without prompts
  -SkipNode         Skip Node.js / Yarn
  -SkipPython       Skip Python 3.12+
  -SkipUv           Skip uv
  -SkipDatabase     Skip PostgreSQL and Docker
  -SkipPowerShell7  Skip PowerShell 7 (Windows PowerShell 5.1 is usually already present)
  -Help             Show this help

Requires winget (App Installer from Microsoft Store on Windows 10/11).
Run as Administrator if installs fail with permission errors.

After install, open a NEW terminal and run:
  scripts\start-local.cmd
"@
}

function Write-Log([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "!!> $Message" -ForegroundColor Yellow }
function Write-Ok([string]$Message) { Write-Host " ok $Message" -ForegroundColor Green }
function Write-Die([string]$Message) {
    Write-Host " xx $Message" -ForegroundColor Red
    exit 1
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Refresh-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
    $uvBin = Join-Path $env:USERPROFILE '.local\bin'
    if (Test-Path $uvBin) { $env:Path = "$uvBin;$env:Path" }
}

function Test-Winget {
    if (-not (Test-Command winget)) {
        Write-Die @"
winget is not available. Install "App Installer" from the Microsoft Store, then re-run this script.
https://aka.ms/getwinget
"@
    }
}

function Install-WingetPackage {
    param(
        [string]$Id,
        [string]$DisplayName,
        [string[]]$ExtraArgs = @()
    )
    Write-Log "Installing $DisplayName ($Id)..."
    $args = @(
        'install', '--id', $Id, '-e',
        '--accept-package-agreements',
        '--accept-source-agreements'
    ) + $ExtraArgs
    & winget @args
    if ($LASTEXITCODE -gt 1) {
        Write-Warn "winget exit code $LASTEXITCODE for $DisplayName (0/1 often means already installed)"
    }
    Refresh-SessionPath
}

function Test-WingetInstalled([string]$Id) {
    $null = & winget list --id $Id -e 2>$null
    return $LASTEXITCODE -eq 0
}

function Test-NodeOk {
    if (-not (Test-Command node)) { return $false }
    $v = (node -v) -replace '^v', ''
    try {
        return [version]$v -ge [version]'18.0.0'
    } catch {
        return $false
    }
}

function Test-YarnOk {
    if (Test-Command yarn) { return $true }
    if (Test-Command corepack) {
        try {
            corepack enable 2>$null | Out-Null
            return (Test-Command yarn)
        } catch { return $false }
    }
    return $false
}

function Test-PythonOk {
    foreach ($cmd in @('python', 'py')) {
        if (-not (Test-Command $cmd)) { continue }
        try {
            $out = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($out -match '^(\d+)\.(\d+)$') {
                $maj = [int]$Matches[1]
                $min = [int]$Matches[2]
                if ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 12)) { return $true }
            }
        } catch { }
    }
    return $false
}

function Test-UvOk {
    return Test-Command uv
}

function Test-PostgresOk {
    return (Test-Command psql) -or (Test-Command pg_isready)
}

function Test-DockerOk {
    if (-not (Test-Command docker)) { return $false }
    try {
        docker info 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-PowerShell7Ok {
    return Test-Command pwsh
}

function Confirm-Install([string]$Message) {
    if ($All) { return $true }
    $r = Read-Host "$Message [Y/n]"
    return ($r -eq '' -or $r -match '^[yY]')
}

function Install-NodeAndYarn {
    if (Test-NodeOk) {
        Write-Ok "Node.js already installed: $(node -v)"
    } else {
        if (-not (Confirm-Install 'Install Node.js LTS via winget?')) { return }
        Install-WingetPackage -Id 'OpenJS.NodeJS.LTS' -DisplayName 'Node.js LTS'
    }
    Refresh-SessionPath

    if (Test-YarnOk) {
        Write-Ok "Yarn already available: $(yarn -v 2>$null)"
        return
    }
    if (-not (Confirm-Install 'Enable Yarn (via corepack, included with Node.js)?')) { return }
    if (Test-Command corepack) {
        Write-Log 'Enabling Yarn through corepack...'
        corepack enable
        corepack prepare yarn@stable --activate
        Refresh-SessionPath
    }
    if (-not (Test-YarnOk)) {
        Write-Log 'Installing Yarn via winget...'
        Install-WingetPackage -Id 'Yarn.Yarn' -DisplayName 'Yarn'
    }
    if (Test-YarnOk) { Write-Ok "Yarn ready: $(yarn -v)" } else { Write-Warn 'Yarn not found — open a new terminal or run: corepack enable' }
}

function Install-Python {
    if (Test-PythonOk) {
        Write-Ok 'Python 3.12+ already installed'
        return
    }
    if (-not (Confirm-Install 'Install Python 3.12 via winget?')) { return }
    Install-WingetPackage -Id 'Python.Python.3.12' -DisplayName 'Python 3.12' -ExtraArgs @(
        '--override',
        'InstallAllUsers=0 PrependPath=1 Include_launcher=1'
    )
    Refresh-SessionPath
    if (-not (Test-PythonOk)) { Write-Warn 'Python not on PATH yet — open a new terminal after install' }
    else { Write-Ok 'Python ready' }
}

function Install-UvTool {
    if (Test-UvOk) {
        Write-Ok "uv already installed: $(uv --version)"
        return
    }
    if (-not (Confirm-Install 'Install uv (Python package manager)?')) { return }
    if (Test-WingetInstalled 'astral-sh.uv') {
        Install-WingetPackage -Id 'astral-sh.uv' -DisplayName 'uv'
    } else {
        Write-Log 'Installing uv via official install script...'
        # Official installer: https://docs.astral.sh/uv/getting-started/installation/
        $installScript = {
            irm https://astral.sh/uv/install.ps1 | iex
        }
        & $installScript
    }
    Refresh-SessionPath
    if (Test-UvOk) { Write-Ok "uv ready: $(uv --version)" } else { Write-Warn 'uv not on PATH — open a new terminal' }
}

function Install-Postgres {
    if (Test-PostgresOk) {
        Write-Ok 'PostgreSQL client tools already on PATH'
        return
    }
    if (-not (Confirm-Install 'Install PostgreSQL 16 via winget?')) { return }
    # Versioned package id on winget; fallback to generic search message
    $pgIds = @('PostgreSQL.PostgreSQL.16', 'PostgreSQL.PostgreSQL.17', 'PostgreSQL.PostgreSQL')
    $installed = $false
    foreach ($id in $pgIds) {
        if (Test-WingetInstalled $id) {
            Write-Ok "PostgreSQL already installed ($id)"
            $installed = $true
            break
        }
    }
    if (-not $installed) {
        foreach ($id in $pgIds) {
            Write-Log "Trying winget package $id..."
            & winget install --id $id -e --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
            if ($LASTEXITCODE -le 1) { $installed = $true; break }
        }
    }
    Refresh-SessionPath
    if (Test-PostgresOk) {
        Write-Ok 'PostgreSQL installed'
        Write-Host '  Default superuser is often postgres — set DB_PASSWORD in backend\.env to match your install.'
    } else {
        Write-Warn 'PostgreSQL may be installed but psql is not on PATH. Add PostgreSQL\bin to PATH or use -Database docker.'
    }
}

function Install-DockerDesktop {
    if (Test-DockerOk) {
        Write-Ok 'Docker is installed and running'
        return
    }
    if (Test-Command docker) {
        Write-Warn 'Docker is installed but the daemon is not running. Start Docker Desktop from the Start menu.'
        return
    }
    if (-not (Confirm-Install 'Install Docker Desktop via winget? (large download; reboot may be required)')) { return }
    Install-WingetPackage -Id 'Docker.DockerDesktop' -DisplayName 'Docker Desktop'
    Write-Warn 'After install: start Docker Desktop once, wait until it is running, then use: .\scripts\start-local.ps1 -Docker'
}

function Install-PowerShell7 {
    $psVer = $PSVersionTable.PSVersion
    if ($psVer.Major -ge 7) {
        Write-Ok "Already running PowerShell $($psVer.ToString())"
        return
    }
    if (Test-PowerShell7Ok) {
        Write-Ok 'PowerShell 7 (pwsh) is installed'
        return
    }
    if (-not (Confirm-Install 'Install PowerShell 7 (pwsh)? Windows PowerShell 5.1+ is sufficient for this project.')) { return }
    Install-WingetPackage -Id 'Microsoft.PowerShell' -DisplayName 'PowerShell 7'
    Write-Ok 'Use pwsh for the best experience; scripts\start-local.cmd prefers pwsh when available.'
}

function Resolve-DatabaseChoice {
    if ($Database -ne 'ask') { return $Database }
    if ($All) { return 'docker' }
    Write-Host ''
    Write-Host 'Database for local development (choose one):'
    Write-Host '  1) Docker Desktop  (recommended — matches start-local.ps1 -Docker, port 5433)'
    Write-Host '  2) PostgreSQL       (native install, default port 5432 in backend\.env)'
    Write-Host '  3) Skip             (already installed / will install manually)'
    $c = Read-Host 'Enter 1, 2, or 3'
    switch ($c) {
        '1' { return 'docker' }
        '2' { return 'postgres' }
        '3' { return 'none' }
        default {
            Write-Warn 'Invalid choice; skipping database install.'
            return 'none'
        }
    }
}

if ($Help) { Show-Help; exit 0 }

foreach ($a in $args) {
    if ($a -match '^--?help$') { Show-Help; exit 0 }
    if ($a -match '^--?all$') { $All = $true }
    if ($a -match '^--?database=(.+)$') { $Database = $Matches[1].ToLower() }
    if ($a -eq '--docker' -or $a -eq '-docker') { $Database = 'docker' }
    if ($a -eq '--postgres' -or $a -eq '-postgres') { $Database = 'postgres' }
}

Write-Host ''
Write-Log 'DB Allocation Utility — Windows prerequisite installer'
Write-Host ''

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Warn 'Not running as Administrator. Some winget installs may fail; re-run PowerShell as Admin if needed.'
}

Test-Winget
Refresh-SessionPath

# PowerShell 5.1+ is always present on supported Windows; report version
Write-Ok "Windows PowerShell $($PSVersionTable.PSVersion)"

if (-not $SkipPowerShell7) { Install-PowerShell7 }
if (-not $SkipNode) { Install-NodeAndYarn }
if (-not $SkipPython) { Install-Python }
if (-not $SkipUv) { Install-UvTool }

if (-not $SkipDatabase) {
    $dbChoice = Resolve-DatabaseChoice
    switch ($dbChoice) {
        'postgres' { Install-Postgres }
        'docker' { Install-DockerDesktop }
        'none' { Write-Log 'Skipping database install' }
    }
}

Write-Host ''
Write-Log 'Summary'
Refresh-SessionPath

$checks = @(
    @{ Name = 'Node.js 18+'; Ok = (Test-NodeOk) },
    @{ Name = 'Yarn'; Ok = (Test-YarnOk) },
    @{ Name = 'Python 3.12+'; Ok = (Test-PythonOk) },
    @{ Name = 'uv'; Ok = (Test-UvOk) },
    @{ Name = 'PostgreSQL CLI (optional)'; Ok = (Test-PostgresOk) },
    @{ Name = 'Docker (optional)'; Ok = (Test-DockerOk) },
    @{ Name = 'PowerShell 7 (optional)'; Ok = (Test-PowerShell7Ok) }
)

foreach ($c in $checks) {
    if ($c.Ok) { Write-Ok $c.Name } else { Write-Warn "Missing: $($c.Name)" }
}

Write-Host ''
Write-Log 'Next steps'
Write-Host '  1. Close and reopen your terminal (refresh PATH).'
Write-Host '  2. Copy backend\.env.example to backend\.env if needed.'
Write-Host '  3. From project root run:  scripts\start-local.cmd'
Write-Host '     With Docker Postgres:  .\scripts\start-local.ps1 -Docker'
Write-Host ''
Write-Host 'If scripts are blocked:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned'
Write-Host ''
