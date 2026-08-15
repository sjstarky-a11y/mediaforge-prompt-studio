param(
    [ValidateSet("list", "recommend", "install", "select")]
    [string]$Action = "list",
    [string]$Model,
    [switch]$SetDefault,
    [switch]$AcceptModelLicense
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$catalogPath = Join-Path $PSScriptRoot "models\model-catalog.json"
$envPath = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $catalogPath)) {
    throw "Model catalog not found: $catalogPath"
}

$catalog = Get-Content $catalogPath -Raw | ConvertFrom-Json

function Get-InstalledModelIds {
    try {
        $response = Invoke-RestMethod "http://127.0.0.1:12434/models" -TimeoutSec 10
        $items = @()
        if ($response -is [array]) { $items = @($response) }
        elseif ($response.data) { $items = @($response.data) }
        elseif ($response.models) { $items = @($response.models) }

        $ids = foreach ($item in $items) {
            $candidates = @()
            if ($item -is [string]) {
                $candidates += $item
            } else {
                if ($item.id) { $candidates += $item.id }
                if ($item.model) { $candidates += $item.model }
                if ($item.name) { $candidates += $item.name }
                if ($item.tags) { $candidates += @($item.tags) }
            }

            foreach ($candidate in $candidates) {
                $modelId = $candidate.ToString().Trim()
                $modelId = $modelId -replace "^(?:index\.)?docker\.io/", ""
                if ($modelId -match "^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$") {
                    $modelId
                }
            }
        }
        return @($ids | Where-Object { $_ } | Select-Object -Unique)
    } catch {
        Write-Warning "Could not query Docker Model Runner model API: $($_.Exception.Message)"
        return @()
    }
}

function Get-NvidiaVramGB {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return 0 }
    try {
        $values = nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
        $maximumMB = ($values | ForEach-Object { [int](($_ -replace "[^0-9]", "")) } | Measure-Object -Maximum).Maximum
        if ($maximumMB) { return [math]::Round($maximumMB / 1024, 1) }
    } catch {}
    return 0
}

function Set-EnvValue([string]$Name, [string]$Value) {
    if (-not (Test-Path $envPath)) {
        Copy-Item (Join-Path $PSScriptRoot ".env.example") $envPath
    }

    $lines = @(Get-Content $envPath)
    $pattern = "^\s*$([regex]::Escape($Name))\s*="
    $updated = $false
    $result = foreach ($line in $lines) {
        if ($line -match $pattern) {
            if (-not $updated) {
                "$Name=$Value"
                $updated = $true
            }
        } else {
            $line
        }
    }
    if (-not $updated) { $result += "$Name=$Value" }
    Set-Content -Path $envPath -Value $result -Encoding utf8
}

function Find-CatalogModel([string]$ModelId) {
    return $catalog.models | Where-Object { $_.id -eq $ModelId } | Select-Object -First 1
}

$installedIds = Get-InstalledModelIds
$vramGB = Get-NvidiaVramGB

if ($Action -eq "list") {
    Write-Host ""
    Write-Host "MediaForge model catalog"
    Write-Host "------------------------"
    if ($vramGB -gt 0) { Write-Host "Detected NVIDIA VRAM: $vramGB GB" }
    else { Write-Host "Detected NVIDIA VRAM: unavailable / CPU profile" }

    $rows = foreach ($item in $catalog.models) {
        [PSCustomObject]@{
            Installed = $(if ($installedIds -contains $item.id) { "Yes" } else { "No" })
            Profile = $item.profile
            Model = $item.display_name
            VRAM_GB = $item.recommended_vram_gb
            Validation = $item.validation
            ID = $item.id
        }
    }

    $catalogIds = @($catalog.models | ForEach-Object { $_.id })
    $rows += foreach ($modelId in $installedIds) {
        if ($catalogIds -notcontains $modelId) {
            [PSCustomObject]@{
                Installed = "Yes"
                Profile = "Custom"
                Model = ($modelId -replace "^ai/", "")
                VRAM_GB = $null
                Validation = "unverified"
                ID = $modelId
            }
        }
    }
    $rows | Format-Table -AutoSize
    exit 0
}

if ($Action -eq "recommend") {
    if ($vramGB -le 0) {
        Write-Host "Recommended model: ai/qwen2.5:3B-Q4_K_M (CPU / compatible default)"
        exit 0
    }

    $recommended = $catalog.models |
        Where-Object { [double]$_.recommended_vram_gb -le $vramGB } |
        Sort-Object {[double]$_.recommended_vram_gb} -Descending |
        Select-Object -First 1

    if (-not $recommended) {
        $recommended = Find-CatalogModel "ai/qwen2.5:3B-Q4_K_M"
    }

    Write-Host "Recommended profile: $($recommended.profile)"
    Write-Host "Recommended model: $($recommended.id)"
    Write-Host "Validation: $($recommended.validation)"
    Write-Host "This is a recommendation only; no model was downloaded or selected."
    exit 0
}

if (-not $Model) {
    throw "Specify -Model with the full model identifier. Example: -Model 'ai/qwen2.5:7B-Q4_K_M'"
}

if ($Model -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$") {
    throw "Invalid Docker Model Runner model identifier: $Model"
}

$catalogModel = Find-CatalogModel $Model
if (
    $Action -eq "install" -and
    $catalogModel -and
    $catalogModel.license -ne "Apache-2.0" -and
    -not $AcceptModelLicense
) {
    throw "This model uses '$($catalogModel.license)'. Review its terms, then repeat with -AcceptModelLicense."
}

if ($Action -eq "install") {
    Write-Host "Downloading model: $Model"
    docker model pull $Model
    if ($LASTEXITCODE -ne 0) { throw "Could not download model: $Model" }

    if ($SetDefault) {
        Set-EnvValue "MEDIAFORGE_MODEL" $Model
        Write-Host "Default Prompt Doctor model updated in .env: $Model"
        Write-Host "Run .\start.ps1 to apply the new default."
    } else {
        Write-Host "Reload the MediaForge page to show the newly installed model."
    }
    Write-Host "Model installation complete."
    exit 0
}

if ($Action -eq "select") {
    if ($installedIds -notcontains $Model) {
        throw "Model is not installed locally. Run .\manage-models.ps1 -Action install -Model '$Model' first."
    }
    Set-EnvValue "MEDIAFORGE_MODEL" $Model
    Write-Host "Default Prompt Doctor model updated in .env: $Model"
    Write-Host "Run .\start.ps1 to apply the new default."
}
