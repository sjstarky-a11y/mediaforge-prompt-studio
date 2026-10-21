param(
    [switch]$TestMode,
    [switch]$NoOpen,
    [switch]$SkipProofWait
)
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot "runtime-policy.ps1")
. (Join-Path $PSScriptRoot "scripts/runtime-common.ps1")
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

function Set-EnvValue($name, $value) {
    $envPath = Join-Path $PSScriptRoot ".env"
    $lines = @(Get-Content $envPath)
    $pattern = "^\s*$([regex]::Escape($name))\s*="
    $updated = $false
    $result = foreach ($line in $lines) {
        if ($line -match $pattern) {
            if (-not $updated) {
                "$name=$value"
                $updated = $true
            }
        } else {
            $line
        }
    }
    if (-not $updated) { $result += "$name=$value" }
    Set-Content -Path $envPath -Value $result -Encoding utf8
}

function Get-CacheSizeGB {
    $relativeCache = if ($selectedImageRuntime -eq "nvidia") { "data\huggingface" } else { "data\ovms-models" }
    $cachePath = Join-Path $PSScriptRoot $relativeCache
    if (-not (Test-Path $cachePath)) { return 0 }
    $bytes = (Get-ChildItem $cachePath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if (-not $bytes) { return 0 }
    return [math]::Round($bytes / 1GB, 2)
}

$appPort = Get-EnvValue "MEDIAFORGE_APP_PORT" "18888"
$imagePort = Get-EnvValue "MEDIAFORGE_IMAGE_PORT" (Get-EnvValue "MEDIAFORGE_OVMS_PORT" "8010")
$appUrl = "http://127.0.0.1:$appPort"
$imageReadyUrl = "http://127.0.0.1:$imagePort/v2/health/ready"

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

if ($TestMode) {
    Set-EnvValue "MEDIAFORGE_PROJECT_NAME" "mediaforge-validation"
    Set-EnvValue "MEDIAFORGE_APP_CONTAINER" "mediaforge-validation-app"
    Set-EnvValue "MEDIAFORGE_CPU_IMAGE_CONTAINER" "mediaforge-validation-cpu"
    Set-EnvValue "MEDIAFORGE_NVIDIA_IMAGE_CONTAINER" "mediaforge-validation-nvidia"
    Set-EnvValue "MEDIAFORGE_INTEL_IMAGE_CONTAINER" "mediaforge-validation-intel"
    Set-EnvValue "MEDIAFORGE_HERO_IMAGE_CONTAINER" "mediaforge-validation-hero"
    Set-EnvValue "MEDIAFORGE_INTEL_TEXT_CONTAINER" "mediaforge-validation-text"
    Set-EnvValue "MEDIAFORGE_INTEL_TEXT_PORT" "8014"
    Set-EnvValue "MEDIAFORGE_APP_PORT" "18889"
    Set-EnvValue "MEDIAFORGE_IMAGE_PORT" "8011"
    $appPort = "18889"
    $imagePort = "8011"
    $appUrl = "http://127.0.0.1:$appPort"
    $imageReadyUrl = "http://127.0.0.1:$imagePort/v2/health/ready"
}

Step "Detecting hardware"
& (Join-Path $PSScriptRoot "detect-hardware.ps1")

Step "Checking Docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker CLI was not found. Install Docker Desktop and run install.ps1 again."
}

try {
    docker info | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Docker is unavailable." }
} catch {
    Fail "Docker Desktop is not running."
}

Step "Checking Docker Compose"
try {
    docker compose version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Compose is unavailable." }
} catch {
    Fail "Docker Compose is not available."
}

Step "Checking local Docker Model Runner setup"
$existingStatus = @(& docker model status 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0 -or $existingStatus -notmatch "Docker Model Runner is running") {
    docker desktop enable model-runner --tcp=12434
    if ($LASTEXITCODE -ne 0) { Fail "Enable Docker Model Runner and host-side TCP in Docker Desktop > Settings > AI." }
}

Step "Checking Docker Model Runner"
try {
    docker model status | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Model Runner status returned exit code $LASTEXITCODE."
    }
} catch {
    Fail "Docker Model Runner is not ready."
}

Step "Building the shared application and runtime tools"
docker build -t $MediaForgeAppImage .
if ($LASTEXITCODE -ne 0) { Fail "Application build failed." }

Step "Detecting adaptive runtime profile"
& (Join-Path $PSScriptRoot "detect-runtime.ps1") | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -ne 0) {
    Fail "Could not detect the active Model Runner backend."
}

Step "Selecting Visual Proof Frame runtime"
$requestedImageRuntime = (Get-EnvValue "MEDIAFORGE_IMAGE_RUNTIME" "auto").ToLowerInvariant()
if ($requestedImageRuntime -notin @("auto", "cpu", "nvidia", "intel")) {
    Fail "MEDIAFORGE_IMAGE_RUNTIME must be auto, cpu, nvidia, or intel."
}

Select-MediaForgeRuntime -Requested $requestedImageRuntime -Root $PSScriptRoot
Set-EnvValue "MEDIAFORGE_IMAGE_PORT" $imagePort
$selectedImageRuntime = Get-EnvValue "MEDIAFORGE_ACTIVE_IMAGE_RUNTIME" "cpu"
$selectedNvidiaProfile = Get-EnvValue "MEDIAFORGE_NVIDIA_PROFILE" "cpu"
$composeFileName = Get-EnvValue "MEDIAFORGE_COMPOSE_FILE" "docker-compose.yml"
$composePath = Join-Path $PSScriptRoot $composeFileName
& (Join-Path $PSScriptRoot "detect-runtime.ps1")

$model = Get-EnvValue "MEDIAFORGE_MODEL" "ai/qwen2.5:3B-Q4_K_M"
Step "Pulling Prompt Doctor model: $model"
docker model pull $model | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -ne 0) {
    Fail "Could not pull $model."
}

Step "Creating local model caches"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data\ovms-models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data\huggingface") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data\intel-text-models") | Out-Null

Step "Building and starting MediaForge with $selectedImageRuntime image runtime"
docker compose -f $composePath up -d --build --remove-orphans | Tee-Object -FilePath $logFile -Append
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
if (-not $NoOpen) { Start-Process $appUrl }

Step "Preparing Visual Proof Frame / SDXL"
Write-Host "The first SDXL download is large and may take up to an hour on a slower connection."
Write-Host "MediaForge itself is already running. This download is not an installation failure."
Write-Host "You may use Prompt Doctor now. Keep this window open for the ready confirmation,"
Write-Host "or close it and run .\status.ps1 later; the containers will continue running."

$sdxlReady = $false
for ($i = 0; (-not $SkipProofWait) -and $i -lt 360; $i++) {
    try {
        $r = Invoke-WebRequest $imageReadyUrl -UseBasicParsing -TimeoutSec 5
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
    $imageContainer = if ($selectedImageRuntime -eq "intel") { Get-EnvValue "MEDIAFORGE_INTEL_IMAGE_CONTAINER" "mediaforge-ovms-intel" } elseif ($selectedImageRuntime -eq "nvidia") { Get-EnvValue "MEDIAFORGE_NVIDIA_IMAGE_CONTAINER" "mediaforge-image-cuda" } else { Get-EnvValue "MEDIAFORGE_CPU_IMAGE_CONTAINER" "mediaforge-ovms-sdxl-cpu" }
    Write-Host "For detailed progress: docker logs $imageContainer"
} else {
    Write-Host "Visual Proof Frame / SDXL is ready." -ForegroundColor Green
}

Write-Host ""
Write-Host "=============================================="
Write-Host "MediaForge Prompt Studio v0.4 Preview"
Write-Host "APP:  $appUrl"
Write-Host "Text route:" (Get-EnvValue "MEDIAFORGE_ACTIVE_TEXT_RUNTIME" "dmr")
Write-Host "Model Runner default/fallback: $model"
Write-Host "IMAGE:" (Get-EnvValue "MEDIAFORGE_IMAGE_BACKEND" "CPU")
Write-Host "SDXL READY: $sdxlReady"
Write-Host "HERO FRAME SET: optional; FLUX.2 downloads only after first-use confirmation (~12 GB)"
try {
    $runtimeProfile = Get-Content (Join-Path $PSScriptRoot "runtime\runtime-profile.json") -Raw | ConvertFrom-Json
    Write-Host "RUNTIME PROFILE: $($runtimeProfile.summary)"
} catch {
    Write-Host "RUNTIME PROFILE: unavailable (run .\detect-runtime.ps1)"
}
Write-Host "=============================================="

'{"package_version":"0.4-preview"}' | Set-Content (Join-Path $logDir "install-complete.json") -Encoding utf8
