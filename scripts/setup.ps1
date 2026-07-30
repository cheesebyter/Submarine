[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$backendPath = Join-Path $projectRoot "services\translation-backend"
$overlayPath = Join-Path $projectRoot "apps\desktop-overlay"

function Assert-LastExitCode {
    param([Parameter(Mandatory)][string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

$pythonVersion = & py -3.12 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
Assert-LastExitCode "Python version check"
if ($pythonVersion -ne "3.12") {
    throw "Python 3.12 is required. Install it and ensure 'py -3.12' works."
}

$nodeMajor = [int]((& node -p "process.versions.node.split('.')[0]"))
Assert-LastExitCode "Node.js version check"
if ($nodeMajor -ne 22) {
    throw "Node.js 22 is required."
}

if (-not (Test-Path -LiteralPath $venvPath)) {
    & py -3.12 -m venv $venvPath
}

$pythonExe = Join-Path $venvPath "Scripts\python.exe"
& $pythonExe -m pip install --upgrade "pip==26.1.2"
Assert-LastExitCode "pip bootstrap"
& $pythonExe -m pip install --editable "$backendPath[dev]"
Assert-LastExitCode "Python dependency installation"
& $pythonExe -m pip install --editable $overlayPath
Assert-LastExitCode "Overlay dependency installation"

Push-Location $projectRoot
try {
    & npm install
    Assert-LastExitCode "npm dependency installation"
}
finally {
    Pop-Location
}

Write-Host "Submarine development environment is ready."
Write-Host "Run: .\scripts\check.ps1"
