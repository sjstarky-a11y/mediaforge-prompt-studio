$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
. (Join-Path $PSScriptRoot "scripts/runtime-common.ps1")
Invoke-MediaForgeRuntimeTool -ToolArguments @("diagnostics")
Write-Host "Shareable report saved under runtime/doctor-report.json. Model names, prompts, paths and logs are excluded."
