#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-v0.3}"
OUTPUT="${2:-$ROOT/dist}"

python3 "$ROOT/scripts/build_release.py" \
  --version "$VERSION" \
  --output "$OUTPUT"
