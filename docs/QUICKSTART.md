# Quick start

## Before installation

- Windows 11 x64 with Docker Desktop's WSL2 engine, or Ubuntu 24.04 x86_64
  with Docker Engine and Compose.
- Docker Model Runner enabled and reachable. On Windows, enable local TCP access
  in Docker Desktop's AI settings. Installers can provision the fallback text model.
- Internet and enough disk space for several model downloads. Intel text adds
  about 4.5 GB; optional Hero downloads about 12 GB after confirmation.
- Intel or NVIDIA GPU drivers when using acceleration. See [platform support](PLATFORM-SUPPORT.md).

32 GB system RAM is the B60 test configuration, not a measured minimum for every
profile. GPU models, CPU fallback, and other running applications affect memory use.

## Download and install

Open the [v0.4 preview release](https://github.com/sjstarky-a11y/mediaforge-prompt-studio/releases/tag/v0.4-preview)
and choose the Windows ZIP or Linux TAR.GZ under **Assets**. Extract into a new
folder; keep the launcher beside `MediaForge-System/`.

| Windows | Linux |
| --- | --- |
| Start Docker Desktop, then double-click `MediaForge-Windows.cmd` | Start Docker, then run `./MediaForge-Linux.sh` |

First use installs the app and downloads public default models. The first image
can take longer while its model downloads and loads. Open `http://127.0.0.1:18888`.

From a source checkout, use the same launchers at the repository root.

## Everyday controls

Run these from the extracted folder or source root:

| Action | Windows PowerShell | Linux terminal |
| --- | --- | --- |
| Start | `.\MediaForge-Windows.cmd start` | `./MediaForge-Linux.sh start` |
| Status | `.\MediaForge-Windows.cmd status` | `./MediaForge-Linux.sh status` |
| Stop | `.\MediaForge-Windows.cmd stop` | `./MediaForge-Linux.sh stop` |
| Shareable report | `.\MediaForge-Windows.cmd doctor` | `./MediaForge-Linux.sh doctor` |

Closing the browser leaves services running. **Stop** ends this installation's
services and unloads its Intel image/text models. Docker Model Runner is shared
with other apps and may keep its last model briefly; see [memory help](TROUBLESHOOTING.md#memory-after-stopping).

## Local settings and updates

In a package, settings are in `MediaForge-System/.env`; in a source checkout,
they are in `.env`. Stop before editing, then start again.

| Setting | Values / purpose |
| --- | --- |
| `MEDIAFORGE_IMAGE_RUNTIME` | `auto`, `cpu`, `nvidia`, `intel` |
| `MEDIAFORGE_TEXT_RUNTIME` | `auto`, `dmr`, `intel` |
| `MEDIAFORGE_APP_PORT` | Local app port; default `18888` |

Auto verifies the available runtime before selecting it. Forced GPU mode fails
clearly if unavailable. Intel text requires an eligible Intel profile with at least
16 GiB of reported GPU memory; see [Intel setup](INTEL-GPU.md).

For updates, stop the old copy, extract the new package into a separate folder,
and transfer only settings you understand. Keep existing caches as a backup;
copying `data/` into the new system folder avoids repeating matching downloads.
Run one installation at a time unless you deliberately assign separate ports/names.
