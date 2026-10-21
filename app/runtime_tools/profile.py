"""Runtime reporting shared by both host launchers."""
from __future__ import annotations

import re
from datetime import datetime, timezone


def parse_dmr_status(text: str, cpu_name: str, gpus: list[dict]) -> dict:
    line = next((line for line in text.splitlines() if re.match(r'^\s*llama\.cpp\s+', line)), "")
    match = re.search(r'Running\s+llama\.cpp\s+([^\s]+)', line)
    variant = match.group(1) if match else None
    running = "Docker Model Runner is running" in text and bool(match)
    backend, runtime, accelerator, vendor = "Unknown", "Unknown", "Unknown", None
    for suffix, label, owner in (("cuda", "NVIDIA CUDA", "NVIDIA"), ("rocm", "AMD ROCm", "AMD"),
                                  ("vulkan", "GPU / Vulkan", None), ("metal", "Apple Metal", "Apple"),
                                  ("cpu", "CPU / llama.cpp", None)):
        if variant and re.search(r"-" + suffix + r"(?:$|[-_])", variant):
            backend, runtime, vendor = suffix.upper() if suffix != "vulkan" else "Vulkan", label, owner
            if suffix == "cpu":
                accelerator = cpu_name
            elif owner:
                candidate = next((g for g in gpus if g.get("Vendor") == owner), {})
                accelerator = candidate.get("Name", f"{owner} GPU")
            else:
                # A Vulkan engine alone does not identify the selected physical GPU.
                accelerator = "GPU (device not reported by Model Runner)"
            break
    return {"status": "Running" if running else "Unavailable", "engine": "llama.cpp",
            "backend": backend, "runtime": runtime, "accelerator": accelerator,
            "variant": variant, "gpu_acceleration": running and backend not in {"CPU", "Unknown"},
            "gpu_vendor": vendor}


def build_profile(env: dict, hardware: dict, dmr_text: str, selection: dict | None = None) -> dict:
    cpu = str(hardware.get("cpu") or "CPU")
    llm = parse_dmr_status(dmr_text, cpu, hardware.get("gpus") or [])
    llm_gpu = llm.pop("gpu_acceleration")
    vendor = llm.pop("gpu_vendor")
    mode = env.get("MEDIAFORGE_ACTIVE_IMAGE_RUNTIME", "cpu")
    selection = selection or {}
    # A configured variable is not proof that a GPU runtime is usable.
    image_gpu = mode in {"intel", "nvidia"} and selection.get("compute_test_passed") is True and selection.get("selected") == mode
    image_vendor = "Intel" if mode == "intel" and image_gpu else "NVIDIA" if image_gpu else "CPU"
    if image_gpu and selection.get("text_runtime") == "intel" and env.get("MEDIAFORGE_ACTIVE_TEXT_RUNTIME") == "intel":
        llm = {"status": "Configured", "engine": "OpenVINO Model Server", "backend": "OpenVINO GPU",
               "runtime": "Intel GPU / OpenVINO", "accelerator": selection.get("accelerator", "Intel GPU"),
               "device": selection.get("device"), "compute_test_passed": True, "model_ready": None}
        llm_gpu, vendor = True, "Intel"
    offload = selection.get("offload_mode", "none") if image_gpu else "none"
    image = {
        "status": "Configured" if mode == "cpu" or image_gpu else "Unverified",
        "engine": "Hugging Face Diffusers" if mode == "nvidia" else "OpenVINO Model Server",
        "backend": "OpenVINO GPU" if mode == "intel" else "CUDA" if mode == "nvidia" else "CPU",
        "runtime": f"{image_vendor} / " + ("Diffusers" if mode == "nvidia" else "OpenVINO"),
        "accelerator": selection.get("accelerator", cpu) if image_gpu else cpu,
        "device": selection.get("device", "CPU"), "memory_profile": selection.get("memory_profile", "cpu"),
        "offload_mode": offload, "uses_cpu_offload": offload in {"sequential", "model"},
        "compute_test_passed": image_gpu, "model_ready": None,
    }
    active = llm_gpu or image_gpu
    profile = "Degraded" if llm["status"] not in {"Running", "Configured"} else "GPU Accelerated" if llm_gpu and image_gpu else "Hybrid" if active else "CPU / Compatible"
    summary = f"{profile.upper()} | {vendor or ('GPU' if llm_gpu else 'CPU')} TEXT | {image_vendor.upper()} IMAGE"
    return {"schema_version": 2, "package_version": "0.4-preview",
            "detected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "profile": profile, "summary": summary,
            "display_mode": "GPU" if llm_gpu and image_gpu and offload == "none" else "GPU + CPU" if active else "CPU",
            "gpu_acceleration": active,
            "gpu_acceleration_scope": ",".join(name for name, enabled in (("llm", llm_gpu), ("image", image_gpu)) if enabled) or "none",
            "llm": llm, "image": image, "platform": hardware.get("platform", "Windows"),
            "note": "GPU execution and model readiness are separate checks. Hero Frame uses its own reported backend."}
