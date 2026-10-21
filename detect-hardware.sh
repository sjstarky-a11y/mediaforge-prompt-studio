#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/mediaforge-common.sh"

mf_ensure_linux
mf_require_command python3 "Python 3 is required for Linux hardware detection."
mkdir -p "$MF_RUNTIME_DIR"

output="$MF_RUNTIME_DIR/hardware-profile.json"
python3 "$ROOT/scripts/linux_profile.py" hardware --output "$output" >/dev/null

python3 - "$output" <<'PY'
import json, sys
profile = json.load(open(sys.argv[1], encoding="utf-8"))
print("\nMediaForge Linux hardware detection")
print("-----------------------------------")
print("Platform:", profile.get("platform"))
print("OS:", profile.get("operating_system"))
print("CPU:", profile.get("cpu"))
print("RAM:", f"{profile.get('ram_gb')} GB")
gpus = profile.get("gpus") or []
if not gpus:
    print("GPU: none detected")
for gpu in gpus:
    details = [gpu.get("Vendor", "Unknown")]
    if gpu.get("AdapterRAM") is not None:
        details.append(f"{gpu['AdapterRAM']} GB")
    if gpu.get("ComputeCapability"):
        details.append(f"compute {gpu['ComputeCapability']}")
    print("GPU:", gpu.get("Name"), f"[{' | '.join(details)}]")
PY
printf 'Hardware report: %s\n' "$output"
