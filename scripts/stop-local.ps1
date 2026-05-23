# Stop processes started by start-local.ps1 on Windows.
$ErrorActionPreference = 'Stop'

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PidFile = Join-Path $RootDir '.local\pids'

if (-not (Test-Path $PidFile)) {
    Write-Host 'No running local stack found (.local\pids missing).'
    exit 0
}

Get-Content -LiteralPath $PidFile | ForEach-Object {
    $parts = $_ -split '\s+', 2
    if ($parts.Count -lt 2) { return }
    $procId = [int]$parts[0]
    $name = $parts[1]
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "Stopping $name (pid $procId)"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        # Stop child processes (e.g. uvicorn/node started under the shell)
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
}

Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Write-Host 'Stopped.'
