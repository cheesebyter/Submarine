[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendPath = Join-Path $projectRoot "services\translation-backend"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Development environment missing. Run .\scripts\setup.ps1 first."
}

Write-Host "Downloading Systran/faster-whisper-large-v3 for explicit local use."
Write-Host "This is a multi-gigabyte download and is not performed during runtime."

Push-Location $backendPath
try {
    & $pythonExe -m submarine_backend.model_download
    if ($LASTEXITCODE -ne 0) {
        throw "Model download failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
