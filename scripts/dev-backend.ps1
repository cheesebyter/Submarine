[CmdletBinding()]
param(
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendPath = Join-Path $projectRoot "services\translation-backend"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Development environment missing. Run .\scripts\setup.ps1 first."
}

Push-Location $backendPath
try {
    $arguments = @(
        "-m", "uvicorn",
        "submarine_backend.main:app",
        "--host", "127.0.0.1",
        "--port", "8765"
    )
    if ($Reload) {
        $arguments += "--reload"
        Write-Warning "Reload mode restarts Whisper after Python file changes."
    }
    & $pythonExe @arguments
}
finally {
    Pop-Location
}
