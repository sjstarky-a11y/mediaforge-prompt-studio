# Intel B60 public pipeline validation — 22 October 2026

This note records only the public standalone Prompt Studio test scenario.
No model configuration, prompt or workflow from a private project was used.

## Environment and scope

- Windows 11 x64, Docker Desktop WSL2 engine.
- Intel Arc Pro B60, marketed 24 GB; OpenVINO reported 25,055,051,776 bytes.
- Intel driver 32.0.101.8976.
- Pinned OpenVINO Model Server 2026.4.1 GPU runtime.
- Text engine: separate Intel OpenVINO GPU service, with Docker Model Runner CPU fallback.
- An isolated checkout and separate localhost ports/container names were used.

## Results

| Check | Observed result |
| --- | --- |
| Auto device selection | Intel selected after a successful GPU calculation |
| Actual execution device | GPU.0, without AUTO or CPU execution fallback |
| Fast Proof | 768 × 768, 16 steps, seed 42; 2.55 seconds with the model ready |
| Quality Proof | 1024 × 1024, 16 steps, seed 42; 4.48 seconds with the model ready |
| Stop/restart and cached generation | Successful; Fast Proof took 6.15 seconds after restart and returned identical PNG bytes |
| Explicit CPU compatibility mode | Same public Fast Proof scenario completed in 38.53 seconds |
| Intel text, English | 2.26 seconds; actual provider reported Intel GPU / OpenVINO |
| Intel text, Croatian | 1.49 seconds; final prompt in Croatian, diagnosis remained English in this sample |
| Text after full stop/restart | 2.41 seconds; diagnosis and prompt both in Croatian after strengthened instruction |
| Automated checks | 93 passed on native Windows and in a Linux container; reproducible archives passed on both |
| Text and image loaded together | Successful; Fast Proof completed in 6.14 seconds |
| Text preparation fallback | DMR completed a request while the Intel model downloaded; actual fallback reported |
| Auto with an unavailable GPU identifier | Fell back to CPU; explicit Intel mode failed before changing the stack |
| Shareable diagnostic report | Excluded models, prompts, local paths, URLs and logs |

The public scene describes a single red ceramic cup on a wooden table beside a
window in soft daylight. Visual inspection confirmed the main subject and setting
after fixing an existing scene-extraction bug that replaced unknown objects with
generic placeholders. The 1024-pixel image added unrequested decorative objects
and produced imperfect cup geometry. A completed render does not establish full
prompt fidelity or general image quality.

Text content inspection also found unrequested composition/position additions,
an earlier cup-to-bowl substitution, and awkward Croatian wording. Narrow common
object and time-of-day checks were added, but Fidelity Guard is not a complete
semantic verifier. The language instruction was strengthened after the mixed
language diagnosis. The subsequent Croatian sample used Croatian throughout, but
contained grammatically poor text and an incorrect verb that changed the lighting
meaning. The guard did not catch that semantic error. Hardware execution is
confirmed; Croatian output is experimental and requires manual review.

These timings are observations from individual requests, not a controlled
cross-backend benchmark. They exclude the initial download and model preparation.

## Validation limits

The native Ubuntu host path still needs its own driver/container/inference test.
The Linux sources and package checks ran successfully in a Linux container. The
installed Ubuntu WSL distribution had no running Docker socket exposed, so no
Linux-host installation is claimed from that environment.

Other Intel devices, integrated Intel graphics and Intel Hero generation are not validated by this test. Existing NVIDIA support still
needs confirmation on additional devices; no NVIDIA card was present in this run.
