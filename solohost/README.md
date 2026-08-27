# MediaForge Prompt Studio v0.3 — Pi SoloHost Profiles

This directory is the versioned source for the Pi SoloHost edition of
MediaForge Prompt Studio. It is intentionally kept separate from the standard
Windows/Linux installer: SoloHost uses Docker Model Runner for its fixed text
model and is managed by Pi Desktop.

## Shared behaviour

- Qwen 2.5 3B Q4_K_M is the one validated Prompt Doctor model.
- English and Croatian output are available.
- Fidelity Guard keeps unapproved changes in `REVIEW`.
- A user may explicitly approve a reviewed addition. The current local prompt
  then becomes `INTENT PROTECTED · USER-APPROVED ADDITION` for a Hero request.
- `CONFLICT` is never bypassed by this approval.
- Fast Proof is not included in SoloHost. The interface exposes only the Hero
  Frame Set path.

## Profiles

| Source file | Intended use | Visual service |
| --- | --- | --- |
| `config_options.core.yml` | Default light local Prompt Doctor | Disabled |
| `config_options.hero.yml` | Explicit Hero add-on | FLUX.2 Klein 4B, CPU capped at 8 cores |

The Hero profile starts the small local service but does not download the
model. The first confirmed Hero Frame Set downloads approximately 12 GB; keep
at least 20 GB of free disk space.

## Pi Desktop packaging rule

Pi Desktop expects the active configuration file to be named
`config_options.yml`. A release package must include exactly one of the two
profile files above under that name. Do not present a profile selector in the
Pi Desktop form; it has proven unreliable for this Compose-profile setting.

## Operational rule

Use Pi Desktop to start, stop and configure the SoloHost app. Do not launch a
second manual Compose stack on port `18888` while the Pi-managed app is
running. Pi Node is a separate application and is not modified by either
profile.
