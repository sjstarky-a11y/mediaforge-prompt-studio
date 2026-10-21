# Intel GPU setup and validation

The Intel profile uses the public OpenVINO image-generation pipeline already
used by Prompt Studio's CPU path. It does not copy model configurations or
workflows from other projects.

## Windows

- Windows 11 x64, current Intel GPU driver, Docker Desktop with its WSL2 engine.
- Start Docker Desktop and enable Docker Model Runner.
- Run `MediaForge-Windows.cmd install`. Auto detects Intel hardware and checks
  actual GPU execution before choosing the Intel image profile.
- The Windows GPU bridge must expose `/dev/dxg` and `/usr/lib/wsl` to containers.
- `MEDIAFORGE_IMAGE_RUNTIME=intel` requires Intel; `cpu` bypasses GPU checks.

The installer resolves its Intel OpenVINO device independently of Windows CIM
AdapterRAM, which is unreliable for modern GPU memory capacities. Set
`MEDIAFORGE_INTEL_DEVICE=GPU.0` (or another OpenVINO identifier) to choose a device;
`auto` prefers the GPU with the largest reported dedicated memory capacity.

For an isolated test from a separate checkout:

```powershell
.\install.ps1 -TestMode -NoOpen -SkipProofWait
```

This uses port 18889 for the application and 8011 for the image service, plus
8014 for the Intel text service, with distinct container names. Model caches remain in that checkout's `data/` folder.

## Linux

Install the Intel compute driver supported by your GPU and distribution.
The current scope is Ubuntu 24.04 x86_64.

```bash
./install.sh --auto
# Or require Intel and fail if it is unavailable:
./install.sh --intel
```

Native Linux uses `/dev/dri` and records the host render group ID for container
permissions. WSL2 uses `/dev/dxg` and mounts the WSL driver libraries read-only.
Do not use `--privileged` as a workaround for missing GPU permissions.

## Text on Intel

`MEDIAFORGE_TEXT_RUNTIME=auto` enables the separate OpenVINO text service when
the selected Intel image device reports at least 16 GiB. The public standalone
default is `OpenVINO/Qwen2.5-7B-Instruct-int4-ov`; this is a public product default,
not a configuration imported from another project. Its first download is about
4.5 GB, in addition to image caches. The default text port is localhost 8013.

Use `dmr` to keep Docker Model Runner or `intel` to require the Intel text service.
Restart with the normal launcher after changing `.env`. The response displays
its actual provider. While Intel text is downloading, the configured Model Runner
model supplies a local fallback. An explicitly selected Model Runner model stays
on that provider. English Commercial mode uses deterministic local rules.

Intel text and image services can remain loaded together on the validated B60.
This does not guarantee every prompt's accuracy or every 16 GiB device's stability.

## Evidence required before calling a device validated

1. Correct device and memory reported by the runtime.
2. Successful small calculation, with execution devices restricted to GPU.
3. Public image model loaded on that device.
4. A completed Proof Frame through the application's own API.
5. Recorded dimensions, seed, elapsed time and visual inspection.
6. Successful stop/restart and CPU fallback checks.

Detailed local reports stay under `runtime/`. Public notes contain only the
hardware/runtime summary and results from the public test scenario.

Sources: [OpenVINO accelerator setup](https://docs.openvino.ai/2026/model-server/ovms_docs_target_devices.html),
[Intel GPU drivers](https://dgpu-docs.intel.com/driver/client/overview.html),
[Docker Model Runner engines](https://docs.docker.com/ai/model-runner/inference-engines/).
