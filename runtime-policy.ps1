function Get-MediaForgeNvidiaImagePolicy {
    param(
        [Parameter(Mandatory = $true)]
        [double]$ComputeCapability,

        [Parameter(Mandatory = $true)]
        [double]$VramGB
    )

    if ($ComputeCapability -lt 6.0) {
        return [PSCustomObject]@{
            Eligible       = $false
            Profile        = "unsupported"
            OffloadMode    = "none"
            DisplayMode    = "CPU"
            Reason         = "CUDA compute capability 6.0 or newer is required."
        }
    }

    if ($VramGB -lt 4.0) {
        return [PSCustomObject]@{
            Eligible       = $false
            Profile        = "unsupported"
            OffloadMode    = "none"
            DisplayMode    = "CPU"
            Reason         = "At least 4 GB of NVIDIA VRAM is required for the SDXL CUDA profile."
        }
    }

    if ($VramGB -lt 6.0) {
        return [PSCustomObject]@{
            Eligible       = $true
            Profile        = "low_memory"
            OffloadMode    = "sequential"
            DisplayMode    = "GPU + CPU"
            Reason         = "Low-memory CUDA profile with sequential CPU offload."
        }
    }

    if ($VramGB -lt 8.0) {
        return [PSCustomObject]@{
            Eligible       = $true
            Profile        = "balanced"
            OffloadMode    = "model"
            DisplayMode    = "GPU + CPU"
            Reason         = "Balanced CUDA profile with model CPU offload."
        }
    }

    return [PSCustomObject]@{
        Eligible       = $true
        Profile        = "full"
        OffloadMode    = "none"
        DisplayMode    = "GPU"
        Reason         = "Full CUDA profile."
    }
}
