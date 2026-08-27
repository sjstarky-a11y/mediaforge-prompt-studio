import json
import re
from pathlib import Path
from typing import Any


MODEL_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)


def load_model_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = Path(path)
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"schema_version": 1, "models": []}

    models = data.get("models")
    if not isinstance(models, list):
        data["models"] = []
    return data


def is_valid_model_id(model_id: str) -> bool:
    return bool(MODEL_ID_PATTERN.fullmatch(model_id.strip()))


def _normalize_dmr_model_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    model_id = value.strip()
    for prefix in ("docker.io/", "index.docker.io/"):
        if model_id.startswith(prefix):
            model_id = model_id[len(prefix) :]
            break

    return model_id if is_valid_model_id(model_id) else None


def parse_dmr_model_ids(payload: Any) -> list[str]:
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = payload.get("data", payload.get("models", []))
    else:
        return []

    if not isinstance(candidates, list):
        return []

    model_ids: list[str] = []
    for item in candidates:
        if isinstance(item, str):
            values = [item]
        elif isinstance(item, dict):
            values = [item.get("id"), item.get("model"), item.get("name")]
            tags = item.get("tags", [])
            if isinstance(tags, list):
                values.extend(tags)
            elif isinstance(tags, str):
                values.append(tags)
        else:
            continue

        for value in values:
            model_id = _normalize_dmr_model_id(value)
            if model_id:
                model_ids.append(model_id)

    return list(dict.fromkeys(model_ids))


def _display_name(model_id: str) -> str:
    short_id = model_id.removeprefix("ai/").rsplit("/", 1)[-1]
    repository, _, tag = short_id.partition(":")

    family = repository.replace("-", " ").replace("_", " ")
    family = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", family)
    family = " ".join(part.capitalize() for part in family.split())

    size = tag.split("-", 1)[0] if tag else ""
    return " ".join(part for part in (family, size) if part)


def build_model_inventory(
    installed_ids: list[str],
    default_model: str,
    catalog: dict[str, Any],
    assume_default_installed: bool = True,
) -> dict[str, Any]:
    curated = {
        item.get("id"): item
        for item in catalog.get("models", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    available = list(dict.fromkeys(installed_ids))
    if assume_default_installed and default_model not in available:
        available.insert(0, default_model)

    installed = []
    for model_id in available:
        metadata = dict(curated.get(model_id, {}))
        metadata.setdefault("id", model_id)
        metadata.setdefault("display_name", _display_name(model_id))
        metadata.setdefault("family", "Custom DMR model")
        metadata.setdefault("parameters", "Unknown")
        metadata.setdefault("profile", "Custom")
        metadata.setdefault("recommended_vram_gb", None)
        metadata.setdefault("validation", "unverified")
        metadata.setdefault("license", "Check model license")
        metadata.setdefault("prompt_mode", "standard")
        metadata["installed"] = True
        metadata["default"] = model_id == default_model
        installed.append(metadata)

    recommendations = []
    for item in catalog.get("models", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        recommendation = dict(item)
        recommendation["installed"] = item["id"] in available
        recommendation["default"] = item["id"] == default_model
        recommendations.append(recommendation)

    return {
        "default_model": default_model,
        "installed": installed,
        "recommendations": recommendations,
    }


def model_prompt_prefix(model_id: str, catalog: dict[str, Any]) -> str:
    for item in catalog.get("models", []):
        if isinstance(item, dict) and item.get("id") == model_id:
            if item.get("prompt_mode") == "no_think":
                return "/no_think\n"
            break
    return ""
