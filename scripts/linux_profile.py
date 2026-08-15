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


def parse_dmr_status(text: str, cpu_name: str, gpus: list[dict[str, Any]]) -> dict[str, Any]:
    running = "Docker Model Runner is running" in text
    line = next((line for line in text.splitlines() if re.match(r'^\s*llama\.cpp\s+', line)), "")
    match = re.search(r'Running\s+llama\.cpp\s+([^\s]+)', line)
    variant = match.group(1) if match else None
    backend, runtime, accelerator, vendor = "Unknown", "Unknown", "Unknown", None
    if variant and "-cuda" in variant:
        backend, runtime, vendor = "CUDA", "NVIDIA CUDA", "NVIDIA"
    elif variant and "-rocm" in variant:
        backend, runtime, vendor = "ROCm", "AMD ROCm", "AMD"
    elif variant and "-vulkan" in variant:
        backend, runtime, vendor = "Vulkan", "GPU / Vulkan", None
    elif variant and "-cpu" in variant:
        backend, runtime, accelerator = "CPU", "CPU / llama.cpp", cpu_name
    if backend in {"CUDA", "ROCm", "Vulkan"}:
        candidate = next((gpu for gpu in gpus if vendor is None or gpu.get("Vendor") == vendor), None)
        accelerator = candidate.get("Name", "GPU") if candidate else (f"{vendor} GPU" if vendor else "GPU")
    return {
        "status": "Running" if running else "Unavailable",
        "engine": "llama.cpp",
        "backend": backend,
        "runtime": runtime,
        "accelerator": accelerator,
        "variant": variant,
        "gpu_acceleration": backend in {"CUDA", "ROCm", "Vulkan"},
        "gpu_vendor": vendor,
    }


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
    cpu_name = str(hardware.get("cpu") or "Unknown CPU")
    gpus = hardware.get("gpus") if isinstance(hardware.get("gpus"), list) else []
    _, dmr_text = _run(["docker", "model", "status"])
    llm = parse_dmr_status(dmr_text, cpu_name, gpus)
    llm["default_model"] = env.get("MEDIAFORGE_MODEL", "ai/qwen2.5:3B-Q4_K_M")
    llm["installed_models"] = _installed_model_count()

    image_mode = env.get("MEDIAFORGE_ACTIVE_IMAGE_RUNTIME", env.get("MEDIAFORGE_IMAGE_RUNTIME", "cpu")).lower()
    if image_mode == "auto":
        image_mode = "cpu"
    image_gpu = image_mode == "nvidia"
    image_profile = env.get("MEDIAFORGE_NVIDIA_PROFILE", "auto").lower() if image_gpu else "cpu"
    offload = env.get("MEDIAFORGE_NVIDIA_OFFLOAD_MODE", "auto").lower() if image_gpu else "none"
    uses_offload = image_gpu and offload in {"sequential", "model"}
    nvidia = next((gpu for gpu in gpus if gpu.get("Vendor") == "NVIDIA"), None)
    image = {
        "status": "Configured",
        "engine": "Hugging Face Diffusers" if image_gpu else "OpenVINO Model Server",
        "backend": "CUDA" if image_gpu else "CPU",
        "runtime": "NVIDIA CUDA / Diffusers SDXL" if image_gpu else "CPU / OpenVINO SDXL INT8",
        "accelerator": (nvidia or {}).get("Name", "NVIDIA GPU") if image_gpu else cpu_name,
        "model": env.get("MEDIAFORGE_NVIDIA_IMAGE_MODEL", "stabilityai/stable-diffusion-xl-base-1.0") if image_gpu else "OpenVINO/stable-diffusion-xl-base-1.0-int8-ov",
        "memory_profile": image_profile,
        "offload_mode": offload,
        "uses_cpu_offload": uses_offload,
    }
    llm_gpu = bool(llm.pop("gpu_acceleration"))
    vendor = llm.pop("gpu_vendor")
    overall_gpu = llm_gpu or image_gpu
    if llm["status"] != "Running":
        profile_name = "Degraded"
    elif llm_gpu and image_gpu:
        profile_name = "GPU Accelerated"
    elif llm_gpu or image_gpu:
        profile_name = "Hybrid"
    else:
        profile_name = "CPU / Compatible"
    if not overall_gpu:
        display = "CPU"
    elif llm_gpu and image_gpu and not uses_offload:
        display = "GPU"
    else:
        display = "GPU + CPU"
    if profile_name == "GPU Accelerated":
        summary = f"GPU ACCELERATED | {vendor or 'GPU'} LLM | NVIDIA IMAGE"
    elif profile_name == "Hybrid":
        summary = f"HYBRID | {vendor or 'CPU'} LLM | {'NVIDIA' if image_gpu else 'CPU'} IMAGE"
    elif profile_name == "CPU / Compatible":
        summary = "CPU | LLM + IMAGE"
    else:
        summary = "DEGRADED | MODEL RUNNER UNAVAILABLE"
    return {
        "schema_version": 1,
        "package_version": "0.2-dev",
        "detected_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "profile": profile_name,
        "summary": summary,
        "display_mode": display,
        "gpu_acceleration": overall_gpu,
        "gpu_acceleration_scope": "llm,image" if llm_gpu and image_gpu else "llm" if llm_gpu else "image" if image_gpu else "none",
        "llm": llm,
        "image": image,
        "platform": hardware.get("platform", "Linux"),
        "note": "LLM and image runtimes are detected independently. CPU remains the Linux fallback.",
    }


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
