[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)][string]$Path,
    [string]$Language,
    [switch]$Translate,
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendPath = Join-Path $projectRoot "services\translation-backend"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Development environment missing. Run .\scripts\setup.ps1 first."
}
$media = (Resolve-Path -LiteralPath $Path).ProviderPath
$arguments = @("-m", "submarine_backend.transcribe_file", $media)
if ($Language) { $arguments += @("--language", $Language) }
if ($Translate) { $arguments += "--translate" }
if ($OutputDir) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $arguments += @("--output-dir", (Resolve-Path -LiteralPath $OutputDir).ProviderPath)
}

$env:PYTHONUTF8 = "1"
Push-Location $backendPath
try {
    & $pythonExe @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Transcription failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
