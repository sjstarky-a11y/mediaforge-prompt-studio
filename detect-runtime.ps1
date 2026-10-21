$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot "scripts/runtime-common.ps1")
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "runtime") | Out-Null
$status = @(& docker model status 2>&1)
$status | Set-Content (Join-Path $PSScriptRoot "runtime/dmr-status.txt") -Encoding utf8
Invoke-MediaForgeRuntimeTool -ToolArguments @("profile")
