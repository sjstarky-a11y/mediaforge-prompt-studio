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

$imageDevice = (Get-EnvValue "MEDIAFORGE_IMAGE_DEVICE" "CPU").ToUpperInvariant()
$imageBackend = if ($imageDevice -eq "CPU") { "CPU" } else { $imageDevice }
$imageRuntime = if ($imageDevice -eq "CPU") {
    "CPU / OpenVINO SDXL INT8"
} else {
    "$imageDevice / OpenVINO SDXL INT8"
}

$profileName = "Unknown"
if ($dmrStatus -ne "Running") {
    $profileName = "Degraded"
} elseif ($gpuAcceleration -and $imageDevice -eq "CPU") {
    $profileName = "Hybrid"
} elseif ($gpuAcceleration -and $imageDevice -ne "CPU") {
    $profileName = "GPU Accelerated"
} elseif ($llmBackend -eq "CPU" -and $imageDevice -eq "CPU") {
    $profileName = "CPU / Compatible"
}

$summary = switch ($profileName) {
    "Hybrid" { "HYBRID | $gpuVendor LLM | CPU IMAGE" }
    "GPU Accelerated" { "GPU ACCELERATED | $gpuVendor LLM | $imageDevice IMAGE" }
    "CPU / Compatible" { "CPU | LLM + IMAGE" }
    "Degraded" { "DEGRADED | MODEL RUNNER UNAVAILABLE" }
    default { "RUNTIME BACKEND UNKNOWN" }
}

$profile = [ordered]@{
    schema_version          = 1
    package_version         = "0.2-dev"
    detected_at             = (Get-Date).ToString("s")
    profile                 = $profileName
    summary                 = $summary
    gpu_acceleration        = $gpuAcceleration
    gpu_acceleration_scope  = if ($gpuAcceleration -and $imageDevice -eq "CPU") { "llm" } elseif ($gpuAcceleration) { "llm,image" } else { "none" }
    llm                     = [ordered]@{
        status       = $dmrStatus
        engine       = $llmEngine
        backend      = $llmBackend
        runtime      = $llmRuntime
        accelerator  = $llmAccelerator
        variant      = $llmVariant
    }
    image                   = [ordered]@{
        status       = "Configured"
        engine       = "OpenVINO Model Server"
        backend      = $imageBackend
        runtime      = $imageRuntime
        accelerator  = if ($imageDevice -eq "CPU") { $cpuName } else { "$imageDevice device" }
        model         = "OpenVINO/stable-diffusion-xl-base-1.0-int8-ov"
    }
    note                    = "LLM and image runtimes are detected and reported independently. CPU remains the image fallback in v0.2-dev."
}

$profile | ConvertTo-Json -Depth 8 | Set-Content $runtimePath -Encoding UTF8

Write-Host ""
Write-Host "MediaForge adaptive runtime detection"
Write-Host "-------------------------------------"
Write-Host "Profile:" $profile.profile
Write-Host "LLM:" $profile.llm.runtime "[$($profile.llm.accelerator)]"
Write-Host "Image:" $profile.image.runtime
Write-Host "GPU acceleration:" $profile.gpu_acceleration "(scope: $($profile.gpu_acceleration_scope))"
Write-Host "Runtime report:" $runtimePath
