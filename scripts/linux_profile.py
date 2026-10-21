#!/usr/bin/env python3
"""Generate MediaForge hardware/runtime reports on Linux and WSL2."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


def _run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return result.returncode, result.stdout + result.stderr


def _os_name() -> str:
    values: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values.get("PRETTY_NAME", platform.platform())


def _cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "Unknown CPU"


def _ram_gb() -> float:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 1024 / 1024, 1)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def detect_gpus() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    code, output = _run([
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,compute_cap",
        "--format=csv,noheader,nounits",
    ])
    if code == 0:
        for line in output.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 4:
                try:
                    memory_gb = round(float(parts[2]) / 1024, 1)
                except ValueError:
                    memory_gb = None
                gpus.append({
                    "Name": parts[0],
                    "Vendor": "NVIDIA",
                    "Driver": parts[1],
                    "AdapterRAM": memory_gb,
                    "ComputeCapability": parts[3],
                })

    code, output = _run(["lspci", "-mm"])
    if code == 0:
        known_names = {gpu["Name"].lower() for gpu in gpus}
        for line in output.splitlines():
            if not re.search(r'(VGA compatible controller|3D controller|Display controller)', line, re.I):
                continue
            vendor = "Unknown"
            if re.search(r'NVIDIA', line, re.I):
                vendor = "NVIDIA"
            elif re.search(r'AMD|ATI', line, re.I):
                vendor = "AMD"
            elif re.search(r'Intel', line, re.I):
                vendor = "Intel"
            name = re.sub(r'^.*?(VGA compatible controller|3D controller|Display controller)\s+"?', '', line, flags=re.I).strip(' "')
            if name and not any(existing in name.lower() or name.lower() in existing for existing in known_names):
                gpus.append({"Name": name, "Vendor": vendor, "Driver": None, "AdapterRAM": None})
    return gpus


def hardware_profile() -> dict[str, Any]:
    kernel = platform.release()
    return {
        "schema_version": 1,
        "profile_type": "hardware_inventory",
        "package_version": "0.2-dev",
        "detected_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "operating_system": _os_name(),
        "platform": "WSL2" if re.search(r'microsoft|wsl', kernel, re.I) else "Linux",
        "architecture": platform.machine(),
        "kernel": kernel,
        "cpu": _cpu_name(),
        "logical_processors": os.cpu_count() or 0,
        "ram_gb": _ram_gb(),
        "gpus": detect_gpus(),
        "note": "This file records Linux hardware only. Runtime selection is written separately.",
    }


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


# Kept as an import for callers of the earlier Linux helper API.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from runtime_tools.profile import parse_dmr_status, build_profile


def _installed_model_count() -> int:
    code, output = _run(["docker", "model", "list", "-q"])
    if code == 0:
        model_ids = {line.strip() for line in output.splitlines() if line.strip()}
        if model_ids:
            return len(model_ids)
    try:
        with urllib.request.urlopen("http://127.0.0.1:12434/models", timeout=5) as response:
            payload = json.load(response)
        if isinstance(payload, list):
            return len(payload)
        for key in ("data", "models"):
            if isinstance(payload.get(key), list):
                return len(payload[key])
    except (OSError, ValueError, TypeError):
        pass
    return 0


def runtime_profile(env_path: Path, hardware_path: Path) -> dict[str, Any]:
    env = read_env(env_path)
    try:
        hardware = json.loads(hardware_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        hardware = hardware_profile()
    _, dmr_text = _run(["docker", "model", "status"])
    try:
        selection = json.loads((hardware_path.parent / "selection.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        selection = {}
    return build_profile(env, hardware, dmr_text, selection)



def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    hardware_parser = subparsers.add_parser("hardware")
    hardware_parser.add_argument("--output", required=True, type=Path)
    runtime_parser = subparsers.add_parser("runtime")
    runtime_parser.add_argument("--env", required=True, type=Path)
    runtime_parser.add_argument("--hardware", required=True, type=Path)
    runtime_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "hardware":
        profile = hardware_profile()
    else:
        profile = runtime_profile(args.env, args.hardware)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()
