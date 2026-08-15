#!/usr/bin/env python3
"""Build or verify the public package checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


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
EXCLUDED_PARTS = {".git", "data", "__pycache__", ".pytest_cache"}


def build_manifest() -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative in EXCLUDED_FILES or any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".zip"}:
            continue
        content = path.read_bytes()
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
