# MediaForge Prompt Studio

**Prepare a video prompt. Review the intent. Preview the scene locally.**

A local workspace for refining cinematic prompts, checking selected changes,
and generating still-image previews before using a separate video generator.

**[Download v0.4 preview](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/releases/tag/v0.4-preview)**
· [Install](docs/QUICKSTART.md) · [Use the app](docs/USER-GUIDE.md) · [Help](docs/TROUBLESHOOTING.md)

## What it does

| Tool | Purpose |
| --- | --- |
| Prompt Doctor | Improve, diagnose, or structure a prompt |
| Fidelity Guard / Intent Lock | Flag selected changes to the original meaning |
| Fast / Quality Proof | Generate a still-image scene preview |
| Hero Frame Set | Optionally compare three image candidates |
| Model Adapter | Format an approved prompt for a video workflow |

Generated text and images need your review. The app does not render video.

## Start

1. Install Docker and enable Docker Model Runner.
2. Download the package for your system and extract it into a new folder.
3. Start the launcher below. First use installs; later use starts the app.

| System | Launcher | Requirements |
| --- | --- | --- |
| Windows | Double-click `MediaForge-Windows.cmd` | Windows 11 x64; Docker Desktop with WSL2 |
| Linux | Run `./MediaForge-Linux.sh` | Ubuntu 24.04 x86_64; Docker Engine, Compose, Model Runner |

Open `http://127.0.0.1:18888`. Internet is needed for the first model downloads;
models are cached locally and are not included in the packages.

## Hardware and limits

- **CPU, NVIDIA and Intel:** automatic runtime selection with CPU compatibility fallback.
- **Intel Arc Pro B60:** text and Fast/Quality Proof verified on Windows/WSL2.
- **Linux:** source/package checks pass; native Intel GPU installation still needs a hardware test.
- **Croatian:** experimental; grammar and meaning errors can escape Fidelity Guard.
- **Hero:** separate CPU/NVIDIA service. macOS packages are not provided in this preview.

See [platform support](docs/PLATFORM-SUPPORT.md) and [recorded Intel tests](docs/INTEL-TESTS.md).

## Documentation

[All guides](docs/README.md) · [Intel setup](docs/INTEL-GPU.md) · [Architecture](docs/ARCHITECTURE.md)
· [Changelog](CHANGELOG.md) · [Report a problem](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/issues/new/choose)

Local settings, model caches, prompts and generated media are excluded from public
packages. See [privacy and diagnostics](docs/TROUBLESHOOTING.md#share-a-report).

Pi SoloHost is managed separately through Pi Desktop:
[distribution guide](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/tree/main/solohost).

**License:** source available for personal, non-commercial evaluation under
[LICENSE](LICENSE). Modification, redistribution and commercial use require the
owner's permission. [Third-party licenses](LICENSES/THIRD_PARTY.md) apply separately.
