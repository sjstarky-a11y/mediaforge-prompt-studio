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

## Public package

`config_options.yml` is the single public SoloHost configurator. It installs
Core by default and exposes an explicit optional `Visual Proof` choice.

The configurator deliberately does not expose `COMPOSE_PROFILES` directly.
Pi Desktop previously treated that reserved field as required even when Core
was selected. Instead, the package keeps an internal `enabled` profile active
and assigns the Hero service to it only when
`MEDIAFORGE_VISUAL_PROOF_MODE=enabled`.

This gives the public package the intended behaviour:

- Core does not pull or start the FLUX service.
- Enabling Visual Proof pulls the separate public image.
- Users can generate one Proof Frame or a three-image Hero Frame Set with the
  same FLUX.2 Klein 4B service.
- The FLUX model is downloaded only after the first confirmed image request.
- CPU capacity is selected independently: 4, 8, 12 or 16 cores.
- The public Compose file is pull-only and never depends on local source or a
  Docker build context.

## Source profiles

| Source file | Intended use | Visual service |
| --- | --- | --- |
| `config_options.core.yml` | Default light local Prompt Doctor | Disabled |
| `config_options.hero.yml` | Explicit Hero add-on | FLUX.2 Klein 4B, CPU capped at 8 cores |
| `config_options.yml` | One public app with user-selectable Hero | Disabled by default; 4/8/12/16 CPU choice |

The Hero profile starts the small local service but does not download the
model. The first confirmed Hero Frame Set downloads approximately 12 GB; keep
at least 20 GB of free disk space.

## Pi Desktop packaging rule

Pi Desktop expects the active configuration file to be named
`config_options.yml`; the repository now carries the public configurator under
that exact name. The separate Core and Hero files remain versioned
rollback/reference profiles; they are not separate public applications.

## Operational rule

Use Pi Desktop to start, stop and configure the SoloHost app. Do not launch a
second manual Compose stack on port `18888` while the Pi-managed app is
running. Pi Node is a separate application and is not modified by either
profile.
