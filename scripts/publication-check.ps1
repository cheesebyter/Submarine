[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
    $candidateFiles = @(
        git ls-files --cached --others --exclude-standard
    ) | Where-Object {
        $_ -and
        -not $_.StartsWith("var/models/") -and
        -not $_.StartsWith("var/logs/")
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Could not enumerate publication candidates."
    }

    $forbiddenNames = @(
        ".env",
        ".env.local",
        "id_rsa",
        "id_ed25519"
    )
    $forbiddenExtensions = @(
        ".wav",
        ".mp3",
        ".flac",
        ".m4a",
        ".srt",
        ".vtt",
        ".pem",
        ".pfx",
        ".key"
    )
    $maxFileBytes = 5MB

    foreach ($relativePath in $candidateFiles) {
        $normalized = $relativePath.Replace("\", "/")
        $leaf = Split-Path -Leaf $relativePath
        $extension = [IO.Path]::GetExtension($relativePath).ToLowerInvariant()
        if ($leaf -in $forbiddenNames -or $extension -in $forbiddenExtensions) {
            throw "Forbidden publication candidate: $normalized"
        }
        $absolutePath = Join-Path $projectRoot $relativePath
        if ((Get-Item -LiteralPath $absolutePath).Length -gt $maxFileBytes) {
            throw "Publication candidate exceeds 5 MiB: $normalized"
        }
    }

    $textFiles = $candidateFiles | Where-Object {
        [IO.Path]::GetExtension($_).ToLowerInvariant() -in @(
            ".json", ".md", ".mjs", ".ps1", ".py", ".toml", ".ts", ".txt",
            ".yaml", ".yml"
        )
    }
    if ($textFiles) {
        $machinePaths = Select-String -Path $textFiles -Pattern @(
            '[A-Za-z]:\\Users\\',
            '[A-Za-z]:\\Project\\'
        )
        if ($machinePaths) {
            $machinePaths | ForEach-Object { Write-Error $_.ToString() }
            throw "Machine-specific absolute paths found."
        }

        $secretPatterns = Select-String -Path $textFiles -Pattern @(
            '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            '(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*["''][A-Za-z0-9+/=_-]{20,}["'']'
        )
        if ($secretPatterns) {
            $secretPatterns | ForEach-Object { Write-Error $_.ToString() }
            throw "Possible secret material found."
        }
    }

    Write-Host "Publication checks passed for $($candidateFiles.Count) files."
}
finally {
    Pop-Location
}
