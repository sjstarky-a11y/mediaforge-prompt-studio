# Maintenance

## Source layout

| Path | Purpose |
| --- | --- |
| `app/` | Standalone UI, API, text routing and shared runtime policy |
| `intel_runtime/`, `image_cuda/`, `image_flux/` | Inference services |
| `scripts/` | Host helpers, source synchronization and package builders |
| `tests/`, `.github/` | Checks and issue templates |
| `solohost/` | Separately managed Pi distribution |
| `docs/archive/` | Historical version notes |
| `data/`, `local/`, `.env`, runtime reports | Local files excluded from public distribution |

Windows/Linux share the policy under `app/runtime_tools/`. Review changes through
a pull request before merging to `main`. Preserve the SoloHost snapshot separately.

## Validate and package

For maintainers with Python 3.12 and application dependencies installed:

```text
python -m pip install -r requirements.txt
python scripts/sync_shared.py --check
python scripts/build_manifest.py
python -m unittest discover -s tests -v
python scripts/build_release.py --check
python scripts/build_release.py --version v0.4-preview
```

Outputs go to `dist/`: Windows ZIP, Linux TAR.GZ and SHA-256 checksums. The builder
uses explicit public sources, excludes private paths, verifies archive contents,
and checks reproducibility. Models are downloaded separately.

The extracted package root holds the launcher, START-HERE, README, LICENSE and
`MediaForge-System/`. Build from the reviewed commit and attach all three artifacts
to a GitHub preview release. Publish recorded hardware results and validation limits;
source/package checks alone do not establish GPU support on a new host.
