[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendPath = Join-Path $projectRoot "services\translation-backend"
$fixturePath = Join-Path $projectRoot "var\logs\translation-benchmark"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Development environment missing. Run .\scripts\setup.ps1 first."
}

New-Item -ItemType Directory -Path $fixturePath -Force | Out-Null
Add-Type -AssemblyName System.Speech
$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synthesizer.SelectVoice("Microsoft Hedda Desktop")
    $synthesizer.SetOutputToWaveFile((Join-Path $fixturePath "german.wav"))
    $synthesizer.Speak(
        "Guten Morgen. Dies ist ein deutscher Satz. Wir übersetzen ihn ins Englische."
    )
    $synthesizer.SetOutputToNull()

    $synthesizer.SelectVoice("Microsoft David Desktop")
    $synthesizer.SetOutputToWaveFile((Join-Path $fixturePath "english.wav"))
    $synthesizer.Speak(
        "Good morning. Today we are testing a completely local translation into English."
    )
    $synthesizer.SetOutputToNull()
}
finally {
    $synthesizer.Dispose()
}

Push-Location $backendPath
try {
    & $pythonExe -m submarine_backend.benchmark `
        (Join-Path $fixturePath "german.wav") `
        (Join-Path $fixturePath "english.wav")
    if ($LASTEXITCODE -ne 0) {
        throw "Translation benchmark failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
