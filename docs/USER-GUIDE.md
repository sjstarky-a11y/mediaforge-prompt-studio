# User guide

## A simple workflow

1. Enter a short description with a subject, action, setting and any required camera direction.
2. Choose the aspect ratio, output language and mode, then generate.
3. Read the result and Fidelity Guard findings. Correct unwanted changes before continuing.
4. Generate a Fast or Quality Proof to inspect the scene; regenerate or approve it.
5. Use Model Adapter to copy the approved prompt into your separate video workflow.

Example: “A red ceramic cup stands on a wooden table beside a window in soft daylight.”

## Modes

| Mode | Use it for |
| --- | --- |
| Improve | A concise refinement close to the original |
| Diagnose | Identify ambiguity or contradictions |
| Cinematic | Add technical presentation while preserving explicit facts |
| Ad | Product/commercial presentation |
| Shots | Break an idea into ordered shots |

English is the reference workflow. Croatian output is experimental: check grammar,
objects, actions and meaning. Fixed section headings remain in English. English
Ad mode uses local rules; other text requests use the selected local model.

## Images and approval

Fast Proof uses 768 × 768; Quality Proof uses 1024 × 1024. These are still-image
checks and can contain extra objects, geometry errors or incomplete actions.
A longer action is represented by one frame, not an animation.

Hero Frame Set is optional. It requests confirmation before its first large model
download, generates three candidates, and lets you select a preferred frame.
Intel text/Proof acceleration does not enable Intel Hero generation.

Approval records your choice. Fidelity Guard checks selected patterns; a protected
status does not guarantee that every semantic or visual change was detected.

## Which device is working?

The runtime indicator distinguishes text and image services. Each text result
reports its actual provider. During Intel text preparation, requests can use the
local Model Runner fallback. A Model Runner model you explicitly select stays on
that provider. Use the launcher **status** action for readiness details.

For startup, stop and settings, see [Quick start](QUICKSTART.md).
