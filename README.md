# MediaForge Prompt Studio — v0.3 Public Preview

**Fix the prompt → protect the intent → see it before you generate.**

MediaForge v0.3 extends the validated v0.2 local workflow with a complete
Hero Frame Set: three sequential FLUX.2 Klein 4B candidates, visible generation
progress, recovery of an active job after refresh, explicit Hero selection, and
a safe stop-after-current-frame control.

> **License:** Source available for personal, non-commercial evaluation only.
> This is not an open-source project. See [`LICENSE`](LICENSE).

## What is included

- Prompt Doctor
- Fidelity Guard / Intent Lock
- Visual Proof
- Fast Proof: one SDXL scene-confirmation frame at 768×768
- Hero Frame Set: three FLUX.2 Klein 4B options at 512×512 with explicit selection
- visible Hero Frame preparation and frame-by-frame progress
- active Hero job recovery after a browser refresh
- safe stop after the currently generating Hero Frame finishes
- Quality Proof 1024×1024
- Single-Frame Extraction
- Model Adapter
- Generic Video
- Runway Gen-4.5
- Veo 3.1
- Kling VIDEO 3.0

## Model Adapter behavior

Model Adapter v2 is deliberately transparent:

- a concise prompt that already works across services is marked **Compatible as-is**;
- Runway, Veo, and Kling formatting is applied only to explicit camera, motion,
  audio, dialogue, or shot cues already present in the approved prompt;
- the adapter never invents missing creative direction merely to make outputs
  look different;
- the interface reports whether the prompt changed and briefly explains any
  model-specific formatting that was applied.

This keeps the normal workflow simple while preserving truthful model-specific
behavior for richer prompts.

## v0.3 runtime scope

MediaForge now records hardware and active inference backends separately:

- `runtime/hardware-profile.json` contains the Windows or Linux hardware inventory.
- `runtime/runtime-profile.json` contains the active LLM and image runtimes.
- Prompt Doctor follows the Docker Model Runner backend selected by Docker Desktop.
- Prompt Doctor discovers locally installed Docker Model Runner models and allows per-request selection.
- Visual Proof Frame uses **OpenVINO SDXL INT8 / CPU** as the compatibility path.
- Eligible NVIDIA GPUs can use the experimental **CUDA / Diffusers SDXL** image path.
- **Hero Frame Set** uses the optional local **FLUX.2 Klein 4B** service on CPU or NVIDIA CUDA.

The primary interface intentionally reports only the execution mode users need:

```text
LOCAL AI · CPU
LOCAL AI · GPU + CPU
LOCAL AI · GPU
```

Detailed Prompt Doctor and Visual Proof Frame backends remain available in
Developer settings and `runtime/runtime-profile.json`.

CPU-only Model Runner remains the compatibility fallback. Runtime detection is
informational and never prevents the application from returning a health response.

## Requirements

- Windows 11 x64, or Ubuntu 24.04 x86_64 / compatible Linux
- Docker Desktop on Windows/WSL2, or Docker Engine on native Linux
- Docker Compose
- Docker Model Runner
- Internet connection for the first model downloads
- Enough free RAM and disk space for local AI models
- Hero Frame Set: at least 15 GB free disk space; 20 GB recommended

Docker Model Runner must expose host-side TCP access on port `12434`. `install.ps1`
configures Docker Desktop; Docker Engine enables this port by default when the
official `docker-model-plugin` package is installed.

## Windows install

1. Install and start Docker Desktop.
2. Download and extract the complete **Windows x64** release ZIP.
3. Double-click `MediaForge-Windows.cmd`.

The launcher installs MediaForge on first use and starts it on later use. It
opens the application automatically when the local services are ready. CPU or
NVIDIA execution is selected automatically; users do not choose CUDA,
OpenVINO, Compose files, or memory profiles.

Advanced users of the generated package can still run the internal PowerShell
scripts directly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\MediaForge-System\install.ps1"
```

In the source repository these scripts remain at repository root, so developers
use `.\install.ps1`. Generated user packages group technical files inside
`MediaForge-System/`.

The installer will:

1. detect CPU/RAM/GPU hardware,
2. verify Docker,
3. enable Docker Model Runner,
4. detect the active Model Runner backend,
5. select the compatible CPU/OpenVINO or NVIDIA/CUDA image profile,
6. pull the default model configured by `MEDIAFORGE_MODEL`,
7. build MediaForge and the selected image service,
8. download/cache the selected SDXL model on first use,
9. open the configured app URL (`http://127.0.0.1:18888/` by default).

The optional FLUX.2 Hero Frame model is not downloaded during installation.
MediaForge asks for confirmation before its first use and clearly reports the
approximately 12 GB download/loading stage in the interface.

## Linux install

The initial Linux development target is Ubuntu 24.04 x86_64. Docker Desktop
WSL2 integration and native Docker Engine are both recognized.

Download and extract the complete **Linux x86_64** release archive, open a
Terminal in the extracted folder, and run:

```bash
./MediaForge-Linux.sh
```

The official `.tar.gz` release preserves executable Shell permissions. If the
files were copied through a filesystem that removed those permissions, run
`chmod +x MediaForge-Linux.sh` once and start it again.

The Linux installer performs the same automatic CPU/NVIDIA selection as the
Windows installer. Average users do not select CUDA, OpenVINO, offload modes,
or Compose files.

On native Ubuntu/Debian, Docker Model Runner is supplied by Docker's official
`docker-model-plugin` package. On WSL2 it is managed by Docker Desktop.

For an isolated WSL2 development run alongside an existing Windows install:

```bash
./MediaForge-Linux.sh install --test-mode
```

Test mode uses:

```text
App:          http://127.0.0.1:18889
Image API:    http://127.0.0.1:8011
Project:      mediaforge-prompt-studio-linux-test
```

If an existing Windows MediaForge container is visible through Docker Desktop,
the internal installer enables test mode automatically rather than replacing it.

### First SDXL download

MediaForge Prompt Doctor becomes available as soon as the web app and selected
local LLM are ready. Visual Proof Frame requires a separate, large SDXL download
on the first install. On a slower connection this can take up to an hour.

While SDXL downloads:

- MediaForge itself is running; this is not an installation failure.
- Prompt Doctor can already be used.
- The installer reports elapsed time and the current local cache size.
- The installer window may be closed without stopping the containers.
- Run `MediaForge-Windows.cmd status` on Windows or
  `./MediaForge-Linux.sh status` on Linux later to confirm
  `Image service ready: True`.

The application also displays **Preparing Visual Proof model** until the large
image model is ready. This state does not prevent Prompt Doctor use.

The SDXL files are cached under `data/ovms-models/` and are reused on later starts.

For the NVIDIA image profile, model files are cached under `data/huggingface/`.

### Visual Proof modes

- **Fast Proof** generates one quick SDXL scene-confirmation frame.
- **Hero Frame Set** generates three FLUX.2 Klein 4B frames sequentially and
  asks the user to select the strongest option for image-to-video use.
- Only the selected frame receives **HERO FRAME APPROVED** status.
- **Create Shot Pack** is shown as a planned next phase; it does not generate
  establishing, action, or detail shots in this release.

Hero frames use 512×512 because the goal is scene and intention confirmation,
not final delivery resolution. On low-memory NVIDIA systems frames are generated
one at a time with CPU offload. FLUX model files are cached locally and reused.

## Multi-model Prompt Doctor

Qwen 2.5 3B remains the small validated default, but the application is no
longer tied to it. MediaForge reads the local Docker Model Runner model list and
shows installed models in the **Prompt Doctor Model** selector.

List the curated compatibility catalog:

```powershell
.\manage-models.ps1 -Action list
```

Linux equivalent:

```bash
./manage-models.sh list
```

Show a recommendation based on detected NVIDIA VRAM without downloading anything:

```powershell
.\manage-models.ps1 -Action recommend
```

Install and select an additional Apache-2.0 model:

```powershell
.\manage-models.ps1 -Action install -Model "ai/qwen2.5:7B-Q4_K_M" -SetDefault
```

Models governed by separate terms require explicit acknowledgement with
`-AcceptModelLicense`. Custom locally installed DMR models are visible as
**unverified** until they pass MediaForge fidelity tests.

Curated development profiles:

| Profile | Model | Recommended VRAM | Status |
| --- | --- | ---: | --- |
| Light | Qwen 2.5 3B | 4 GB | validated default |
| Light | Gemma 3 QAT 4B | 6 GB | candidate |
| Balanced | Qwen 2.5 7B | 6 GB | candidate |
| Balanced | Qwen 3 8B | 8 GB | candidate |
| Creator | Gemma 3 QAT 12B | 12 GB | candidate |
| Pro | Qwen 3 30B-A3B | 24 GB | candidate |
| Pro | Gemma 3 QAT 27B | 24 GB | candidate |

VRAM values are conservative selection guidance, not hard execution limits.
Docker Model Runner may use system RAM or a different backend depending on the
machine and Docker Desktop configuration.

## NVIDIA image profile

With `MEDIAFORGE_IMAGE_RUNTIME=auto`, the installer selects CUDA image
generation when it detects all of the following:

- NVIDIA GPU available to Windows and Docker;
- compute capability 6.0 or newer;
- at least 4 GB VRAM.

MediaForge does not use a card-name allowlist. It selects an internal profile
from detected capability and memory:

| NVIDIA VRAM | Internal profile | Execution |
| ---: | --- | --- |
| 4 to <6 GB | Low Memory | CUDA with sequential CPU offload |
| 6 to <8 GB | Balanced | CUDA with model CPU offload |
| 8 GB+ | Full | CUDA without model offload |

The internal profile is automatic. Average users see only `CPU`, `GPU + CPU`,
or `GPU`. Unsupported hardware or failed Docker GPU validation safely selects
the CPU/OpenVINO compatibility path.

### GTX 1050 validation

A controlled practical test was completed on a Lenovo 81FV with an Intel
Core i5-8300H, 31.9 GB RAM, and a GeForce GTX 1050 4 GB (compute 6.1).
Both runs used Fast Proof 768×768, 16 steps, seed 42 and the same source prompt.

| Runtime | Total time | Relative result |
| --- | ---: | ---: |
| GTX 1050 / CUDA FP16 Low Memory | 146.50 s | 4.38× faster |
| CPU / OpenVINO SDXL INT8 | 641.87 s | baseline |

The test reduced elapsed time by 77.2%, saving approximately 8 minutes 15
seconds per image. Peak PyTorch VRAM allocation was approximately 1737.5 MB.
This comparison measures practical MediaForge execution; the CUDA FP16 and
OpenVINO INT8 backends are not mathematically identical.

## Ports

Default host ports are configured in `.env`:

```dotenv
MEDIAFORGE_APP_PORT=18888
MEDIAFORGE_IMAGE_PORT=8010
```

Edit these values before starting the stack if either port is already occupied.
The Windows PowerShell scripts, Linux Shell scripts, and Docker Compose all use
the configured values.

## Start later

```powershell
.\start.ps1
```

```bash
./start.sh
```

## Stop

```powershell
.\stop.ps1
```

```bash
./stop.sh
```

## Status / troubleshooting

```powershell
.\status.ps1
```

```bash
./status.sh
```

Create a Linux diagnostic report that does not copy the `.env` file or include
prompt and model-response bodies:

```bash
./doctor.sh --save
```

Useful logs:

```powershell
docker logs mediaforge-prompt-studio
docker logs mediaforge-ovms-sdxl-cpu
docker logs mediaforge-image-cuda
```

## Local models

Prompt Doctor default:

`ai/qwen2.5:3B-Q4_K_M`

Additional installed Docker Model Runner models are discovered automatically.
The curated catalog currently covers Light, Balanced, Creator, and Pro profiles.

Visual Proof Frame compatibility model:

`OpenVINO/stable-diffusion-xl-base-1.0-int8-ov`

Downloaded models are cached locally. The OVMS model cache is stored under
`data/ovms-models/`; the NVIDIA Diffusers cache is stored under
`data/huggingface/`. Both are excluded from Git.

## Privacy

The development package is designed to run locally. Prompt Doctor requests go
to the local Docker Model Runner endpoint, and Proof Frame requests go to the
selected local OpenVINO or NVIDIA/Diffusers image service.

## Current limitation

This is an Adaptive Runtime development milestone, not a final universal installer.
The CPU/OpenVINO path remains the published compatibility baseline. Windows CPU
and GTX 1050 CUDA paths are validated. The Linux Shell layer and its isolated
CPU/OpenVINO workflow have been validated end to end under Ubuntu 24.04 on WSL2,
including Prompt Doctor and Fast Proof. A ready-state 768x768 Fast Proof completed
in under one minute on the Ryzen 9 9950X test workstation. Native Linux host
validation remains pending. The NVIDIA CUDA
image service is development code. Its Low Memory path is validated on a GTX
1050 4 GB, while additional NVIDIA generations and VRAM tiers still require
hardware validation before public release.

Planned runtime milestones:

- validation of NVIDIA CUDA image generation across additional GPU generations and VRAM tiers
- Intel/OpenVINO GPU image profile
- AMD acceleration
- expanded AUTO hardware/backend selection
- native Ubuntu CPU/NVIDIA validation

CPU remains the compatibility fallback.

## Release packages

MediaForge uses platform-specific release packages so average users do not see
scripts intended for another operating system:

| Platform | Release artifact | User entry point |
| --- | --- | --- |
| Windows 11 x64 | `MediaForge-Prompt-Studio-<version>-Windows-x64.zip` | Double-click `MediaForge-Windows.cmd` |
| Ubuntu/Linux x86_64 | `MediaForge-Prompt-Studio-<version>-Linux-x86_64.tar.gz` | Run `./MediaForge-Linux.sh` |

AI models are downloaded locally during installation and are not bundled in
either archive. Every package contains a generated file manifest, and every
release build produces a `SHA256SUMS-<version>.txt` integrity file.

The extracted package root contains only the `START-HERE` guide, one platform
launcher, `README.md`, `LICENSE`, and `MediaForge-System/`. Ordinary users do
not need to open or modify the technical folder.

Maintainers can build both packages from one source checkpoint:

```powershell
.\build-release.ps1 -Version "v0.3"
```

```bash
./build-release.sh v0.3
```

Generated artifacts are written to `dist/`. See
[`PACKAGING-V0.3.md`](PACKAGING-V0.3.md) for the release verification workflow.

## Distribution architecture

```text
                    MediaForge Core
                          |
             +------------+------------+
             |                         |
        Pi SoloHost                GitHub / Docker
             |                         |
        Pi Desktop                Public installer
             |                         |
         localhost                  localhost
```

The same MediaForge core is intended to serve both distribution paths.

## Feedback and security

- Use GitHub Issues for reproducible, non-sensitive public-test bugs.
- Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before submitting feedback.
- Follow [`SECURITY.md`](SECURITY.md) for private vulnerability reports.
- Never publish private prompts, credentials, personal data, or full unrelated logs.

## License

MediaForge Prompt Studio's original code, UI, product logic, documentation, and
branding are copyright © 2026 Siniša Josip Starčević. All rights are reserved.
Viewing the source and running an unmodified copy for personal, non-commercial
evaluation are permitted; modification, redistribution, derivative works,
hosted services, and commercial use require prior written permission. See
[`LICENSE`](LICENSE) for the controlling terms.

## Third-party software and model licenses

Third-party runtimes, packages, and downloaded models retain their own licenses.
See [`LICENSES/THIRD_PARTY.md`](LICENSES/THIRD_PARTY.md).

## Project status

**v0.3 Public Preview — local AI workflow for Windows and Linux**

The public preview is intended for testing and feedback. Windows CPU,
Windows NVIDIA low-memory, and Ubuntu 24.04 WSL2 CPU paths have completed
real-world validation; broader native Linux hardware coverage is still growing.
