#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
source "$ROOT/scripts/intel-runtime.sh"
mf_ensure_linux
mf_require_docker
mf_runtime_tool diagnostics
mf_info "Shareable report: runtime/doctor-report.json. Model names, prompts, paths and logs are excluded."
