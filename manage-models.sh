#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"
cd "$ROOT"
mf_ensure_linux
mf_ensure_env

if [ "${1-}" = "--help" ] || [ "${1-}" = "-h" ]; then
    cat <<'EOF'
Usage:
  ./manage-models.sh list
  ./manage-models.sh recommend
  ./manage-models.sh install --model MODEL [--set-default] [--accept-model-license]
  ./manage-models.sh select --model MODEL
EOF
    exit 0
fi

action="${1:-list}"
[ "$#" -gt 0 ] && shift
model=""
set_default=false
accept_license=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --model) shift; model="${1-}" ;;
        --set-default) set_default=true ;;
        --accept-model-license) accept_license=true ;;
        --help|-h)
            cat <<'EOF'
Usage:
  ./manage-models.sh list
  ./manage-models.sh recommend
  ./manage-models.sh install --model MODEL [--set-default] [--accept-model-license]
  ./manage-models.sh select --model MODEL
EOF
            exit 0
            ;;
        *) mf_die "Unknown option: $1" ;;
    esac
    shift
done

case "$action" in list|recommend|install|select) ;; *) mf_die "Action must be list, recommend, install, or select." ;; esac

mf_require_command python3 "Python 3 is required for model management."
mf_require_docker

catalog="$ROOT/models/model-catalog.json"
[ -f "$catalog" ] || mf_die "Model catalog not found: $catalog"

installed_json="$(python3 - <<'PY'
import json, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:12434/models", timeout=5) as r:
        print(json.dumps(json.load(r)))
except Exception:
    print("[]")
PY
)"

if [ "$action" = list ]; then
    vram="0"
    if command -v nvidia-smi >/dev/null 2>&1; then
        memory="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | sort -nr | head -n1 || true)"
        [ -n "$memory" ] && vram="$(awk -v mb="$memory" 'BEGIN { printf "%.1f", mb/1024 }')"
    fi
    python3 - "$catalog" "$installed_json" "$vram" <<'PY'
import json, sys
from app.model_catalog import load_model_catalog, parse_dmr_model_ids
catalog = load_model_catalog(sys.argv[1])
try: installed = set(parse_dmr_model_ids(json.loads(sys.argv[2])))
except Exception: installed = set()
print("\nMediaForge model catalog")
print("------------------------")
print("Detected NVIDIA VRAM:", f"{sys.argv[3]} GB" if float(sys.argv[3]) > 0 else "unavailable / CPU profile")
print(f"{'Installed':<10} {'Profile':<10} {'Model':<24} {'VRAM':>5}  {'Validation':<11} ID")
for item in catalog.get("models", []):
    yes = "Yes" if item["id"] in installed else "No"
    print(f"{yes:<10} {item['profile']:<10} {item['display_name']:<24} {item['recommended_vram_gb']:>5}  {item['validation']:<11} {item['id']}")
catalog_ids = {item["id"] for item in catalog.get("models", [])}
for model_id in sorted(installed - catalog_ids):
    print(f"{'Yes':<10} {'Custom':<10} {model_id.removeprefix('ai/'):<24} {'':>5}  {'unverified':<11} {model_id}")
PY
    exit 0
fi

if [ "$action" = recommend ]; then
    vram="0"
    if command -v nvidia-smi >/dev/null 2>&1; then
        memory="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | sort -nr | head -n1 || true)"
        [ -n "$memory" ] && vram="$(awk -v mb="$memory" 'BEGIN { printf "%.1f", mb/1024 }')"
    fi
    python3 - "$catalog" "$vram" <<'PY'
import json, sys
catalog = json.load(open(sys.argv[1], encoding="utf-8"))
vram = float(sys.argv[2])
if vram <= 0:
    print("Recommended model: ai/qwen2.5:3B-Q4_K_M (CPU / compatible default)")
else:
    eligible = [m for m in catalog["models"] if float(m["recommended_vram_gb"]) <= vram]
    selected = max(eligible, key=lambda m: float(m["recommended_vram_gb"]), default=catalog["models"][0])
    print("Recommended profile:", selected["profile"])
    print("Recommended model:", selected["id"])
    print("Validation:", selected["validation"])
    print("This is a recommendation only; no model was downloaded or selected.")
PY
    exit 0
fi

[ -n "$model" ] || mf_die "Specify --model with the full Docker Model Runner identifier."
python3 - "$model" <<'PY' || exit 1
import sys
from app.model_catalog import is_valid_model_id
if not is_valid_model_id(sys.argv[1]):
    print(f"Invalid Docker Model Runner model identifier: {sys.argv[1]}", file=sys.stderr)
    raise SystemExit(1)
PY

license="$(python3 - "$catalog" "$model" <<'PY'
import json, sys
catalog = json.load(open(sys.argv[1], encoding="utf-8"))
item = next((item for item in catalog.get("models", []) if item.get("id") == sys.argv[2]), {})
print(item.get("license", "Unknown"))
PY
)"

if [ "$action" = install ]; then
    if [ "$license" != "Apache-2.0" ] && [ "$license" != "Unknown" ] && [ "$accept_license" != true ]; then
        mf_die "This model uses '$license'. Review its terms, then repeat with --accept-model-license."
    fi
    mf_info "Downloading model: $model"
    docker model pull "$model"
    if [ "$set_default" = true ]; then
        mf_env_set MEDIAFORGE_MODEL "$model"
        mf_info "Default model updated. Run ./start.sh to apply it."
    else
        mf_info "Reload MediaForge to show the newly installed model."
    fi
    exit 0
fi

if [ "$action" = select ]; then
    if ! python3 - "$installed_json" "$model" <<'PY'
import json, sys
from app.model_catalog import parse_dmr_model_ids
raise SystemExit(0 if sys.argv[2] in parse_dmr_model_ids(json.loads(sys.argv[1])) else 1)
PY
    then
        mf_die "Model is not installed locally. Install it first with ./manage-models.sh install --model '$model'."
    fi
    mf_env_set MEDIAFORGE_MODEL "$model"
    mf_info "Default model updated. Run ./start.sh to apply it."
fi
