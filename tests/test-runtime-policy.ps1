$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $repoRoot "runtime-policy.ps1")

function Assert-Equal($Actual, $Expected, $Message) {
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', received '$Actual'."
    }
}

$unsupported = Get-MediaForgeNvidiaImagePolicy -ComputeCapability 5.2 -VramGB 4
Assert-Equal $unsupported.Eligible $false "Legacy compute capability must fall back to CPU."

$lowMemory = Get-MediaForgeNvidiaImagePolicy -ComputeCapability 6.1 -VramGB 4
Assert-Equal $lowMemory.Eligible $true "GTX 1050-class hardware must be eligible."
Assert-Equal $lowMemory.Profile "low_memory" "A 4 GB GPU must use the low-memory profile."
Assert-Equal $lowMemory.OffloadMode "sequential" "The low-memory profile must use sequential offload."
Assert-Equal $lowMemory.DisplayMode "GPU + CPU" "Low-memory execution must be presented simply."

$balanced = Get-MediaForgeNvidiaImagePolicy -ComputeCapability 7.5 -VramGB 6
Assert-Equal $balanced.Profile "balanced" "A 6 GB GPU must use the balanced profile."
Assert-Equal $balanced.OffloadMode "model" "The balanced profile must use model offload."

$full = Get-MediaForgeNvidiaImagePolicy -ComputeCapability 8.6 -VramGB 8
Assert-Equal $full.Profile "full" "An 8 GB GPU must use the full profile."
Assert-Equal $full.OffloadMode "none" "The full profile must keep the pipeline on GPU."
Assert-Equal $full.DisplayMode "GPU" "Full GPU execution must be presented simply."

Write-Host "NVIDIA runtime policy tests passed."
