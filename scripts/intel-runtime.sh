#!/usr/bin/env bash

mf_check_intel_runtime() {
    printf '{"available":false,"compute_test_passed":false}\n' > "$MF_RUNTIME_DIR/intel-probe.json"
    # lspci is often absent in WSL; the GPU runtime remains the authoritative probe.
    if ! [ -e /dev/dxg ] && ! [ -d /dev/dri ]; then return; fi
    docker build -t mediaforge-intel-runtime:v0.4-preview "$MF_ROOT/intel_runtime" || return 0
    local device result
    device="$(mf_env_get MEDIAFORGE_INTEL_DEVICE auto)"
    local args=()
    if [ -e /dev/dxg ]; then
        args+=(--device /dev/dxg --mount type=bind,source=/usr/lib/wsl,target=/usr/lib/wsl,readonly)
    else
        args+=(--device /dev/dri)
        local group
        group="$(stat -c '%g' /dev/dri/renderD* 2>/dev/null | head -n 1)"
        if [ -n "$group" ]; then args+=(--group-add "$group"); mf_env_set MEDIAFORGE_INTEL_RENDER_GROUP "$group"; fi
    fi
    if result="$(docker run --rm "${args[@]}" -e "MEDIAFORGE_INTEL_DEVICE=$device" --entrypoint python3 \
        mediaforge-intel-runtime:v0.4-preview /opt/mediaforge/probe.py)"; then
        printf '%s\n' "$result" > "$MF_RUNTIME_DIR/intel-probe.json"
        mf_info "Intel GPU execution check passed."
    else
        mf_warn "Intel GPU execution is unavailable. Auto mode can use CPU."
    fi
}

mf_runtime_tool() {
    docker run --rm --user "$(id -u):$(id -g)" --entrypoint python \
        --mount "type=bind,source=$MF_ROOT,target=/workspace" mediaforge-prompt-studio:v0.4-preview \
        -m runtime_tools.cli "$@"
}

mf_select_runtime() {
    local requested="$1"
    local name="" compute=0 memory=0 available=false line=""
    if [ "$requested" = auto ] || [ "$requested" = nvidia ]; then
        if command -v nvidia-smi >/dev/null 2>&1; then
            line="$(nvidia-smi --query-gpu=name,compute_cap,memory.total --format=csv,noheader,nounits 2>/dev/null | head -n 1 || true)"
            if [ -n "$line" ]; then
                IFS=',' read -r name compute memory <<< "$line"
                if docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi -L >/dev/null 2>&1; then available=true; fi
            fi
        fi
    fi
    python3 - "$MF_RUNTIME_DIR/nvidia-probe.json" "$available" "$name" "$compute" "$memory" <<'PY'
import json, sys
from pathlib import Path
try:
    report = dict(available=sys.argv[2] == "true", name=sys.argv[3], compute_capability=float(sys.argv[4]), memory_bytes=float(sys.argv[5])*1024**2)
except ValueError:
    report = dict(available=False)
Path(sys.argv[1]).write_text(json.dumps(report), encoding="utf-8")
PY
    printf '{"available":false,"compute_test_passed":false}\n' > "$MF_RUNTIME_DIR/intel-probe.json"
    if [ "$requested" = auto ] || [ "$requested" = intel ]; then mf_check_intel_runtime; fi
    local transport=linux
    if mf_is_wsl || docker info --format '{{.OperatingSystem}}' | grep -qi 'Docker Desktop'; then transport=wsl; fi
    mf_runtime_tool select --mode "$requested" --transport "$transport"
}
