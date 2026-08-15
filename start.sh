#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
cd "$ROOT"
mf_ensure_linux
mf_ensure_env
mf_require_docker
mf_model_runner_ready || mf_die "Docker Model Runner llama.cpp is not ready."
"$ROOT/detect-hardware.sh" >/dev/null
"$ROOT/detect-runtime.sh" >/dev/null
mf_compose up -d
app_port="$(mf_env_get MEDIAFORGE_APP_PORT 18888)"
app_url="http://127.0.0.1:$app_port"
if mf_wait_http "$app_url/health" 60 2; then
    mf_info "MediaForge is ready: $app_url"
    mf_open_url "$app_url"
else
    mf_die "MediaForge did not become ready. Run ./status.sh or ./doctor.sh."
fi
