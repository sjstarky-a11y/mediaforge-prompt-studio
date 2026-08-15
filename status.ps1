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
$imagePort = Get-EnvValue "MEDIAFORGE_IMAGE_PORT" (Get-EnvValue "MEDIAFORGE_OVMS_PORT" "8010")
$imageRuntime = Get-EnvValue "MEDIAFORGE_ACTIVE_IMAGE_RUNTIME" (Get-EnvValue "MEDIAFORGE_IMAGE_RUNTIME" "cpu")
$nvidiaProfile = Get-EnvValue "MEDIAFORGE_NVIDIA_PROFILE" "auto"
$nvidiaOffload = Get-EnvValue "MEDIAFORGE_NVIDIA_OFFLOAD_MODE" "auto"
$composeFile = Get-EnvValue "MEDIAFORGE_COMPOSE_FILE" "docker-compose.yml"
$composePath = Join-Path $PSScriptRoot $composeFile

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
docker compose -f $composePath ps

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
Write-Host "Visual Proof Frame health"
Write-Host "-------------------------"
try {
    $r = Invoke-WebRequest "http://127.0.0.1:$imagePort/v2/health/ready" -UseBasicParsing -TimeoutSec 5
    Write-Host "Image runtime:" $imageRuntime
    if ($imageRuntime -eq "nvidia") {
        Write-Host "NVIDIA profile:" $nvidiaProfile "(offload: $nvidiaOffload)"
    }
    Write-Host "Image service ready:" ($r.StatusCode -eq 200)
} catch {
    Write-Host "Image runtime:" $imageRuntime
    Write-Host "Image service ready: False (the first SDXL download may still be in progress)"
    $cachePath = Join-Path $PSScriptRoot $(if ($imageRuntime -eq "nvidia") { "data\huggingface" } else { "data\ovms-models" })
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
Write-Host "Prompt Doctor models"
Write-Host "--------------------"
try {
    $models = Invoke-RestMethod "http://127.0.0.1:$appPort/api/models" -TimeoutSec 10
    $installedCount = @($models.installed).Count
    Write-Host "Default model:" $models.default_model
    Write-Host "Installed models visible to MediaForge:" $installedCount
} catch {
    Write-Host "Model inventory unavailable."
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
