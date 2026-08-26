# MediaForge v0.3 — Linux/WSL2 test guide

This development layer adds Ubuntu 24.04 x86_64 host scripts without changing
the existing Windows PowerShell entry points.

## Current validation scope

| Environment | Status |
| --- | --- |
| Windows CPU / OpenVINO | validated |
| Windows GTX 1050 / CUDA low-memory | validated |
| Ubuntu 24.04 WSL2 CPU / OpenVINO | end-to-end validated on Ryzen 9 9950X workstation |
| Native Ubuntu 24.04 CPU/NVIDIA | implementation complete; host confirmation pending |

## WSL2 CPU test beside the Windows installation

Run these commands from the Linux filesystem copy, not `/mnt/c`:

```bash
cd ~/mediaforge-prompt-studio-linux-test
chmod +x *.sh scripts/*.sh tests/*.sh
./install.sh --test-mode --cpu
```

The installer also enables test mode automatically when it sees the existing
Windows `mediaforge-prompt-studio` container.

Test endpoints:

- MediaForge: `http://127.0.0.1:18889`
- Visual Proof health: `http://127.0.0.1:8011/v2/health/ready`

The Windows v0.1a stack remains on ports 18888/8010 with its original container
names. Docker Model Runner and its model cache are shared by Docker Desktop.

The validated WSL2 run completed Prompt Doctor, Fidelity Guard, OpenVINO model
download and a 768x768 Fast Proof. With the image service already ready, the
observed Fast Proof time was under one minute on the Ryzen 9 9950X workstation.

Useful commands:

```bash
./status.sh
./doctor.sh --save
./stop.sh
```

## WSL2 NVIDIA test

On a Windows/WSL2 machine with working Docker GPU access:

```bash
./install.sh --test-mode --auto
```

Use `--nvidia` only when testing that an unavailable or unsupported GPU fails
closed instead of using CPU fallback.

## Native Ubuntu requirements

- Ubuntu 24.04 x86_64
- Docker Engine from Docker's official repository
- Docker Compose plugin
- Docker Model Runner (`docker-model-plugin`)
- NVIDIA driver and Docker GPU access for the optional CUDA path

Docker Model Runner TCP access is enabled by default on port 12434 under Docker
Engine. MediaForge binds its own web and image endpoints to `127.0.0.1`.

## Expected first-run behavior

Prompt Doctor becomes available before the SDXL image model finishes its first
download. Closing the installer does not stop running containers. Run
`./status.sh` to check Visual Proof readiness later.

The installer prepares the local model-cache directories for the service user
inside each image. This avoids Linux bind-mount ownership failures while keeping
the application and image ports bound to localhost.

## Reporting

`./doctor.sh --save` writes `runtime/doctor-report.txt`. It does not copy the
`.env` file or include prompt/model-response bodies, but it does contain selected
runtime settings and recent logs. Review it before sharing.
