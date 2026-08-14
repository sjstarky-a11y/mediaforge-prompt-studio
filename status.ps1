$ErrorActionPreference = "Continue"
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

$appPort = Get-EnvValue "MEDIAFORGE_APP_PORT" "18888"
$ovmsPort = Get-EnvValue "MEDIAFORGE_OVMS_PORT" "8010"

Write-Host ""
Write-Host "Hardware detection"
Write-Host "------------------"
try {
    & (Join-Path $PSScriptRoot "detect-hardware.ps1")
} catch {
    Write-Host "Hardware detection failed:" $_.Exception.Message
}

Write-Host ""
Write-Host "MediaForge containers"
Write-Host "---------------------"
docker compose ps

Write-Host ""
Write-Host "Docker Model Runner"
Write-Host "-------------------"
docker model status

Write-Host ""
Write-Host "Adaptive runtime detection"
Write-Host "--------------------------"
try {
    & (Join-Path $PSScriptRoot "detect-runtime.ps1")
} catch {
    Write-Host "Runtime detection failed:" $_.Exception.Message
}

Write-Host ""
Write-Host "MediaForge health"
Write-Host "-----------------"
try {
    Invoke-RestMethod "http://127.0.0.1:$appPort/health" | Format-List
} catch {
    Write-Host "MediaForge app is not reachable on port $appPort."
}

Write-Host ""
Write-Host "SDXL / OVMS health"
Write-Host "------------------"
try {
    $r = Invoke-WebRequest "http://127.0.0.1:$ovmsPort/v2/health/ready" -UseBasicParsing -TimeoutSec 5
    Write-Host "OVMS ready:" ($r.StatusCode -eq 200)
} catch {
    Write-Host "OVMS ready: False (the first SDXL download may still be in progress)"
    $cachePath = Join-Path $PSScriptRoot "data\ovms-models"
    if (Test-Path $cachePath) {
        $bytes = (Get-ChildItem $cachePath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        if ($bytes) {
            Write-Host "Local SDXL cache:" ([math]::Round($bytes / 1GB, 2)) "GB"
        }
    }
}

Write-Host ""
Write-Host "Hardware profile"
Write-Host "----------------"
$profile = Join-Path $PSScriptRoot "runtime\hardware-profile.json"
if (Test-Path $profile) {
    Get-Content $profile
} else {
    Write-Host "No hardware profile yet. Run .\detect-hardware.ps1"
}

Write-Host ""
Write-Host "Runtime profile"
Write-Host "---------------"
$runtimeProfile = Join-Path $PSScriptRoot "runtime\runtime-profile.json"
if (Test-Path $runtimeProfile) {
    Get-Content $runtimeProfile
} else {
    Write-Host "No runtime profile yet. Run .\detect-runtime.ps1"
}
