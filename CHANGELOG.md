# Changelog

All notable public-test changes are documented here.

## [Unreleased] - v0.2-dev Adaptive Runtime Foundation

### Added

- independent LLM and image runtime detection
- Docker Model Runner backend recognition for CPU, CUDA, ROCm, Vulkan, and Metal variants
- host-generated `runtime/runtime-profile.json` with a safe application fallback
- hybrid runtime reporting for NVIDIA/CUDA Prompt Doctor plus CPU/OpenVINO Proof Frame
- dynamic runtime badge in the MediaForge interface
- runtime profile unit tests

### Changed

- hardware inventory no longer claims that all inference is CPU-only
- `/health` now returns readable runtime summary fields plus structured runtime information
- `/runtime` exposes the complete local runtime profile
- `install.ps1`, `start.ps1`, and `status.ps1` refresh the active runtime profile
- Visual Proof Frame remains on the validated OpenVINO SDXL INT8 CPU path

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
