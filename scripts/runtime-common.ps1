$MediaForgeAppImage = "mediaforge-prompt-studio:v0.4-preview"
$MediaForgeIntelImage = "mediaforge-intel-runtime:v0.4-preview"
$MediaForgeRuntimeRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-MediaForgeRuntimeTool {
    param([string[]]$ToolArguments)
    docker run --rm --entrypoint python --mount "type=bind,source=$MediaForgeRuntimeRoot,target=/workspace" `
        $MediaForgeAppImage -m runtime_tools.cli @ToolArguments
    if ($LASTEXITCODE -ne 0) { throw "Runtime configuration failed. Review the message above." }
}

function Test-MediaForgeIntelRuntime {
    param([string]$Root)
    $path = Join-Path $Root "runtime/intel-probe.json"
    '{"available":false,"compute_test_passed":false}' | Set-Content $path -Encoding utf8
    $hardware = Get-Content (Join-Path $Root "runtime/hardware-profile.json") -Raw | ConvertFrom-Json
    if (-not @($hardware.gpus | Where-Object { $_.Vendor -eq "Intel" }).Count) { return }
    Write-Host "Checking Intel GPU execution through the Windows WSL GPU bridge..."
    docker build -t $MediaForgeIntelImage (Join-Path $Root "intel_runtime")
    if ($LASTEXITCODE -ne 0) { return }
    $device = Get-EnvValue "MEDIAFORGE_INTEL_DEVICE" "auto"
    $result = docker run --rm --device /dev/dxg --mount type=bind,source=/usr/lib/wsl,target=/usr/lib/wsl,readonly `
        -e "MEDIAFORGE_INTEL_DEVICE=$device" --entrypoint python3 $MediaForgeIntelImage /opt/mediaforge/probe.py
    if ($LASTEXITCODE -eq 0) {
        try {
            $report = $result | ConvertFrom-Json
            if ($report.compute_test_passed -eq $true) {
                $result | Set-Content $path -Encoding utf8
                Write-Host "Intel GPU execution check passed:" $report.name
            }
        } catch { Write-Host "Intel GPU check did not return a valid result; using the compatibility path." }
    } else { Write-Host "Intel GPU is present, but the execution check failed. Auto mode can use CPU." }
}

function Select-MediaForgeRuntime {
    param([string]$Requested, [string]$Root)
    $runtime = Join-Path $Root "runtime"
    $nvidia = @{ available = $false }
    '{"available":false,"compute_test_passed":false}' | Set-Content (Join-Path $runtime "intel-probe.json") -Encoding utf8
    if ($Requested -in @("auto", "nvidia") -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        try {
            # CUDA uses the first visible device; do not report a different card.
            $line = @(& nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader,nounits 2>$null) | Select-Object -First 1
            if ($line -and $LASTEXITCODE -eq 0) {
                $parts = $line -split ","
                docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi -L | Out-Null
                $nvidia = @{ available = ($LASTEXITCODE -eq 0); name = $parts[0].Trim();
                    compute_capability = [double]::Parse($parts[1].Trim(), [Globalization.CultureInfo]::InvariantCulture);
                    memory_bytes = [double]::Parse($parts[2].Trim(), [Globalization.CultureInfo]::InvariantCulture) * 1MB }
            }
        } catch { $nvidia = @{ available = $false } }
    }
    $nvidia | ConvertTo-Json | Set-Content (Join-Path $runtime "nvidia-probe.json") -Encoding utf8
    # Probe Intel too when Auto is used; policy decides among eligible candidates.
    if ($Requested -in @("auto", "intel")) { Test-MediaForgeIntelRuntime -Root $Root }
    Invoke-MediaForgeRuntimeTool -ToolArguments @("select", "--mode", $Requested, "--transport", "wsl")
}
