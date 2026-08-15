#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
cd "$ROOT"
mf_ensure_linux
mf_ensure_env

save_report=false
[ "${1-}" = "--save" ] && save_report=true
report="$MF_RUNTIME_DIR/doctor-report.txt"
mkdir -p "$MF_RUNTIME_DIR"

generate_report() {
    printf 'MediaForge Linux Doctor\n'
    printf 'Generated: %s\n' "$(date --iso-8601=seconds 2>/dev/null || date)"
    printf 'Platform: %s\n' "$(mf_is_wsl && printf 'WSL2' || printf 'native Linux')"
    printf 'Kernel: %s\n' "$(uname -srmo)"
    printf 'Architecture: %s\n' "$(uname -m)"
    printf 'Project directory: %s\n' "$ROOT"
    printf 'Test mode: %s\n' "$(mf_env_get MEDIAFORGE_TEST_MODE 0)"
    printf 'Compose file: %s\n' "$(mf_compose_file)"
    printf 'App port: %s\n' "$(mf_env_get MEDIAFORGE_APP_PORT 18888)"
    printf 'Image port: %s\n' "$(mf_env_get MEDIAFORGE_IMAGE_PORT 8010)"
    printf '\nDisk usage:\n'
    df -h "$ROOT" 2>&1 || true
    printf '\nDocker version:\n'
    docker version 2>&1 || true
    printf '\nDocker Compose version:\n'
    docker compose version 2>&1 || true
    printf '\nDocker Model Runner:\n'
    docker model status 2>&1 || true
    printf '\nNVIDIA:\n'
    nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader 2>&1 || printf 'NVIDIA GPU unavailable.\n'
    printf '\nCompose validation:\n'
    mf_compose config --quiet 2>&1 && printf 'Valid\n' || printf 'Invalid\n'
    printf '\nMediaForge containers:\n'
    mf_compose ps 2>&1 || true
    printf '\nApplication health:\n'
    curl --silent --show-error --max-time 5 "http://127.0.0.1:$(mf_env_get MEDIAFORGE_APP_PORT 18888)/health" 2>&1 || true
    printf '\n\nImage health:\n'
    curl --silent --show-error --max-time 5 -o /dev/null -w 'HTTP %{http_code}\n' "http://127.0.0.1:$(mf_env_get MEDIAFORGE_IMAGE_PORT 8010)/v2/health/ready" 2>&1 || true
    printf '\nRecent application logs (last 30 lines):\n'
    mf_compose logs --tail 30 mediaforge 2>&1 || true
}

if [ "$save_report" = true ]; then
    generate_report | tee "$report"
    printf '\nDiagnostic report saved to: %s\n' "$report"
    printf 'The report omits the .env file and prompt/response bodies. It includes selected runtime settings and recent logs; review it before sharing.\n'
else
    generate_report
    printf '\nRun ./doctor.sh --save to create a shareable local report.\n'
fi
