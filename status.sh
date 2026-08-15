#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
cd "$ROOT"
mf_ensure_linux
mf_ensure_env

printf '\nHardware detection\n------------------\n'
"$ROOT/detect-hardware.sh" || true

printf '\nMediaForge containers\n---------------------\n'
if command -v docker >/dev/null 2>&1; then
    mf_compose ps || true
else
    mf_warn "Docker CLI not found."
fi

printf '\nDocker Model Runner\n-------------------\n'
docker model status 2>&1 || true

printf '\nAdaptive runtime detection\n--------------------------\n'
"$ROOT/detect-runtime.sh" || true

app_port="$(mf_env_get MEDIAFORGE_APP_PORT 18888)"
image_port="$(mf_env_get MEDIAFORGE_IMAGE_PORT 8010)"
printf '\nMediaForge health\n-----------------\n'
if curl --silent --show-error --fail --max-time 5 "http://127.0.0.1:$app_port/health"; then
    printf '\n'
else
    mf_warn "MediaForge is not reachable on port $app_port."
fi

printf '\nVisual Proof Frame health\n-------------------------\n'
if curl --silent --fail --max-time 5 "http://127.0.0.1:$image_port/v2/health/ready" >/dev/null; then
    mf_info "Image service ready: True"
else
    mf_info "Image service ready: False (the first SDXL download may still be in progress)"
fi
mf_info "Image runtime: $(mf_env_get MEDIAFORGE_ACTIVE_IMAGE_RUNTIME cpu)"

printf '\nRuntime profile\n---------------\n'
if [ -f "$MF_RUNTIME_DIR/runtime-profile.json" ]; then
    cat "$MF_RUNTIME_DIR/runtime-profile.json"
else
    mf_warn "No runtime profile is available."
fi
