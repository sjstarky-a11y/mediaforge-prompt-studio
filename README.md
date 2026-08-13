# MediaForge Prompt Studio — Public Test v0.1a CPU

**Fix the prompt → protect the intent → see it before you generate.**

This repository contains the first standalone public-test package for
MediaForge Prompt Studio.

> **License:** Source available for personal, non-commercial evaluation only.
> This is not an open-source project. See [`LICENSE`](LICENSE).

## What is included

- Prompt Doctor
- Fidelity Guard / Intent Lock
- Visual Proof Frame
- Fast Proof 768×768
- Quality Proof 1024×1024
- Single-Frame Extraction
- Model Adapter
- Generic Video
- Runway Gen-4.5
- Veo 3.1
- Kling VIDEO 3.0

## Public Test v0.1a scope

This first package intentionally runs inference on **CPU / Compatible mode**.

The installer already records the detected NVIDIA / AMD / Intel GPU hardware in `runtime/hardware-profile.json`, but GPU acceleration is not enabled in v0.1a. GPU backends will be added as separate public-test milestones without changing the MediaForge UI workflow.

## Requirements

- Windows 11 x64
- Docker Desktop
- Docker Compose
- Docker Model Runner
- Internet connection for the first model downloads
- Enough free RAM and disk space for local AI models

Docker Model Runner must expose host-side TCP access on port `12434`. `install.ps1` attempts to configure this automatically with Docker Desktop's current `--tcp=12434` syntax.

## Install

1. Install and start Docker Desktop.
2. Extract or clone this repository.
3. Open PowerShell in the repository folder.
4. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

The installer will:

1. detect CPU/RAM/GPU hardware,
2. verify Docker,
3. enable Docker Model Runner,
4. pull `ai/qwen2.5:3B-Q4_K_M`,
5. build MediaForge,
6. start OpenVINO Model Server,
7. download/cache the SDXL INT8 model on first use,
8. open the configured app URL (`http://127.0.0.1:18888/` by default).

### First SDXL download

MediaForge Prompt Doctor becomes available as soon as the web app and Qwen are ready. Visual Proof Frame requires a separate, large SDXL INT8 download on the first install. On a slower connection this can take up to an hour.

While SDXL downloads:

- MediaForge itself is running; this is not an installation failure.
- Prompt Doctor can already be used.
- The installer reports elapsed time and the current local cache size.
- The installer window may be closed without stopping the containers.
- Run `.\status.ps1` later to confirm `OVMS ready: True`.

The SDXL files are cached under `data/ovms-models/` and are reused on later starts.

## Ports

Default host ports are configured in `.env`:

```dotenv
MEDIAFORGE_APP_PORT=18888
MEDIAFORGE_OVMS_PORT=8010
```

Edit these values before starting the stack if either port is already occupied. `install.ps1`, `start.ps1`, `status.ps1`, and Docker Compose all use the configured values.

## Start later

```powershell
.\start.ps1
```

## Stop

```powershell
.\stop.ps1
```

## Status / troubleshooting

```powershell
.\status.ps1
```

Useful logs:

```powershell
docker logs mediaforge-prompt-studio
docker logs mediaforge-ovms-sdxl-cpu
```

## Local models

Prompt Doctor:

`ai/qwen2.5:3B-Q4_K_M`

Visual Proof Frame:

`OpenVINO/stable-diffusion-xl-base-1.0-int8-ov`

Downloaded models are cached locally. The OVMS model cache is stored under `data/ovms-models/` and is excluded from Git.

## Privacy

The Public Test package is designed to run locally. Prompt Doctor requests go to the local Docker Model Runner endpoint, and Proof Frame requests go to the local OpenVINO Model Server service.

## Current limitation

This is a **Windows / CPU public-test milestone**, not the final universal installer.

Planned runtime milestones:

- NVIDIA acceleration
- Intel acceleration
- AMD acceleration
- AUTO hardware/backend selection

CPU remains the compatibility fallback.

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

**Public Test v0.1a CPU**

This package is for testing and feedback before wider release.
