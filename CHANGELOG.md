# Changelog

All notable public-test changes are documented here.

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
