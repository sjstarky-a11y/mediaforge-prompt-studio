# Application and distribution structure

`app/` is the standalone product source. `app/runtime_tools/` owns the shared
Windows/Linux runtime selection, reporting and privacy-safe diagnostics.

Windows PowerShell and Linux shell scripts collect host-specific evidence. The
same Python policy runs in the application container on either platform, so
Windows users do not need a separate Python installation.

`intel_runtime/` supplies the pinned OpenVINO GPU image and model-free GPU probe.
CPU and NVIDIA profiles retain their existing inference services. Intel Compose
profiles extend the common application and CPU image-service definition and
provide the platform-specific GPU devices. Fast/Quality Proof, Prompt Doctor and
Hero generation are independent capabilities.

`app/text_backend.py` routes text independently between OpenVINO and Docker Model
Runner, including model readiness and an explicitly reported preparation fallback.
`app/system_api.py` keeps health and readiness endpoints separate from prompt logic.

`solohost/` is the independently managed Pi distribution. `solohost/v0.3.1/`
preserves its published configuration snapshot. Its startup rules remain under
Pi Desktop. Shared pure application modules have one authoritative source in
`app/` and are checked with `scripts/sync_shared.py --check`. Distribution-specific
UI and service behaviour remain explicit profiles pending further consolidation.

`scripts/build_release.py` builds reproducible Windows and Linux archives using
an explicit source list. `runtime/PACKAGE-MANIFEST.json` describes public sources,
not local configurations. `local/`, `.env`, runtime reports, model caches and test
media must not be committed or included in public artifacts.

User guides are indexed in [docs/README](README.md). Historical release notes live
under `docs/archive/`; current packages include the active user and maintenance guides.
