# MediaForge v0.2-dev — NVIDIA + Multi-Model Runtime

## Goal

Report what actually runs each MediaForge workload instead of assigning one
machine-wide CPU/GPU label.

## Runtime model

| Workload | Engine | Current selectable backend |
| --- | --- | --- |
| Prompt Doctor | Docker Model Runner / llama.cpp | CPU or NVIDIA CUDA; dynamic local model selection |
| Visual Proof Frame | OpenVINO Model Server / SDXL INT8 | CPU compatibility profile |
| Visual Proof Frame | Diffusers / SDXL FP16 | NVIDIA CUDA profiles for compute 6.0+, 4 GB+ VRAM |

Detailed component runtimes remain available in Developer settings and the
runtime report. The primary UI intentionally shows only `CPU`, `GPU + CPU`, or
`GPU`.

## Generated reports

- `runtime/hardware-profile.json`: hardware facts only
- `runtime/runtime-profile.json`: active backend facts only

Both reports are local runtime files and are excluded from Git.

## Refresh behavior

Windows entry points invoke `detect-runtime.ps1`. Linux/WSL2 entry points invoke
`detect-runtime.sh`, which writes the same schema through
`scripts/linux_profile.py`.
Run it manually after changing GPU-backed inference in Docker Desktop:

```powershell
.\detect-runtime.ps1
```

Refresh the MediaForge page afterward to update the runtime badge.

## Linux and WSL2 host layer

Linux entry points:

- `install.sh`: automatic CPU/NVIDIA selection and first-time setup
- `start.sh`, `stop.sh`, `status.sh`: lifecycle management
- `doctor.sh`: non-sensitive diagnostics
- `detect-hardware.sh`, `detect-runtime.sh`: host/runtime reports
- `manage-models.sh`: curated and custom Docker Model Runner models

`install.sh --test-mode` isolates the WSL2 development stack from an existing
Windows installation with separate project/container names and ports 18889/8011.
The isolation is implemented through environment interpolation in the existing
CPU and NVIDIA Compose files, so production and test paths use identical images.

Current Linux validation levels:

| Environment | CPU/OpenVINO | NVIDIA/CUDA | Host installation |
| --- | --- | --- | --- |
| Ubuntu 24.04 WSL2 workstation | end-to-end validated; ready-state Fast Proof under 1 minute | no NVIDIA hardware | Docker Desktop integration validated |
| Ubuntu 24.04 WSL2 GTX 1050 laptop | available for test | low-memory test target | Docker Desktop integration |
| Native Ubuntu 24.04 | pending external confirmation | pending external confirmation | Docker Engine + docker-model-plugin |

## Model architecture

- `/api/models` discovers models from Docker Model Runner.
- Qwen 2.5 3B is the validated default, not a hard dependency.
- The UI can switch between locally installed models without rebuilding the app.
- `models/model-catalog.json` stores compatibility metadata and VRAM guidance.
- `manage-models.ps1` handles catalog listing, recommendation, installation, and default selection.
- Candidate and custom models remain explicitly marked unverified until fidelity testing is complete.

## Model Adapter v2

The adapter endpoint keeps the approved creative prompt locked and now reports
whether a target-specific transformation actually occurred:

- `changed: false` means the approved prompt is already compatible with the
  selected video service;
- `changed: true` means deterministic formatting was applied to explicit cues;
- `adaptation_notes` explains the applied formatting or why no rewrite was
  needed.

Runway camera direction, Veo audio/dialogue cues, and Kling shot/audio cues are
handled only when already present. Missing motion, sound, dialogue, shots,
characters, or scene details are never invented to force different outputs.

## Image runtime selection

`install.ps1` writes the resolved compose profile to `.env`:

- `docker-compose.yml` for CPU/OpenVINO;
- `docker-compose.nvidia.yml` for CUDA/Diffusers.

The CUDA image service exposes the same local OpenAI-compatible image endpoint
shape used by the CPU service, so Prompt Doctor and Fidelity Guard remain
backend-independent.

Automatic internal profiles:

| NVIDIA VRAM | Internal profile | Offload | Primary UI |
| ---: | --- | --- | --- |
| 4 to <6 GB | `low_memory` | sequential CPU offload | `GPU + CPU` |
| 6 to <8 GB | `balanced` | model CPU offload | `GPU + CPU` |
| 8 GB+ | `full` | none | `GPU` when both workloads use GPU |

These are capability tiers, not card-name allowlists. CUDA compute capability
6.0 or newer and successful Docker GPU access are also required.

## Validated baseline

- Windows 11 Pro
- Intel Core i5-8300H, 32 GB RAM
- NVIDIA GeForce GTX 1050 4 GB
- Docker Model Runner `llama.cpp` CUDA
- Qwen 2.5 3B Q4_K_M
- OpenVINO SDXL INT8 on CPU

Observed warm Prompt Doctor response: 1.31 seconds.

Controlled Fast Proof test at 768×768, 16 steps and seed 42:

| Runtime | Total time |
| --- | ---: |
| GTX 1050 4 GB / CUDA FP16 with sequential offload | 146.50 s |
| i5-8300H / OpenVINO SDXL INT8 | 641.87 s |

The GTX 1050 completed the practical test 4.38× faster, reducing elapsed time
by 77.2%. Peak PyTorch VRAM allocation was approximately 1737.5 MB. Because the
CPU and CUDA paths use different precision and execution engines, this is a
practical workflow comparison rather than bit-identical inference.

## Fast Proof frozen baseline

Controlled WSL/OpenVINO testing changed one variable at a time across prompt
structure, negative prompt, inference steps, guidance, resolution, and RNG seed.
The selected Fast Proof baseline is:

- the concise source-derived single-frame prompt, without a second constraint-expansion pass;
- the original general negative prompt;
- 768x768 output;
- 16 inference steps;
- server-default guidance (observed to match an explicit value of 5.0);
- seed 42 for the first frame, with Regenerate advancing the seed.

The Visual Proof Frame remains a user-confirmation layer. SDXL output varies by
seed, so Approve Scene and Regenerate remain intentional parts of the workflow.

## Still requiring hardware validation

- CUDA/Diffusers SDXL across additional NVIDIA generations and VRAM tiers
- fallback behavior after CUDA out-of-memory conditions
- quality and timing comparison against OpenVINO CPU
- additional Prompt Doctor models beyond the validated Qwen 2.5 3B baseline
- automatic recovery after a CUDA service fails after installation
- Intel GPU image execution
- AMD GPU execution
- automatic mutation of Docker Desktop GPU settings
- performance-based backend selection
