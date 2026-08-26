$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot "runtime-policy.ps1")
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

function Get-NvidiaImageCapability {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $null }
    try {
        $profiles = foreach ($line in @(nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader,nounits 2>$null)) {
            $parts = $line -split ","
            if ($parts.Count -ge 3) {
                [PSCustomObject]@{
                    Name = $parts[0].Trim()
                    ComputeCapability = [double]::Parse($parts[1].Trim(), [Globalization.CultureInfo]::InvariantCulture)
                    VramGB = [math]::Round(([double]($parts[2].Trim())) / 1024, 1)
                }
            }
        }
        return $profiles | Sort-Object VramGB -Descending | Select-Object -First 1
    } catch {
        return $null
    }
}

function Test-DockerNvidiaAccess {
    try {
        docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi -L | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
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
    Fail "Docker Model Runner is required for MediaForge v0.3."
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

Step "Detecting adaptive runtime profile"
& (Join-Path $PSScriptRoot "detect-runtime.ps1") | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -ne 0) {
    Fail "Could not detect the active Model Runner backend."
}

Step "Selecting Visual Proof Frame runtime"
$requestedImageRuntime = (Get-EnvValue "MEDIAFORGE_IMAGE_RUNTIME" "auto").ToLowerInvariant()
if ($requestedImageRuntime -notin @("auto", "cpu", "nvidia")) {
    Fail "MEDIAFORGE_IMAGE_RUNTIME must be auto, cpu, or nvidia."
}

$nvidiaProfile = Get-NvidiaImageCapability
$nvidiaImageReady = $false
$nvidiaPolicy = $null
if ($nvidiaProfile) {
    $nvidiaPolicy = Get-MediaForgeNvidiaImagePolicy `
        -ComputeCapability $nvidiaProfile.ComputeCapability `
        -VramGB $nvidiaProfile.VramGB
    $nvidiaImageReady = $nvidiaPolicy.Eligible
    Write-Host "NVIDIA image candidate: $($nvidiaProfile.Name), compute $($nvidiaProfile.ComputeCapability), $($nvidiaProfile.VramGB) GB VRAM"
    Write-Host "Automatic image profile: $($nvidiaPolicy.Profile) - $($nvidiaPolicy.Reason)"
}

if ($nvidiaImageReady) {
    Write-Host "Validating NVIDIA access from Docker containers..."
    $nvidiaImageReady = Test-DockerNvidiaAccess
    if (-not $nvidiaImageReady) {
        Write-Host "Docker GPU validation failed; Visual Proof Frame will use the CPU fallback." -ForegroundColor Yellow
    }
}

if ($requestedImageRuntime -eq "nvidia" -and -not $nvidiaImageReady) {
    Fail "The NVIDIA image profile requires CUDA compute capability 6.0+ and at least 4 GB VRAM, plus working Docker GPU access. Use MEDIAFORGE_IMAGE_RUNTIME=cpu or auto."
}

$selectedImageRuntime = if ($requestedImageRuntime -eq "nvidia" -or ($requestedImageRuntime -eq "auto" -and $nvidiaImageReady)) { "nvidia" } else { "cpu" }
$selectedNvidiaProfile = if ($selectedImageRuntime -eq "nvidia") { $nvidiaPolicy.Profile } else { "cpu" }
$selectedOffloadMode = if ($selectedImageRuntime -eq "nvidia") { $nvidiaPolicy.OffloadMode } else { "none" }
$composeFileName = if ($selectedImageRuntime -eq "nvidia") { "docker-compose.nvidia.yml" } else { "docker-compose.yml" }
$composePath = Join-Path $PSScriptRoot $composeFileName

Set-EnvValue "MEDIAFORGE_ACTIVE_IMAGE_RUNTIME" $selectedImageRuntime
Set-EnvValue "MEDIAFORGE_COMPOSE_FILE" $composeFileName
Set-EnvValue "MEDIAFORGE_IMAGE_PORT" $imagePort
Set-EnvValue "MEDIAFORGE_IMAGE_DEVICE" $(if ($selectedImageRuntime -eq "nvidia") { "CUDA" } else { "CPU" })
Set-EnvValue "MEDIAFORGE_IMAGE_API_URL" $(if ($selectedImageRuntime -eq "nvidia") { "http://image-cuda:8000/v3" } else { "http://ovms-sdxl:8000/v3" })
Set-EnvValue "MEDIAFORGE_IMAGE_BACKEND" $(if ($selectedImageRuntime -eq "nvidia") { "NVIDIA CUDA / Diffusers" } else { "OpenVINO CPU" })
Set-EnvValue "MEDIAFORGE_NVIDIA_PROFILE" $selectedNvidiaProfile
Set-EnvValue "MEDIAFORGE_NVIDIA_OFFLOAD_MODE" $selectedOffloadMode

Write-Host "Selected image runtime: $selectedImageRuntime ($composeFileName)"
if ($selectedImageRuntime -eq "nvidia") {
    Write-Host "NVIDIA execution profile: $selectedNvidiaProfile (offload: $selectedOffloadMode)"
}
& (Join-Path $PSScriptRoot "detect-runtime.ps1") | Tee-Object -FilePath $logFile -Append

$model = Get-EnvValue "MEDIAFORGE_MODEL" "ai/qwen2.5:3B-Q4_K_M"
Step "Pulling Prompt Doctor model: $model"
docker model pull $model | Tee-Object -FilePath $logFile -Append
if ($LASTEXITCODE -ne 0) {
    Fail "Could not pull $model."
}

Step "Creating local model caches"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data\ovms-models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data\huggingface") | Out-Null

Step "Building and starting MediaForge with $selectedImageRuntime image runtime"
docker compose -f $composePath up -d --build | Tee-Object -FilePath $logFile -Append
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
    $imageContainer = if ($selectedImageRuntime -eq "nvidia") { "mediaforge-image-cuda" } else { "mediaforge-ovms-sdxl-cpu" }
    Write-Host "For detailed progress: docker logs $imageContainer"
} else {
    Write-Host "Visual Proof Frame / SDXL is ready." -ForegroundColor Green
}

Write-Host ""
Write-Host "=============================================="
Write-Host "MediaForge Prompt Studio v0.3 Adaptive Runtime"
Write-Host "APP:  $appUrl"
Write-Host "LLM:  $model"
Write-Host "IMAGE:" $(if ($selectedImageRuntime -eq "nvidia") { "SDXL / NVIDIA CUDA Diffusers [$selectedNvidiaProfile]" } else { "OpenVINO SDXL INT8 / CPU" })
Write-Host "SDXL READY: $sdxlReady"
Write-Host "HERO FRAME SET: optional; FLUX.2 downloads only after first-use confirmation (~12 GB)"
try {
    $runtimeProfile = Get-Content (Join-Path $PSScriptRoot "runtime\runtime-profile.json") -Raw | ConvertFrom-Json
    Write-Host "RUNTIME PROFILE: $($runtimeProfile.summary)"
} catch {
    Write-Host "RUNTIME PROFILE: unavailable (run .\detect-runtime.ps1)"
}
Write-Host "=============================================="
