# Shared helpers for local PostgreSQL on Windows (EDB / winget install).
# Loaded by setup-local-postgres.ps1 and start-local.ps1 (use LiteralPath — paths may contain spaces).

function Find-PostgresBinDirs {
    $dirs = @()
    $roots = @(
        'C:\Program Files\PostgreSQL',
        'C:\Program Files (x86)\PostgreSQL'
    )
    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $bin = Join-Path $_.FullName 'bin'
                if (Test-Path -LiteralPath (Join-Path $bin 'psql.exe')) { $dirs += $bin }
            }
    }
    $dirs | Sort-Object {
        if ($_ -match '\\PostgreSQL\\(\d+)\\') { [int]$Matches[1] } else { 0 }
    } -Descending
}

function Add-PostgresToPath {
    $added = @()
    foreach ($bin in (Find-PostgresBinDirs)) {
        if ($env:Path -notlike "*$bin*") {
            $env:Path = "$bin;$env:Path"
            $added += $bin
        }
    }
    return $added
}

function Get-PostgresCliVersion {
    if (-not (Get-Command psql -ErrorAction SilentlyContinue)) { return $null }
    $v = & psql --version 2>$null
    if ($LASTEXITCODE -eq 0) { return ($v -replace '\s+', ' ').Trim() }
    return $null
}

function Get-PostgresServiceNames {
    Get-Service -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^postgresql' -or $_.DisplayName -match 'PostgreSQL' } |
        Select-Object -ExpandProperty Name
}

function Start-PostgresWindowsService {
    $names = @(Get-PostgresServiceNames)
    if (-not $names.Count) {
        Write-Warn 'No PostgreSQL Windows service found. Start Postgres manually from Services (services.msc).'
        return $false
    }
    foreach ($name in $names) {
        $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
        if (-not $svc) { continue }
        if ($svc.Status -eq 'Running') {
            Write-Log "PostgreSQL service already running: $name"
            return $true
        }
        Write-Log "Starting PostgreSQL service: $name"
        try {
            Start-Service -Name $name -ErrorAction Stop
            Start-Sleep -Seconds 2
            if ((Get-Service -Name $name).Status -eq 'Running') { return $true }
        } catch {
            Write-Warn "Could not start service ${name}: $($_.Exception.Message)"
        }
    }
    return $false
}

function Test-PostgresPort {
    param([string]$HostName, [int]$Port)
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $client.Connect($HostName, $Port)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Test-PostgresReady {
    param([string]$HostName, [int]$Port, [string]$User)
    if (Get-Command pg_isready -ErrorAction SilentlyContinue) {
        $env:PGPASSWORD = $env:DB_PASSWORD
        & pg_isready -h $HostName -p $Port -U $User 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    }
    return (Test-PostgresPort -HostName $HostName -Port $Port)
}

function Wait-LocalPostgres {
    param([string]$HostName, [int]$Port, [string]$User)
    Write-Log "Waiting for PostgreSQL at ${HostName}:${Port}..."
    for ($i = 1; $i -le 60; $i++) {
        if (Test-PostgresReady -HostName $HostName -Port $Port -User $User) {
            Write-Log 'PostgreSQL is ready'
            return
        }
        if ($i -eq 5) { Start-PostgresWindowsService | Out-Null }
        Start-Sleep -Seconds 1
    }
    Write-Die @"
PostgreSQL is not reachable at ${HostName}:${Port}.
- Start the 'postgresql-*' service in services.msc
- Check backend\.env (DB_PORT is usually 5432 for local installs)
- Run: .\scripts\setup-local-postgres.ps1
"@
}

function Invoke-PostgresSql {
    param(
        [string]$Sql,
        [string]$Database = 'postgres'
    )
    if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
        return $null
    }
    $env:PGPASSWORD = $env:DB_PASSWORD
    & psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $Database -tAc $Sql 2>$null
}

function Test-PostgresConnection {
    $r = Invoke-PostgresSql 'SELECT 1'
    return "$r" -eq '1'
}

function Ensure-PostgresDatabase {
    $exists = Invoke-PostgresSql "SELECT 1 FROM pg_database WHERE datname='$($env:DB_NAME)'"
    if ("$exists" -eq '1') {
        Write-Log "Database '$($env:DB_NAME)' already exists"
        return
    }
    if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
        Write-Warn "psql not on PATH — create database '$($env:DB_NAME)' manually in pgAdmin"
        return
    }
    Write-Log "Creating database '$($env:DB_NAME)'"
    $env:PGPASSWORD = $env:DB_PASSWORD
    & psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d postgres -c "CREATE DATABASE `"$($env:DB_NAME)`";"
    if ($LASTEXITCODE -ne 0) {
        Write-Die "Failed to create database '$($env:DB_NAME)'. Check DB_USER and DB_PASSWORD in backend\.env"
    }
}

function Initialize-LocalPostgresWindows {
    $added = Add-PostgresToPath
    if ($added.Count) {
        Write-Log "Added PostgreSQL to PATH for this session: $($added[0])"
        $ver = Get-PostgresCliVersion
        if ($ver) { Write-Log $ver }
    } elseif (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
        Write-Warn @"
psql not found on PATH.
Install PostgreSQL for Windows, then re-run this script.
Typical location: C:\Program Files\PostgreSQL\16\bin\psql.exe
On Windows use:  psql --version   (not postgres --version)
"@
    } else {
        $ver = Get-PostgresCliVersion
        if ($ver) { Write-Log $ver }
    }

    $hostName = if ($env:DB_HOST) { $env:DB_HOST } else { 'localhost' }
    $port = if ($env:DB_PORT) { [int]$env:DB_PORT } else { 5432 }
    $user = if ($env:DB_USER) { $env:DB_USER } else { 'postgres' }

    if (Test-PostgresReady -HostName $hostName -Port $port -User $user) {
        Write-Log "PostgreSQL already running on port $port"
    } else {
        Start-PostgresWindowsService | Out-Null
        Wait-LocalPostgres -HostName $hostName -Port $port -User $user
    }

    if (Get-Command psql -ErrorAction SilentlyContinue) {
        if (-not (Test-PostgresConnection)) {
            Write-Die @"
Cannot connect as user '$user'. Update backend\.env:
  DB_PASSWORD=<your postgres password>
Then run: .\scripts\setup-local-postgres.ps1
"@
        }
        Write-Log 'PostgreSQL connection OK'
    }

    Ensure-PostgresDatabase
}

if (-not (Get-Command Write-Log -ErrorAction SilentlyContinue)) {
    function Write-Log([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
    function Write-Warn([string]$Message) { Write-Host "!!> $Message" -ForegroundColor Yellow }
    function Write-Die([string]$Message) { Write-Host "xx> $Message" -ForegroundColor Red; exit 1 }
}
