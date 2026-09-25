# MediaForge Prompt Studio — Pi SoloHost v0.3.1

This folder mirrors the tested Pi SoloHost package configuration for MediaForge Prompt Studio v0.3.1.

## Before installation

1. Install and start Docker Desktop.
2. Wait until Docker Engine is running.
3. Open Docker Desktop > Settings > AI.
4. Make sure Docker Model Runner is enabled.
5. Keep Docker Desktop running while Pi Desktop installs or recreates MediaForge.

The Prompt Doctor model is provisioned through Docker Model Runner. On a clean installation the first model download can take some time.

Visual Proof is optional. Its first use downloads an additional local image model of approximately 12 GB. Keep at least 20 GB of free disk space when using Visual Proof.

## Files

- `config_options.yml` — Pi Desktop configurator shown before recreation/install.
- `docker-compose.yml` — tested SoloHost service definition.

## Runtime images

- `aerialcroatia/mediaforge-prompt-studio:0.3-solohost.8`
- `aerialcroatia/mediaforge-image-flux:0.3-solohost.8`

v0.3.1 is an installation/setup hardening release. The runtime images remain on the tested `0.3-solohost.8` build because the application runtime itself was not changed.

## Important

The repository root still contains the older standalone Windows Public Test v0.1a package. Its root `docker-compose.yml`, `install.ps1`, and related files are intentionally kept unchanged so that the standalone installer remains reproducible.
