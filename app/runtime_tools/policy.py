"""Select a backend only after its execution environment has passed a probe."""
from __future__ import annotations


def nvidia_policy(compute: float, memory_gb: float) -> dict:
    if compute < 6 or memory_gb < 4:
        return {"eligible": False, "profile": "unsupported", "offload_mode": "none"}
    profile, offload = ("low_memory", "sequential") if memory_gb < 6 else ("balanced", "model") if memory_gb < 8 else ("full", "none")
    return {"eligible": True, "profile": profile, "offload_mode": offload}


def select_backend(requested: str, nvidia: dict, intel: dict) -> dict:
    if requested not in {"auto", "cpu", "nvidia", "intel"}:
        raise ValueError("Runtime must be auto, cpu, nvidia, or intel.")
    intel_ready = (intel.get("available") is True and
                   intel.get("compute_test_passed") is True and
                   str(intel.get("device", "")).startswith("GPU") and
                   int(intel.get("memory_bytes") or 0) >= 8 * 1024**3)
    policy = nvidia_policy(float(nvidia.get("compute_capability") or 0), float(nvidia.get("memory_bytes") or 0) / 1024**3)
    nvidia = {**nvidia, **policy}
    ready = {"nvidia": nvidia.get("available") is True and policy["eligible"], "intel": intel_ready, "cpu": True}
    if requested != "auto" and not ready[requested]:
        raise ValueError(f"Requested {requested} runtime did not pass its GPU check. Use auto or cpu.")
    selected = requested if requested != "auto" else next(
        name for name in ("nvidia", "intel", "cpu") if ready[name])
    candidate = intel if selected == "intel" else nvidia if selected == "nvidia" else {}
    return {
        "requested": requested, "selected": selected,
        "device": candidate.get("device", "CUDA" if selected == "nvidia" else "CPU"),
        "accelerator": candidate.get("name", "CPU"),
        "memory_profile": candidate.get("profile", "intel" if selected == "intel" else "cpu"),
        "offload_mode": candidate.get("offload_mode", "none"),
        "compute_test_passed": selected != "cpu",
        "memory_bytes": int(candidate.get("memory_bytes") or 0),
        "reason": ("GPU execution check passed; model readiness is checked separately."
                   if selected != "cpu" else "CPU compatibility mode. No eligible GPU runtime was selected."),
    }


def select_text_runtime(selection: dict, requested: str = "auto") -> str:
    if requested not in {"auto", "dmr", "intel"}:
        raise ValueError("Text runtime must be auto, dmr, or intel.")
    # The public 7B INT4 text model and Proof Frame share the GPU. Keep space for both.
    eligible = selection["selected"] == "intel" and selection.get("memory_bytes", 0) >= 16 * 1024**3
    if requested == "intel" and not eligible:
        raise ValueError("Intel text needs a verified Intel image profile with at least 16 GiB GPU memory. Use auto or dmr.")
    return "intel" if requested != "dmr" and eligible else "dmr"


def selection_env(selection: dict, transport: str = "linux") -> dict[str, str]:
    mode = selection["selected"]
    compose = {"cpu": "docker-compose.yml", "nvidia": "docker-compose.nvidia.yml",
               "intel": "docker-compose.intel.yml"}[mode]
    if mode == "intel" and transport == "wsl":
        compose = "docker-compose.intel-wsl.yml"
    return {
        "MEDIAFORGE_IMAGE_RUNTIME": selection["requested"],
        "MEDIAFORGE_ACTIVE_IMAGE_RUNTIME": mode,
        "MEDIAFORGE_COMPOSE_FILE": compose,
        "MEDIAFORGE_IMAGE_DEVICE": selection["device"],
        "MEDIAFORGE_IMAGE_API_URL": "http://image-cuda:8000/v3" if mode == "nvidia" else "http://ovms-sdxl:8000/v3",
        "MEDIAFORGE_IMAGE_BACKEND": {"cpu": "OpenVINO CPU", "intel": "Intel GPU / OpenVINO", "nvidia": "NVIDIA CUDA / Diffusers"}[mode],
        "MEDIAFORGE_NVIDIA_PROFILE": selection["memory_profile"] if mode == "nvidia" else "cpu",
        "MEDIAFORGE_NVIDIA_OFFLOAD_MODE": selection["offload_mode"] if mode == "nvidia" else "none",
    }
