# Configure and verify LOCAL PostgreSQL on Windows for DB Allocation Utility.
#
# Use this after installing PostgreSQL on Windows (not Docker).
#
#   .\scripts\setup-local-postgres.ps1
#   .\scripts\setup-local-postgres.ps1 -Password "your-postgres-password"
#
param(
    [string]$Password,
    [int]$Port = 5432,
    [string]$User = 'postgres',
    [string]$DatabaseName = 'db_allocation',
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $RootDir 'backend'
$EnvFile = Join-Path $BackendDir '.env'
$EnvExample = Join-Path $BackendDir '.env.example'

. (Join-Path $PSScriptRoot 'lib\windows-postgres.ps1')

function Show-Help {
    @"
Configure local PostgreSQL on Windows for this project.

Usage:
  .\scripts\setup-local-postgres.ps1
  .\scripts\setup-local-postgres.ps1 -Password "secret"

Updates backend\.env with DB_HOST, DB_PORT=5432, DB_USER, DB_PASSWORD, DB_NAME.
Finds psql under Program Files\PostgreSQL\*, starts the Windows service if needed,
and creates the database.

Then run:  scripts\start-local-postgres.cmd
"@
}

function Set-EnvLine {
    param([hashtable]$Lines, [string]$Key, [string]$Value)
    $pattern = "^\s*$([regex]::Escape($Key))\s*="
    $newLine = "$Key=$Value"
    $found = $false
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $pattern) {
            $Lines[$i] = $newLine
            $found = $true
            break
        }
    }
    if (-not $found) { $Lines.Add($newLine) }
}

function Update-BackendEnv {
    param([string]$Pass)
    $envPass = $Pass
    if ($envPass -match '[\s#=]') { $envPass = '"' + $envPass.Replace('"', '""') + '"' }
    if (-not (Test-Path $EnvFile)) {
        if (Test-Path $EnvExample) {
            Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
            Write-Log 'Created backend\.env from .env.example'
        } else {
            Write-Die 'backend\.env not found'
        }
    }
    $lines = [System.Collections.ArrayList]@(Get-Content -LiteralPath $EnvFile)
    Set-EnvLine -Lines $lines -Key 'DB_HOST' -Value 'localhost'
    Set-EnvLine -Lines $lines -Key 'DB_PORT' -Value "$Port"
    Set-EnvLine -Lines $lines -Key 'DB_USER' -Value $User
    Set-EnvLine -Lines $lines -Key 'DB_PASSWORD' -Value $envPass
    Set-EnvLine -Lines $lines -Key 'DB_NAME' -Value $DatabaseName
    $lines | Set-Content -LiteralPath $EnvFile -Encoding utf8
    Write-Log 'Updated backend\.env for local PostgreSQL (port 5432)'
}

function Load-EnvFile {
    param([string]$Path)
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) { return }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim().Trim('"').Trim("'")
        Set-Item -Path "env:$key" -Value $val
    }
}

if ($Help) { Show-Help; exit 0 }

Write-Host ''
Write-Log 'Setup local PostgreSQL (Windows)'
Write-Host ''

$bins = Find-PostgresBinDirs
if ($bins.Count) {
    Write-Log "Found PostgreSQL: $($bins[0])"
} else {
    Write-Warn 'Could not find PostgreSQL under Program Files. Ensure psql is installed.'
}

if (-not $Password) {
    $secure = Read-Host "Enter PostgreSQL password for user '$User'" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

if (-not $Password) { Write-Die 'Password is required' }

Update-BackendEnv -Pass $Password

$env:DB_HOST = 'localhost'
$env:DB_PORT = "$Port"
$env:DB_USER = $User
$env:DB_PASSWORD = $Password
$env:DB_NAME = $DatabaseName

Initialize-LocalPostgresWindows

Write-Host ''
Write-Log 'Local PostgreSQL is ready'
Write-Host "  Host:     localhost:$Port"
Write-Host "  Database: $DatabaseName"
Write-Host "  User:     $User"
Write-Host ''
Write-Log 'Start the app:  scripts\start-local-postgres.cmd'
Write-Host ''
