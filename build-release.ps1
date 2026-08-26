param(
    [string]$Version = "v0.3"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to build release packages."
}

docker run --rm `
    --mount "type=bind,source=$PSScriptRoot,target=/work" `
    -w /work `
    python:3.12-slim `
    python scripts/build_release.py --version $Version --output /work/dist

if ($LASTEXITCODE -ne 0) {
    throw "Release packaging failed."
}

Write-Host "Release packages are available in: $(Join-Path $PSScriptRoot 'dist')" -ForegroundColor Green
