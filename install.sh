#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
source "$ROOT/runtime-policy.sh"
source "$ROOT/scripts/intel-runtime.sh"

requested_runtime=""
test_mode=false
open_browser=true
wait_for_proof=true

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --test-mode        Use isolated WSL2 ports and container names.
  --cpu              Force the CPU/OpenVINO image path.
  --nvidia           Require the NVIDIA/CUDA image path.
  --intel            Require an Intel GPU execution check.
  --auto              Automatically select NVIDIA, Intel or CPU (default).
  --no-open           Do not open a browser after startup.
  --skip-proof-wait   Return after Prompt Doctor is ready.
  --help              Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --test-mode) test_mode=true ;;
        --cpu) requested_runtime="cpu" ;;
        --nvidia) requested_runtime="nvidia" ;;
        --intel) requested_runtime="intel" ;;
        --auto) requested_runtime="auto" ;;
        --no-open) open_browser=false ;;
        --skip-proof-wait) wait_for_proof=false ;;
        --help|-h) usage; exit 0 ;;
        *) mf_die "Unknown option: $1" ;;
    esac
    shift
done

cd "$ROOT"
mf_ensure_linux
mf_ensure_env
if [ -z "$requested_runtime" ]; then requested_runtime="$(mf_env_get MEDIAFORGE_IMAGE_RUNTIME auto)"; fi
mkdir -p "$MF_RUNTIME_DIR"
chmod +x "$ROOT"/*.sh "$ROOT"/scripts/*.sh 2>/dev/null || true
log_file="$MF_RUNTIME_DIR/install-linux.log"
touch "$log_file"

mf_step "Checking Linux prerequisites"
mf_require_command curl "curl is required. On Ubuntu run: sudo apt-get install curl"
mf_require_command python3 "Python 3 is required. On Ubuntu run: sudo apt-get install python3"
mf_require_docker

if mf_is_wsl; then
    mf_info "Environment: Ubuntu under WSL2 / Docker Desktop"
    if docker inspect mediaforge-prompt-studio >/dev/null 2>&1 && [ "$test_mode" = false ]; then
        mf_warn "An existing Windows MediaForge container was detected. Enabling isolated WSL2 test mode automatically."
        test_mode=true
    fi
else
    mf_info "Environment: native Linux"
fi

if [ "$test_mode" = true ]; then
    mf_configure_test_mode
    mf_info "WSL2 test mode: app port 18889, image port 8011, isolated container names."
else
    mf_env_set MEDIAFORGE_TEST_MODE 0
fi
mf_env_set MEDIAFORGE_PLATFORM linux

mf_step "Checking Docker Model Runner"
if ! command -v docker >/dev/null 2>&1 || ! docker model version >/dev/null 2>&1; then
    if mf_is_wsl; then
        mf_die "Docker Model Runner is not available in WSL2. Enable it in Docker Desktop > Settings > AI."
    fi
    if command -v apt-get >/dev/null 2>&1; then
        mf_info "Installing the official Docker Model Runner package..."
        sudo apt-get update
        sudo apt-get install -y docker-model-plugin
    else
        mf_die "Install the Docker Model Runner plugin for your Linux distribution, then run install.sh again."
    fi
fi

if ! mf_model_runner_ready; then
    if mf_is_wsl; then
        mf_die "Docker Model Runner is not ready. Enable it in Docker Desktop and wait for llama.cpp to report Running."
    fi
    docker model install-runner >/dev/null 2>&1 || true
    sleep 5
    mf_model_runner_ready || mf_die "Docker Model Runner llama.cpp is not ready. Run: docker model status"
fi
docker model status | tee -a "$log_file"

mf_step "Detecting Linux hardware"
"$ROOT/detect-hardware.sh" | tee -a "$log_file"

mf_step "Building the shared application and runtime tools"
docker build -t mediaforge-prompt-studio:v0.4-preview "$ROOT"

mf_step "Selecting Visual Proof Frame runtime"
mf_select_runtime "$requested_runtime"
selected_runtime="$(mf_env_get MEDIAFORGE_ACTIVE_IMAGE_RUNTIME cpu)"
image_port="$(mf_env_get MEDIAFORGE_IMAGE_PORT 8010)"

"$ROOT/detect-runtime.sh" | tee -a "$log_file"

model="$(mf_env_get MEDIAFORGE_MODEL ai/qwen2.5:3B-Q4_K_M)"
mf_step "Pulling Prompt Doctor model: $model"
docker model pull "$model" | tee -a "$log_file"

mf_step "Creating local model caches"
mkdir -p "$ROOT/data/ovms-models" "$ROOT/data/huggingface" "$ROOT/data/intel-text-models"
# The OpenVINO and CUDA images may use container-specific UIDs that do not
# match the Linux host user. These directories contain downloadable model
# cache data only, so make the bind mounts writable without requiring sudo.
chmod 0777 "$ROOT/data/ovms-models" "$ROOT/data/huggingface" "$ROOT/data/intel-text-models"

mf_step "Validating and starting MediaForge"
mf_compose config --quiet
mf_compose up -d --build --remove-orphans | tee -a "$log_file"

app_port="$(mf_env_get MEDIAFORGE_APP_PORT 18888)"
app_url="http://127.0.0.1:$app_port"
image_url="http://127.0.0.1:$image_port/v2/health/ready"

mf_step "Waiting for MediaForge web app"
if ! mf_wait_http "$app_url/health" 90 2; then
    mf_compose ps >&2 || true
    mf_die "MediaForge did not become ready. Run ./status.sh and ./doctor.sh."
fi
mf_info "MediaForge web app is ready. Prompt Doctor can be used now."
[ "$open_browser" = true ] && mf_open_url "$app_url"

proof_ready=false
if [ "$wait_for_proof" = true ]; then
    mf_step "Preparing Visual Proof Frame / SDXL"
    mf_info "The first SDXL download is large. Prompt Doctor remains available while it downloads."
    cache_path="$ROOT/data/ovms-models"
    [ "$selected_runtime" = "nvidia" ] && cache_path="$ROOT/data/huggingface"
    for ((i=0; i<360; i++)); do
        if curl --silent --fail --max-time 5 "$image_url" >/dev/null 2>&1; then
            proof_ready=true
            break
        fi
        if (( i % 3 == 0 )); then
            elapsed="$(awk -v seconds="$((i*10))" 'BEGIN { printf "%.1f", seconds/60 }')"
            mf_info "SDXL download/loading in progress... elapsed: $elapsed min, local cache: $(mf_cache_size_gb "$cache_path") GB"
        fi
        sleep 10
    done
fi

"$ROOT/detect-runtime.sh" >/dev/null || true
printf '\n==============================================\n'
printf 'MediaForge Prompt Studio v0.4 Preview — Linux\n'
printf 'APP: %s\n' "$app_url"
printf 'LLM: %s\n' "$model"
printf 'IMAGE: %s\n' "$selected_runtime"
printf 'SDXL READY: %s\n' "$proof_ready"
printf 'HERO FRAME SET: optional; FLUX.2 downloads after first-use confirmation (~12 GB)\n'
printf 'TEST MODE: %s\n' "$test_mode"
printf '==============================================\n'
if [ "$wait_for_proof" = true ] && [ "$proof_ready" != true ]; then
    mf_warn "Visual Proof Frame is still downloading or loading. Run ./status.sh later."
fi

printf '{"package_version":"0.4-preview"}\n' > "$MF_RUNTIME_DIR/install-complete.json"
