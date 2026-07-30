[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendPath = Join-Path $projectRoot "services\translation-backend"
$overlayPath = Join-Path $projectRoot "apps\desktop-overlay"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string]$Step,
        [Parameter(Mandatory)][scriptblock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Development environment missing. Run .\scripts\setup.ps1 first."
}

Push-Location $backendPath
try {
    Invoke-Checked "Ruff format check" { & $pythonExe -m ruff format --check . }
    Invoke-Checked "Ruff lint" { & $pythonExe -m ruff check . }
    Invoke-Checked "mypy" { & $pythonExe -m mypy src }
    Invoke-Checked "pytest" { & $pythonExe -m pytest }
}
finally {
    Pop-Location
}

Push-Location $overlayPath
try {
    Invoke-Checked "Overlay Ruff format check" { & $pythonExe -m ruff format --check . }
    Invoke-Checked "Overlay Ruff lint" { & $pythonExe -m ruff check . }
    Invoke-Checked "Overlay mypy" { & $pythonExe -m mypy src }
    Invoke-Checked "Overlay pytest" { & $pythonExe -m pytest }
}
finally {
    Pop-Location
}

Push-Location $projectRoot
try {
    Invoke-Checked "TypeScript check" { & npm run check }
    Invoke-Checked "JavaScript tests" { & npm test }
    Invoke-Checked "JavaScript build" { & npm run build }
}
finally {
    Pop-Location
}

Write-Host "All Submarine checks passed."
