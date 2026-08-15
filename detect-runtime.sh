#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"

mf_ensure_linux
mf_ensure_env
mf_require_command python3 "Python 3 is required for Linux runtime detection."
mkdir -p "$MF_RUNTIME_DIR"

hardware="$MF_RUNTIME_DIR/hardware-profile.json"
if [ ! -f "$hardware" ]; then
    "$ROOT/detect-hardware.sh" >/dev/null
fi
output="$MF_RUNTIME_DIR/runtime-profile.json"
python3 "$ROOT/scripts/linux_profile.py" runtime --env "$MF_ENV" --hardware "$hardware" --output "$output" >/dev/null

python3 - "$output" <<'PY'
import json, sys
profile = json.load(open(sys.argv[1], encoding="utf-8"))
print("\nMediaForge adaptive Linux runtime detection")
print("-------------------------------------------")
print("Profile:", profile.get("profile"))
print("User mode:", profile.get("display_mode"))
llm = profile.get("llm", {})
image = profile.get("image", {})
print("LLM:", llm.get("runtime"), f"[{llm.get('accelerator')}]")
print("Default model:", llm.get("default_model"), f"(installed models: {llm.get('installed_models')})")
print("Image:", image.get("runtime"))
print("GPU acceleration:", profile.get("gpu_acceleration"), f"(scope: {profile.get('gpu_acceleration_scope')})")
PY
printf 'Runtime report: %s\n' "$output"
