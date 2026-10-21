#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
source "$ROOT/scripts/intel-runtime.sh"
mf_ensure_linux
mkdir -p "$MF_RUNTIME_DIR"
docker model status > "$MF_RUNTIME_DIR/dmr-status.txt" 2>&1 || true
mf_runtime_tool profile
