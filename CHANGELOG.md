# Changelog

All notable public-test changes are documented here.

## [Unreleased] - v0.3 Public Preview

### Added

- independent LLM and image runtime detection
- Docker Model Runner backend recognition for CPU, CUDA, ROCm, Vulkan, and Metal variants
- host-generated `runtime/runtime-profile.json` with a safe application fallback
- hybrid runtime reporting for NVIDIA/CUDA Prompt Doctor plus CPU/OpenVINO Proof Frame
- dynamic runtime badge in the MediaForge interface
- runtime profile unit tests
- dynamic discovery and selection of locally installed Docker Model Runner models
- curated Light, Balanced, Creator, and Pro model catalog
- `manage-models.ps1` for model recommendations, installation, and default selection
- backend-neutral Visual Proof Frame image API configuration
- experimental NVIDIA CUDA / Diffusers SDXL service and Compose profile
- automatic NVIDIA image eligibility checks with CPU fallback
- deterministic detection of unrequested mood, narrative, and lighting inventions from weaker models
- Improve-mode structure validation for 1–4 diagnosis bullets, allowing concise one-bullet diagnoses without weakening intent protection
- automatic NVIDIA Low Memory, Balanced, and Full image profiles
- GTX 1050 4 GB CUDA/Diffusers Fast Proof validation
- controlled Visual Proof prompt, step, guidance, resolution, and seed validation
- simple user-facing `CPU`, `GPU + CPU`, and `GPU` execution labels
- automatic correction of lighting-only Improve reviews before final fidelity approval
- Ubuntu 24.04/WSL2 Shell entry points for install, start, stop, status, diagnostics, and model management
- Linux hardware and adaptive runtime profile generation with the existing JSON schema
- isolated WSL2 test mode using ports 18889/8011 and independent container names
- Linux NVIDIA eligibility policy matching the validated Windows low-memory tiers
- Linux runtime unit tests and Shell syntax validation in GitHub Actions
- Linux model-cache permissions prepared for non-matching container user IDs
- experimental Proof prompt expansions were reverted to the validated checkpoint before controlled parameter testing
- WSL runtime reporting now counts installed models through the Docker CLI
- Ubuntu 24.04 WSL2 CPU/OpenVINO end-to-end validation, including a ready-state 768x768 Fast Proof completed in under one minute on the Ryzen 9 9950X workstation
- transparent Model Adapter v2 status for prompts that are already compatible with the selected video service
- deterministic profile tests for Runway Gen-4.5, Veo 3.1, and Kling VIDEO 3.0
- one-click `MediaForge-Windows.cmd` launcher that installs on first use and starts on later use
- deterministic Windows x64 ZIP and Linux x86_64 tar.gz release packaging
- platform-specific package contents, embedded file manifests, and SHA256SUMS output
- release packaging tests that verify reproducibility, private-file exclusion, and Linux executable permissions
- platform-neutral Windows ZIP and Linux gzip output that remains byte-identical across supported build environments
- platform-neutral source manifest hashing for Windows CRLF and Linux LF checkouts
- friendly Visual Proof model download/loading status with automatic readiness checks
- simplified release roots with technical runtime files grouped under `MediaForge-System/`
- one-command `MediaForge-Linux.sh` launcher for generated Linux packages
- optional FLUX.2 Klein 4B Hero Frame service for CPU and NVIDIA CUDA
- Hero Frame Set workflow with three sequential 512×512 candidates and explicit selection
- visible first-use FLUX download/loading state and approximately 12 GB confirmation
- approved Hero Frame status plus a clearly marked planned Shot Pack phase
- persistent Hero Frame job status so an active set is restored after refresh
- visible preparation and frame-by-frame progress for Hero Frame generation
- safe stop-after-current-frame control that preserves completed candidates

### Changed

- hardware inventory no longer claims that all inference is CPU-only
- `/health` now returns readable runtime summary fields plus structured runtime information
- `/runtime` exposes the complete local runtime profile
- `install.ps1`, `start.ps1`, and `status.ps1` refresh the active runtime profile
- Visual Proof Frame automatically uses NVIDIA CUDA on compatible compute 6.0+, 4 GB+ hardware and otherwise uses OpenVINO SDXL INT8 CPU
- Qwen 2.5 3B remains the default but is no longer hardcoded per request
- Compose project and container names are configurable without changing Windows defaults
- Visual Proof Frame now sends the original concise single-frame extraction directly to SDXL; the experimental constraint-expansion layer is no longer active
- Fast Proof is frozen at 768x768, 16 steps, server-default guidance, and initial seed 42 after controlled WSL/OpenVINO testing
- Model Adapter now reports `changed` and `adaptation_notes`, applying target-specific formatting only to explicit camera, audio, dialogue, or shot cues
- average Windows users no longer need to type PowerShell execution-policy commands
- the Linux release archive preserves `./install.sh` executable permissions

## [0.1a] - 2026-08-13

### Included

- Prompt Doctor with Improve, Diagnose, Cinematic, Commercial, and Shot List modes
- Fidelity Guard / Intent Lock
- Visual Proof Frame with Fast and Quality profiles
- deterministic single-frame extraction
- Model Adapter profiles for Generic Video, Runway Gen-4.5, Veo 3.1, and Kling VIDEO 3.0
- Windows hardware detection with CPU-compatible runtime selection

### Packaging improvements

- corrected Docker Model Runner TCP flag syntax
- clarified first-run SDXL download progress and readiness
- made application and OVMS host ports configurable through `.env`
- corrected single-GPU console detection
- corrected hardware-profile package version
- removed duplicate directory nesting from the release archive

### Runtime scope

- Windows 11
- CPU / Compatible inference
- Qwen 2.5 3B through Docker Model Runner
- SDXL INT8 through OpenVINO Model Server

GPU acceleration is not enabled in this milestone.
