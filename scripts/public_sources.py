"""Files excluded from public source manifests and downloadable packages."""
from pathlib import Path


def is_private_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    if any(part in {".git", ".venv", "venv", "runtime", "data", "local", "dist", "__pycache__", ".pytest_cache"} for part in parts):
        return True
    if any(part.startswith(".env") and part != ".env.example" for part in parts):
        return True
    if any(part.endswith((".local.json", ".local.yml", ".local.yaml")) for part in parts):
        return True
    return path.suffix.lower() in {".log", ".pem", ".key", ".pyc", ".zip", ".gz", ".safetensors", ".bin", ".pt", ".onnx"}
