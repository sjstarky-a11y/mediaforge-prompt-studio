$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-EnvValue($name, $defaultValue) {
    $envPath = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path $envPath)) { return $defaultValue }
    $escapedName = [regex]::Escape($name)
    $line = Get-Content $envPath | Where-Object { $_ -match "^\s*$escapedName\s*=" } | Select-Object -Last 1
    if ($line) {
        $value = ($line -split "=", 2)[1].Trim()
        if ($value) { return $value }
    }
    return $defaultValue
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found."
}

& (Join-Path $PSScriptRoot "detect-hardware.ps1")
& (Join-Path $PSScriptRoot "detect-runtime.ps1")

$composeFile = Get-EnvValue "MEDIAFORGE_COMPOSE_FILE" "docker-compose.yml"
$composePath = Join-Path $PSScriptRoot $composeFile
docker compose -f $composePath up -d
if ($LASTEXITCODE -ne 0) {
    throw "Could not start MediaForge."
}

Start-Sleep -Seconds 3
$appPort = Get-EnvValue "MEDIAFORGE_APP_PORT" "18888"
Start-Process "http://127.0.0.1:$appPort/"
