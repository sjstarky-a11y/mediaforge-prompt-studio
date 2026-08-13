$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$logDir = Join-Path $PSScriptRoot "runtime"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "install-log.txt"

if (-not (Test-Path (Join-Path $PSScriptRoot ".env"))) {
    Copy-Item (Join-Path $PSScriptRoot ".env.example") (Join-Path $PSScriptRoot ".env")
}

function Get-EnvValue($name, $defaultValue) {
    $envPath = Join-Path $PSScriptRoot ".env"
    $escapedName = [regex]::Escape($name)
    $line = Get-Content $envPath | Where-Object { $_ -match "^\s*$escapedName\s*=" } | Select-Object -Last 1
    if ($line) {
        $value = ($line -split "=", 2)[1].Trim()
        if ($value) { return $value }
    }
    return $defaultValue
}

function Get-CacheSizeGB {
    $cachePath = Join-Path $PSScriptRoot "data\ovms-models"
    if (-not (Test-Path $cachePath)) { return 0 }
    $bytes = (Get-ChildItem $cachePath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if (-not $bytes) { return 0 }
    return [math]::Round($bytes / 1GB, 2)
}

$appPort = Get-EnvValue "MEDIAFORGE_APP_PORT" "18888"
$ovmsPort = Get-EnvValue "MEDIAFORGE_OVMS_PORT" "8010"
$appUrl = "http://127.0.0.1:$appPort"
$ovmsReady = "http://127.0.0.1:$ovmsPort/v2/health/ready"

function Step($text) {
    Write-Host ""
    Write-Host "==> $text"
    Add-Content -Path $logFile -Value "[$(Get-Date -Format s)] $text"
}

function Fail($text) {
    Write-Host ""
    Write-Host "ERROR: $text" -ForegroundColor Red
    Write-Host "Install log: $logFile"
    exit 1
}

Step "Detecting hardware"
& (Join-Path $PSScriptRoot "detect-hardware.ps1")

Step "Checking Docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker CLI was not found. Install Docker Desktop and run install.ps1 again."
}

try {
    docker info | Out-Null
} catch {
    Fail "Docker Desktop is not running."
}

Step "Checking Docker Compose"
try {
    docker compose version | Out-Null
} catch {
    Fail "Docker Compose is not available."
}

Step "Enabling Docker Model Runner with local TCP access"
try {
    docker desktop enable model-runner --tcp=12434 --cors all | Tee-Object -FilePath $logFile -Append
} catch {
    Write-Host "Automatic Model Runner enable did not complete."
    Write-Host "Open Docker Desktop > Settings > AI and enable Docker Model Runner + host-side TCP on port 12434."
    Fail "Docker Model Runner is required for Public Test v0.1a."
}

Step "Checking Docker Model Runner"
try {
    docker model status | Tee-Object -FilePath $logFile -Append
} catch {
    Fail "Docker Model Runner is not ready."
}

$model = "ai/qwen2.5:3B-Q4_K_M"
Step "Pulling Prompt Doctor model: $model"
docker model pull $model | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -ne 0) {
    Fail "Could not pull $model."
}

Step "Creating local model cache"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data\ovms-models") | Out-Null

Step "Building and starting MediaForge + SDXL CPU service"
docker compose up -d --build | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -ne 0) {
    Fail "docker compose up failed."
}

Step "Waiting for MediaForge web app"
$appReady = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $r = Invoke-WebRequest "$appUrl/health" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) {
            $appReady = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $appReady) {
    Fail "MediaForge app did not become ready. Run .\status.ps1 and docker compose logs."
}

Write-Host "MediaForge web app is ready. Prompt Doctor can be used now." -ForegroundColor Green
Start-Process $appUrl

Step "Preparing Visual Proof Frame / SDXL"
Write-Host "The first SDXL download is large and may take up to an hour on a slower connection."
Write-Host "MediaForge itself is already running. This download is not an installation failure."
Write-Host "You may use Prompt Doctor now. Keep this window open for the ready confirmation,"
Write-Host "or close it and run .\status.ps1 later; the containers will continue running."

$sdxlReady = $false
for ($i = 0; $i -lt 360; $i++) {
    try {
        $r = Invoke-WebRequest $ovmsReady -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) {
            $sdxlReady = $true
            break
        }
    } catch {}
    if (($i % 3) -eq 0) {
        $elapsedMinutes = [math]::Round(($i * 10) / 60, 1)
        $cacheGB = Get-CacheSizeGB
        Write-Host "SDXL download/loading in progress... elapsed: $elapsedMinutes min, local cache: $cacheGB GB"
    }
    Start-Sleep -Seconds 10
}

if (-not $sdxlReady) {
    Write-Host ""
    Write-Host "SETUP COMPLETE: MediaForge is running." -ForegroundColor Green
    Write-Host "Visual Proof Frame is still downloading or loading; this is not a failure." -ForegroundColor Yellow
    Write-Host "Run .\status.ps1 later to check readiness."
    Write-Host "For detailed progress: docker logs mediaforge-ovms-sdxl-cpu"
} else {
    Write-Host "Visual Proof Frame / SDXL is ready." -ForegroundColor Green
}

Write-Host ""
Write-Host "=============================================="
Write-Host "MediaForge Prompt Studio Public Test v0.1a CPU"
Write-Host "APP:  $appUrl"
Write-Host "LLM:  $model"
Write-Host "IMAGE: OpenVINO SDXL INT8 / CPU"
Write-Host "SDXL READY: $sdxlReady"
Write-Host "=============================================="
