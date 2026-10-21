#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
cd "$ROOT"
mf_ensure_linux
mf_ensure_env
mf_require_docker
mf_compose stop
mf_info "MediaForge containers stopped. Model caches and user settings were preserved."
