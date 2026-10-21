"""Export an allowlisted report without models, prompts, logs, URLs or paths."""
from datetime import datetime, timezone


def shareable_report(profile: dict) -> dict:
    result = {"application": "MediaForge Prompt Studio",
              "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "package_version": profile.get("package_version") if profile.get("package_version") in {"0.4-preview", "0.3", "0.2-dev"} else "unknown",
              "platform": profile.get("platform") if profile.get("platform") in {"Windows", "Linux", "WSL2"} else "unknown", "components": {}}
    for name in ("llm", "image"):
        source = profile.get(name, {})
        if not isinstance(source, dict):
            source = {}
        result["components"][name] = {
            "status": source.get("status") if source.get("status") in {"Running", "Configured", "Unverified", "Unavailable", "Unknown"} else "Unknown",
            "backend": source.get("backend") if source.get("backend") in {"CUDA", "CPU", "Vulkan", "ROCM", "ROCm", "METAL", "OpenVINO GPU", "Unknown"} else "Unknown",
            "compute_test_passed": source.get("compute_test_passed") is True,
        }
    return result
