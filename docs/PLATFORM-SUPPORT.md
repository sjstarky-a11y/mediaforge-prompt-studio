# Platform support

The standalone packages target Windows 11 x64 and Ubuntu 24.04 x86_64.
WSL2 and native Linux are separate validation environments.

| Environment | CPU | NVIDIA images | Intel Fast/Quality Proof |
| --- | --- | --- | --- |
| Windows 11 / Docker Desktop | Previously validated | Previously validated on a low-memory CUDA device | B60 validated; see the dated test note |
| Ubuntu 24.04 / WSL2 | Previously validated | Implementation; hardware confirmation needed | Bridge used by Windows package; Linux-host installation pending |
| Native Ubuntu 24.04 / Docker Engine | Host confirmation needed | Host confirmation needed | Implementation; host confirmation needed |

These statements apply to the public Prompt Studio pipeline. Validation of a
different application or a different model is not transferred to this table.

## Automatic selection

Auto prefers a verified NVIDIA profile, then a verified Intel profile, then CPU.
Explicit CPU mode skips GPU execution checks. Explicit Intel or NVIDIA mode stops
with a clear error if the requested environment cannot run. Auto can fall back to
CPU. GPU presence, successful runtime execution, model readiness and completed
generation are reported separately.

Intel selection currently requires a successful OpenVINO GPU computation and at
least 8 GiB of runtime-reported device memory. This is a conservative initial
policy, not a claim that every Intel GPU with that capacity has been validated.
An unknown memory capacity keeps Auto on CPU.

Prompt Doctor uses a separate OpenVINO text service on a verified Intel profile
with at least 16 GiB of reported memory. This conservative policy reserves room
for text and images; it is validated on B60 only. Other profiles use the actual
Docker Model Runner engine. `MEDIAFORGE_TEXT_RUNTIME=dmr` keeps that route even
on Intel; `auto` selects the eligible Intel service and `intel` requires it.
During Intel text preparation the application explicitly reports the DMR fallback. The optional Hero service continues
to use its CPU or NVIDIA backend. Each component must report its own device.

## Installation

Windows: install Docker Desktop, enable Model Runner, then launch
`MediaForge-Windows.cmd`. Linux: install Docker Engine, Compose and Model Runner,
then run `./MediaForge-Linux.sh`. See the root README for exact requirements.

Containers are bound to localhost. GPU execution checks do not inspect or download
user models. Image models are cached locally when the image service starts.

## Privacy

Local `.env`, `local/`, `*.local.json`, `data/` and `runtime/` are not public source.
Release packaging rejects private configuration paths. The shareable Doctor report
uses an allowlist and excludes model names, prompts, responses, URLs, filesystem
paths and logs. Full health endpoints are for local inspection, not public reports.

Only public Prompt Studio defaults belong in `models/model-catalog.json`. A private
catalog can be selected through `MEDIAFORGE_MODEL_CATALOG_PATH` and kept outside the
repository or in `local/`; it must never be bundled with a public image.

See [Intel B60 validation results](INTEL-TESTS.md) for observed times and limits.
