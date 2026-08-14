import json
import os
from pathlib import Path
from typing import Any


RUNTIME_PROFILE_PATH = Path(
    os.getenv("MEDIAFORGE_RUNTIME_PROFILE_PATH", "/runtime/runtime-profile.json")
)


def default_runtime_profile() -> dict[str, Any]:
    """Return a safe response while host-side runtime detection is unavailable."""
    return {
        "schema_version": 1,
        "profile": "Unknown",
        "summary": "RUNTIME DETECTION PENDING",
        "gpu_acceleration": False,
        "gpu_acceleration_scope": "none",
        "detected_at": None,
        "llm": {
            "status": "Unknown",
            "engine": "llama.cpp",
            "backend": "Unknown",
            "runtime": "Unknown",
            "accelerator": "Unknown",
        },
        "image": {
            "status": "Configured",
            "engine": "OpenVINO Model Server",
            "backend": "CPU",
            "runtime": "CPU / OpenVINO SDXL INT8",
            "accelerator": "CPU",
        },
    }


def load_runtime_profile(path: Path | str | None = None) -> dict[str, Any]:
    """Load the host-generated profile without making app health depend on it."""
    profile_path = Path(path) if path is not None else RUNTIME_PROFILE_PATH
    fallback = default_runtime_profile()

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return fallback

    if not isinstance(data, dict):
        return fallback

    result = fallback.copy()
    result.update(
        {
            key: data[key]
            for key in (
                "schema_version",
                "package_version",
                "detected_at",
                "profile",
                "summary",
                "gpu_acceleration",
                "gpu_acceleration_scope",
                "note",
            )
            if key in data
        }
    )

    for component in ("llm", "image"):
        component_data = data.get(component)
        if isinstance(component_data, dict):
            merged = fallback[component].copy()
            merged.update(component_data)
            result[component] = merged

    return result
