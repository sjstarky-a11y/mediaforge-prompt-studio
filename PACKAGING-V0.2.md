# MediaForge v0.2 release packaging

MediaForge publishes separate Windows and Linux packages from the same tested
source checkpoint. The release builder keeps the first-run experience simple
while preserving verifiable package contents.

## Generated artifacts

| Platform | Artifact | First action |
| --- | --- | --- |
| Windows 11 x64 | `MediaForge-Prompt-Studio-<version>-Windows-x64.zip` | Extract, then double-click `MediaForge-Windows.cmd` |
| Ubuntu/Linux x86_64 | `MediaForge-Prompt-Studio-<version>-Linux-x86_64.tar.gz` | Extract, then run `./MediaForge-Linux.sh` |

The builder also writes `SHA256SUMS-<version>.txt` beside the archives.

Models and runtime caches are never bundled. The installers download the
selected local models after automatic CPU/NVIDIA detection.

Each extracted package has a deliberately small user-facing root: the
`START-HERE` guide, one launcher, `README.md`, `LICENSE`, and the
`MediaForge-System/` folder. Installation scripts, Compose definitions, app
code, and runtime metadata stay inside `MediaForge-System/`.

## Build both packages

Windows maintainer command:

```powershell
.\build-release.ps1 -Version "v0.2-dev"
```

Linux maintainer command:

```bash
./build-release.sh v0.2-dev
```

The output directory is `dist/` by default.

## Packaging guarantees

`scripts/build_release.py` uses explicit platform allowlists and performs the
following checks before accepting an archive:

- includes only the launcher and management scripts for the target platform;
- excludes `.git`, `.env`, model caches, runtime profiles, logs, tests, and
  development-only packaging tools;
- creates exactly one top-level application folder;
- writes `RELEASE-INFO.json` and a per-file
  `runtime/PACKAGE-MANIFEST.json` with sizes and SHA-256 hashes;
- extracts and verifies each completed archive;
- confirms that Linux `MediaForge-Linux.sh` and the internal `install.sh` are executable;
- fixes archive timestamps, ownership, ordering, and permissions so identical
  source checkpoints produce byte-identical packages.

Run the full reproducibility check without retaining output artifacts:

```bash
python3 scripts/build_release.py --check
```

## Release checklist

1. Confirm the intended Git branch and a clean working tree.
2. Run all unit, Shell, PowerShell, JavaScript, and Compose validations.
3. Run `python3 scripts/build_manifest.py --check`.
4. Run `python3 scripts/build_release.py --check`.
5. Build the final artifacts with the intended version.
6. Verify each published file against `SHA256SUMS-<version>.txt`.
7. Test installation from a newly extracted archive, not from the development
   repository or an existing runtime cache.

GitHub's automatically generated **Source code (zip)** and **Source code
(tar.gz)** archives are repository snapshots. They are not MediaForge
installation packages. Users should download the platform-specific asset from
the release page.
