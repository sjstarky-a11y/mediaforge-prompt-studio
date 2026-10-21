#!/usr/bin/env python3
"""Build or verify the public package checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
try:
    from .public_sources import is_private_path
except ImportError:
    from public_sources import is_private_path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "runtime" / "PACKAGE-MANIFEST.json"
EXCLUDED_FILES = {
    Path(".env"),
    Path("runtime/hardware-profile.json"),
    Path("runtime/runtime-profile.json"),
    Path("runtime/install-log.txt"),
    Path("runtime/install-linux.log"),
    Path("runtime/doctor-report.txt"),
    Path("runtime/PACKAGE-MANIFEST.json"),
}
EXCLUDED_PARTS = {".git", "data", "dist", "local", "runtime", "__pycache__", ".pytest_cache"}


def canonical_content(content: bytes) -> bytes:
    """Normalize UTF-8 text to Git's LF representation before hashing."""
    if b"\x00" in content:
        return content
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def build_manifest() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    public_files = []
    for directory, directories, files in os.walk(ROOT):
        relative_directory = Path(directory).relative_to(ROOT)
        directories[:] = [name for name in directories
                           if not is_private_path(relative_directory / name)
                           and name not in EXCLUDED_PARTS
                           and not (Path(directory) / name).is_symlink()]
        public_files.extend(Path(directory) / name for name in files)
    for path in sorted(public_files, key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT)
        if path.is_symlink() or is_private_path(relative) or relative in EXCLUDED_FILES or any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".zip"}:
            continue
        content = canonical_content(path.read_bytes())
        entries.append({
            "file": relative.as_posix(),
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build_manifest()
    if args.check:
        try:
            actual = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise SystemExit("Package manifest is missing or invalid.")
        if actual != expected:
            raise SystemExit("Package manifest is out of date. Run: python3 scripts/build_manifest.py")
        print("Package manifest is current.")
        return
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(expected)} entries to {MANIFEST}")


if __name__ == "__main__":
    main()
