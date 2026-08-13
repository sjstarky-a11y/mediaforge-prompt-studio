$ErrorActionPreference = "Stop"

$runtimeDir = Join-Path $PSScriptRoot "runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ramBytes = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$ramGB = [math]::Round($ramBytes / 1GB, 1)

$gpuList = @()
try {
    $gpuList = @(Get-CimInstance Win32_VideoController | ForEach-Object {
        $vendor = "Unknown"
        if ($_.Name -match "NVIDIA") { $vendor = "NVIDIA" }
        elseif ($_.Name -match "AMD|Radeon") { $vendor = "AMD" }
        elseif ($_.Name -match "Intel|Arc") { $vendor = "Intel" }

        [PSCustomObject]@{
            Name       = $_.Name
            Vendor     = $vendor
            Driver     = $_.DriverVersion
            AdapterRAM = if ($_.AdapterRAM) { [math]::Round($_.AdapterRAM / 1GB, 1) } else { $null }
        }
    })
} catch {
    $gpuList = @()
}

$profile = [PSCustomObject]@{
    package_version       = "0.1a-cpu"
    detected_at           = (Get-Date).ToString("s")
    operating_system      = (Get-CimInstance Win32_OperatingSystem).Caption
    cpu                   = $cpu.Name
    logical_processors    = $cpu.NumberOfLogicalProcessors
    ram_gb                = $ramGB
    gpus                  = @($gpuList)
    runtime_selected      = "CPU / Compatible"
    gpu_acceleration      = $false
    note                  = "Public Test v0.1a records GPU hardware now, but intentionally runs inference on CPU. GPU backends are added in later public-test milestones."
}

$profile | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $runtimeDir "hardware-profile.json") -Encoding UTF8

Write-Host ""
Write-Host "MediaForge hardware detection"
Write-Host "-----------------------------"
Write-Host "CPU:" $profile.cpu
Write-Host "RAM:" "$($profile.ram_gb) GB"

if ($gpuList.Count -gt 0) {
    foreach ($gpu in $gpuList) {
        Write-Host "GPU:" $gpu.Name "[$($gpu.Vendor)]"
    }
} else {
    Write-Host "GPU: none detected by Windows CIM"
}

Write-Host ""
Write-Host "Runtime selected for Public Test v0.1a: CPU / Compatible"
Write-Host "Hardware report:" (Join-Path $runtimeDir "hardware-profile.json")
