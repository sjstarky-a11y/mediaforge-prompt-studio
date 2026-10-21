# MediaForge Prompt Studio

**Refine the prompt. Protect the intent. Preview the scene locally.**

MediaForge Prompt Studio helps prepare cinematic prompts, check whether an edit
preserves the original idea, and create a local image preview before committing
to a video generation workflow.

The v0.4 development preview brings the Windows and Linux standalone packages
together and adds automatic Intel GPU selection alongside the CPU and NVIDIA
paths. Hardware support is reported per function, with CPU compatibility fallback.

> Source available for personal, non-commercial evaluation under [LICENSE](LICENSE).
> Third-party software and models retain their own [licenses](LICENSES/THIRD_PARTY.md).

## Features

- **Prompt Doctor:** prepare English or Croatian prompts using a local language model.
- **Fidelity Guard / Intent Lock:** review additions and protect the source intent.
- **Fast and Quality Proof:** generate a local scene preview.
- **Hero Frame Set:** optionally create three candidates and select a preferred frame.
- **Model Adapter:** format approved prompts for the supported video services without
  inventing camera moves, dialogue or creative direction.

## Windows and Linux

| Package | Target | Start |
| --- | --- | --- |
| Windows | Windows 11 x64, Docker Desktop with WSL2 and Model Runner | `MediaForge-Windows.cmd` |
| Linux | Ubuntu 24.04 x86_64, Docker Engine, Compose and Model Runner | `./MediaForge-Linux.sh` |

Install Docker and enable Model Runner before first use. The first installation
needs an internet connection and several gigabytes of free space for model caches.
Once downloaded, inference runs locally. Models are not bundled in the archives.

From a source checkout on Windows:

```powershell
.\install.ps1
```

On Linux:

```bash
./install.sh --auto
```

The installer checks available execution environments and selects **NVIDIA, Intel,
or CPU** for Fast/Quality Proof. An Intel selection requires a real GPU calculation;
detecting a card name is insufficient. An unavailable GPU in Auto mode falls back
to CPU. Explicit GPU mode reports an error if its check fails.

Prompt Doctor also uses Intel OpenVINO on a verified Intel profile with at least
16 GiB of reported GPU memory. While its public text model is preparing, requests
use the local Docker Model Runner fallback and report that route. Other profiles
use Model Runner's own backend. Hero Frame Set uses its separate CPU or NVIDIA service. See the [platform support table](docs/PLATFORM-SUPPORT.md) for tested
environments and limitations, and the [Intel guide](docs/INTEL-GPU.md) for setup.

Intel Arc Pro B60 has completed public Windows/WSL2 text and Proof Frame tests.
See the [dated validation note](docs/INTEL-TESTS.md) for timings,
visual findings and the remaining Linux-host checks.

The default application address is `http://127.0.0.1:18888`. Host ports can be
changed in the local `.env` file. Prompt Doctor can become ready while the image
model is still downloading or loading. Use `status.ps1` or `./status.sh` to check.

## Local settings and privacy

Public defaults belong to this standalone product. Private model selections,
workflows and configurations from other projects are not included.

- Keep personal settings in `.env`, `local/` or files ending in `.local.json`.
- Model caches and runtime reports are excluded from Git and release packages.
- `doctor.ps1` or `./doctor.sh` creates an allowlisted report without model names,
  prompts, responses, URLs, local paths or logs.
- Application health and detailed status are local tools and may show local
  settings. Do not copy them wholesale into a public issue.

## Distribution and development

The standalone packages share one Windows/Linux runtime policy under
`app/runtime_tools/`. The [architecture guide](docs/ARCHITECTURE.md) describes the
source and packaging layout. Development changes are reviewed before promotion
to the default branch; a source preview is not automatically a published release.

The [published releases](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/releases)
contain older Windows/Linux packages. The new preview packages are built from this
branch with `scripts/build_release.py --version v0.4-preview`.

Pi SoloHost is a separately managed distribution under `solohost/`; its published
v0.3.1 configuration is preserved in [solohost/v0.3.1](solohost/v0.3.1/).
Use Pi Desktop to manage that installation.

Please use [GitHub Issues](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/issues)
for reproducible public-package bugs and follow [SECURITY.md](SECURITY.md) for
private vulnerability reports.
