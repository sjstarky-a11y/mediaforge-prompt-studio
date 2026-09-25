# Changelog

All notable MediaForge Prompt Studio public-test and SoloHost packaging changes are documented here.

## [0.3.1] - 2026-09-25 — Pi SoloHost

### Installation and setup hardening

- added a dedicated Pi SoloHost v0.3.1 package reference under `solohost/v0.3.1/`
- clarified that Docker Desktop must be started and Docker Engine must be running before Pi Desktop installs or recreates MediaForge
- clarified that Docker Model Runner must be enabled in Docker Desktop Settings > AI
- retained explicit Docker Model Runner model provisioning for reliable clean installations
- kept Visual Proof optional and configurable with 4, 8, 12, or 16 CPU-core limits
- clarified first-run local model download behavior and the approximately 12 GB Visual Proof download
- retained tested runtime images `0.3-solohost.8`; no application runtime rebuild is required for this packaging update
- preserved the repository-root standalone Public Test v0.1a package unchanged

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
