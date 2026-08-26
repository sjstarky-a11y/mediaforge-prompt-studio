#!/usr/bin/env bash

# Shared Linux/WSL helpers. Entry-point scripts enable strict mode themselves.
MF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MF_ENV="$MF_ROOT/.env"
MF_ENV_EXAMPLE="$MF_ROOT/.env.example"
MF_RUNTIME_DIR="$MF_ROOT/runtime"

mf_is_wsl() {
    grep -qiE '(microsoft|wsl)' /proc/sys/kernel/osrelease 2>/dev/null
}

mf_step() {
    printf '\n==> %s\n' "$1"
}

mf_info() {
    printf '%s\n' "$1"
}

mf_warn() {
    printf 'WARNING: %s\n' "$1" >&2
}

mf_die() {
    printf '\nERROR: %s\n' "$1" >&2
    exit 1
}

mf_ensure_linux() {
    [ "$(uname -s)" = "Linux" ] || mf_die "This script supports Linux and WSL2. Use the PowerShell scripts on Windows."
    case "$(uname -m)" in
        x86_64|amd64) ;;
        *) mf_die "The v0.3 Linux development package currently supports x86_64 only." ;;
    esac
}

mf_ensure_env() {
    if [ ! -f "$MF_ENV" ]; then
        cp "$MF_ENV_EXAMPLE" "$MF_ENV"
    fi
}

mf_env_get() {
    local key="$1"
    local default_value="${2-}"
    local value=""
    if [ -f "$MF_ENV" ]; then
        value="$(awk -F= -v key="$key" '
            $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
                sub(/^[^=]*=/, "", $0); value=$0
            }
            END { gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); print value }
        ' "$MF_ENV")"
    fi
    if [ -n "$value" ]; then
        printf '%s' "$value"
    else
        printf '%s' "$default_value"
    fi
}

mf_env_set() {
    local key="$1"
    local value="$2"
    local temp_file
    mf_ensure_env
    temp_file="$(mktemp "$MF_ROOT/.env.tmp.XXXXXX")"
    awk -v key="$key" -v value="$value" '
        BEGIN { found=0 }
        $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
            if (!found) print key "=" value
            found=1
            next
        }
        { print }
        END { if (!found) print key "=" value }
    ' "$MF_ENV" > "$temp_file"
    mv "$temp_file" "$MF_ENV"
}

mf_compose_file() {
    mf_env_get MEDIAFORGE_COMPOSE_FILE docker-compose.yml
}

mf_compose() {
    local compose_file
    compose_file="$(mf_compose_file)"
    [ -f "$MF_ROOT/$compose_file" ] || mf_die "Compose file not found: $compose_file"
    docker compose --env-file "$MF_ENV" -f "$MF_ROOT/$compose_file" "$@"
}

mf_require_command() {
    command -v "$1" >/dev/null 2>&1 || mf_die "$2"
}

mf_require_docker() {
    mf_require_command docker "Docker CLI was not found. Install Docker Engine or enable Docker Desktop WSL integration."
    docker info >/dev/null 2>&1 || mf_die "Docker Engine is not running or the current user cannot access it."
    docker compose version >/dev/null 2>&1 || mf_die "Docker Compose is not available."
}

mf_model_runner_ready() {
    local output
    output="$(docker model status 2>&1 || true)"
    printf '%s' "$output" | grep -q 'Docker Model Runner is running' &&
        printf '%s' "$output" | grep -Eq '^llama\.cpp[[:space:]]+Running'
}

mf_wait_http() {
    local url="$1"
    local attempts="$2"
    local delay="$3"
    local i
    for ((i=0; i<attempts; i++)); do
        if curl --silent --show-error --fail --max-time 5 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep "$delay"
    done
    return 1
}

mf_open_url() {
    local url="$1"
    if mf_is_wsl && command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start "" "$url" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 || true
    else
        mf_info "Open in a browser: $url"
    fi
}

mf_cache_size_gb() {
    local path="$1"
    if [ ! -d "$path" ]; then
        printf '0'
        return
    fi
    local bytes
    bytes="$(du -sb "$path" 2>/dev/null | awk '{print $1}')"
    awk -v bytes="${bytes:-0}" 'BEGIN { printf "%.2f", bytes/1073741824 }'
}

mf_configure_test_mode() {
    mf_env_set MEDIAFORGE_TEST_MODE 1
    mf_env_set MEDIAFORGE_PROJECT_NAME mediaforge-prompt-studio-linux-test
    mf_env_set MEDIAFORGE_APP_CONTAINER mediaforge-linux-test
    mf_env_set MEDIAFORGE_CPU_IMAGE_CONTAINER mediaforge-ovms-sdxl-linux-test
    mf_env_set MEDIAFORGE_NVIDIA_IMAGE_CONTAINER mediaforge-image-cuda-linux-test
    mf_env_set MEDIAFORGE_HERO_IMAGE_CONTAINER mediaforge-image-flux-linux-test
    mf_env_set MEDIAFORGE_APP_PORT 18889
    mf_env_set MEDIAFORGE_OVMS_PORT 8011
    mf_env_set MEDIAFORGE_IMAGE_PORT 8011
}
