# MediaForge v0.2-dev — Adaptive Runtime Foundation

## Goal

Report what actually runs each MediaForge workload instead of assigning one
machine-wide CPU/GPU label.

## Runtime model

| Workload | Engine | Current selectable backend |
| --- | --- | --- |
| Prompt Doctor | Docker Model Runner / llama.cpp | CPU or NVIDIA CUDA on validated Windows systems |
| Visual Proof Frame | OpenVINO Model Server / SDXL INT8 | CPU |

When Prompt Doctor uses CUDA while Proof Frame uses CPU, the runtime profile is
`Hybrid` and the UI displays `HYBRID · NVIDIA LLM · CPU IMAGE`.

## Generated reports

- `runtime/hardware-profile.json`: hardware facts only
- `runtime/runtime-profile.json`: active backend facts only

Both reports are local runtime files and are excluded from Git.

## Refresh behavior

`install.ps1`, `start.ps1`, and `status.ps1` invoke `detect-runtime.ps1`.
Run it manually after changing GPU-backed inference in Docker Desktop:

```powershell
.\detect-runtime.ps1
```

Refresh the MediaForge page afterward to update the runtime badge.

## Validated baseline

- Windows 11 Pro
- Intel Core i5-8300H, 32 GB RAM
- NVIDIA GeForce GTX 1050 4 GB
- Docker Model Runner `llama.cpp` CUDA
- Qwen 2.5 3B Q4_K_M
- OpenVINO SDXL INT8 on CPU

Observed warm Prompt Doctor response: 1.31 seconds. Observed Proof Frame time:
approximately 6–8 minutes on the i5-8300H CPU.

## Not included yet

- SDXL generation on the GTX 1050
- Intel GPU image execution
- AMD GPU execution
- automatic mutation of Docker Desktop GPU settings
- performance-based backend selection
