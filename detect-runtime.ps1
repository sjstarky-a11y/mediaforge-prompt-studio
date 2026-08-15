$ErrorActionPreference = "Stop"

$runtimeDir = Join-Path $PSScriptRoot "runtime"
$hardwarePath = Join-Path $runtimeDir "hardware-profile.json"
$runtimePath = Join-Path $runtimeDir "runtime-profile.json"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

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

$hardware = $null
if (Test-Path $hardwarePath) {
    try {
        $hardware = Get-Content $hardwarePath -Raw | ConvertFrom-Json
    } catch {
        $hardware = $null
    }
}

$cpuName = if ($hardware -and $hardware.cpu) {
    $hardware.cpu.ToString().Trim()
} else {
    (Get-CimInstance Win32_Processor | Select-Object -First 1).Name.Trim()
}

$gpuList = if ($hardware -and $hardware.gpus) { @($hardware.gpus) } else { @() }

$dmrStatus = "Unavailable"
$llmEngine = "llama.cpp"
$llmBackend = "Unknown"
$llmRuntime = "Unknown"
$llmAccelerator = "Unknown"
$llmVariant = $null
$gpuAcceleration = $false
$gpuVendor = $null
$activeModel = Get-EnvValue "MEDIAFORGE_MODEL" "ai/qwen2.5:3B-Q4_K_M"
$installedModelCount = 0

if (Get-Command docker -ErrorAction SilentlyContinue) {
    $statusLines = @(& docker model status 2>&1)
    $statusExitCode = $LASTEXITCODE
    $statusText = $statusLines -join "`n"

    if ($statusExitCode -eq 0 -and $statusText -match "Docker Model Runner is running") {
        $dmrStatus = "Running"
        $llamaLine = $statusLines | Where-Object { $_ -match "^\s*llama\.cpp\s+" } | Select-Object -First 1

        if ($llamaLine -and $llamaLine -match "Running\s+llama\.cpp\s+([^\s]+)") {
            $llmVariant = $Matches[1]
        }

        if ($llmVariant -match "-cuda(?:$|[-_])") {
            $llmBackend = "CUDA"
            $llmRuntime = "NVIDIA CUDA"
            $gpuAcceleration = $true
            $gpuVendor = "NVIDIA"
            $nvidiaGpu = $gpuList | Where-Object { $_.Vendor -eq "NVIDIA" } | Select-Object -First 1
            $llmAccelerator = if ($nvidiaGpu) { $nvidiaGpu.Name } else { "NVIDIA GPU" }
        } elseif ($llmVariant -match "-rocm(?:$|[-_])") {
            $llmBackend = "ROCm"
            $llmRuntime = "AMD ROCm"
            $gpuAcceleration = $true
            $gpuVendor = "AMD"
            $amdGpu = $gpuList | Where-Object { $_.Vendor -eq "AMD" } | Select-Object -First 1
            $llmAccelerator = if ($amdGpu) { $amdGpu.Name } else { "AMD GPU" }
        } elseif ($llmVariant -match "-vulkan(?:$|[-_])") {
            $llmBackend = "Vulkan"
            $llmRuntime = "GPU / Vulkan"
            $gpuAcceleration = $true
            $gpuCandidate = $gpuList | Where-Object { $_.Vendor -ne "Unknown" } | Select-Object -First 1
            $llmAccelerator = if ($gpuCandidate) { $gpuCandidate.Name } else { "Vulkan GPU" }
            $gpuVendor = if ($gpuCandidate) { $gpuCandidate.Vendor } else { "GPU" }
        } elseif ($llmVariant -match "-metal(?:$|[-_])") {
            $llmBackend = "Metal"
            $llmRuntime = "Apple Metal"
            $gpuAcceleration = $true
            $gpuVendor = "Apple"
            $llmAccelerator = "Apple GPU"
        } elseif ($llmVariant -match "-cpu(?:$|[-_])") {
            $llmBackend = "CPU"
            $llmRuntime = "CPU / llama.cpp"
            $llmAccelerator = $cpuName
        } elseif ($llamaLine) {
            $llmBackend = "Unknown"
            $llmRuntime = "llama.cpp / backend unknown"
            $llmAccelerator = "Unknown"
        }
    }
}

try {
    $modelResponse = Invoke-RestMethod "http://127.0.0.1:12434/models" -TimeoutSec 10
    if ($modelResponse -is [array]) { $installedModelCount = @($modelResponse).Count }
    elseif ($modelResponse.data) { $installedModelCount = @($modelResponse.data).Count }
    elseif ($modelResponse.models) { $installedModelCount = @($modelResponse.models).Count }
} catch {
    $installedModelCount = 0
}

$imageMode = (Get-EnvValue "MEDIAFORGE_ACTIVE_IMAGE_RUNTIME" (Get-EnvValue "MEDIAFORGE_IMAGE_RUNTIME" "cpu")).ToLowerInvariant()
if ($imageMode -eq "auto") { $imageMode = "cpu" }
$imageGpuAcceleration = $imageMode -eq "nvidia"
$imageMemoryProfile = if ($imageGpuAcceleration) {
    (Get-EnvValue "MEDIAFORGE_NVIDIA_PROFILE" "auto").ToLowerInvariant()
} else {
    "cpu"
}
$imageOffloadMode = if ($imageGpuAcceleration) {
    (Get-EnvValue "MEDIAFORGE_NVIDIA_OFFLOAD_MODE" "auto").ToLowerInvariant()
} else {
    "none"
}
$imageUsesCpuOffload = $imageGpuAcceleration -and $imageOffloadMode -in @("sequential", "model")
$imageDevice = if ($imageGpuAcceleration) { "CUDA" } else { "CPU" }
$imageBackend = $imageDevice
$imageNvidiaGpu = $gpuList | Where-Object { $_.Vendor -eq "NVIDIA" } | Select-Object -First 1
$imageAccelerator = if ($imageGpuAcceleration -and $imageNvidiaGpu) {
    $imageNvidiaGpu.Name
} elseif ($imageGpuAcceleration) {
    "NVIDIA GPU"
} else {
    $cpuName
}
$imageRuntime = if ($imageGpuAcceleration) {
    "NVIDIA CUDA / Diffusers SDXL"
} else {
    "CPU / OpenVINO SDXL INT8"
}
$imageEngine = if ($imageGpuAcceleration) { "Hugging Face Diffusers" } else { "OpenVINO Model Server" }
$imageModel = if ($imageGpuAcceleration) {
    Get-EnvValue "MEDIAFORGE_NVIDIA_IMAGE_MODEL" "stabilityai/stable-diffusion-xl-base-1.0"
} else {
    "OpenVINO/stable-diffusion-xl-base-1.0-int8-ov"
}
$overallGpuAcceleration = $gpuAcceleration -or $imageGpuAcceleration

$profileName = "Unknown"
if ($dmrStatus -ne "Running") {
    $profileName = "Degraded"
} elseif ($gpuAcceleration -and $imageGpuAcceleration) {
    $profileName = "GPU Accelerated"
} elseif ($gpuAcceleration -or $imageGpuAcceleration) {
    $profileName = "Hybrid"
} elseif ($llmBackend -eq "CPU" -and $imageDevice -eq "CPU") {
    $profileName = "CPU / Compatible"
}

$summary = switch ($profileName) {
    "Hybrid" {
        if ($gpuAcceleration) { "HYBRID | $gpuVendor LLM | CPU IMAGE" }
        else { "HYBRID | CPU LLM | NVIDIA IMAGE" }
    }
    "GPU Accelerated" { "GPU ACCELERATED | $gpuVendor LLM | NVIDIA IMAGE" }
    "CPU / Compatible" { "CPU | LLM + IMAGE" }
    "Degraded" { "DEGRADED | MODEL RUNNER UNAVAILABLE" }
    default { "RUNTIME BACKEND UNKNOWN" }
}

$displayMode = if (-not $overallGpuAcceleration) {
    "CPU"
} elseif (
    $gpuAcceleration -and
    $imageGpuAcceleration -and
    -not $imageUsesCpuOffload
) {
    "GPU"
} else {
    "GPU + CPU"
}

$profile = [ordered]@{
    schema_version          = 1
    package_version         = "0.2-dev"
    detected_at             = (Get-Date).ToString("s")
    profile                 = $profileName
    summary                 = $summary
    display_mode            = $displayMode
    gpu_acceleration        = $overallGpuAcceleration
    gpu_acceleration_scope  = if ($gpuAcceleration -and $imageGpuAcceleration) { "llm,image" } elseif ($gpuAcceleration) { "llm" } elseif ($imageGpuAcceleration) { "image" } else { "none" }
    llm                     = [ordered]@{
        status       = $dmrStatus
        engine       = $llmEngine
        backend      = $llmBackend
        runtime      = $llmRuntime
        accelerator  = $llmAccelerator
        variant      = $llmVariant
        default_model = $activeModel
        installed_models = $installedModelCount
    }
    image                   = [ordered]@{
        status       = "Configured"
        engine       = $imageEngine
        backend      = $imageBackend
        runtime      = $imageRuntime
        accelerator  = $imageAccelerator
        model         = $imageModel
        memory_profile = $imageMemoryProfile
        offload_mode  = $imageOffloadMode
        uses_cpu_offload = $imageUsesCpuOffload
    }
    note                    = "LLM and image runtimes are detected and reported independently. CPU remains the image fallback in v0.2-dev."
}

$profile | ConvertTo-Json -Depth 8 | Set-Content $runtimePath -Encoding UTF8

Write-Host ""
Write-Host "MediaForge adaptive runtime detection"
Write-Host "-------------------------------------"
Write-Host "Profile:" $profile.profile
Write-Host "User mode:" $profile.display_mode
Write-Host "LLM:" $profile.llm.runtime "[$($profile.llm.accelerator)]"
Write-Host "Default model:" $profile.llm.default_model "(installed models: $($profile.llm.installed_models))"
Write-Host "Image:" $profile.image.runtime
Write-Host "GPU acceleration:" $profile.gpu_acceleration "(scope: $($profile.gpu_acceleration_scope))"
Write-Host "Runtime report:" $runtimePath
