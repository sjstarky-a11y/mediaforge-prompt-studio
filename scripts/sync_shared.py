"""Keep pure shared SoloHost modules generated from the main application source."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ("fidelity_concepts.py", "model_catalog.py")


def sync(check=False):
    differences = []
    for name in SHARED:
        source = ROOT / "app" / name
        destination = ROOT / "solohost" / "app" / name
        if not destination.exists() or source.read_bytes() != destination.read_bytes():
            differences.append(name)
            if not check:
                destination.write_bytes(source.read_bytes())
    if check and differences:
        raise SystemExit("Shared module drift: " + ", ".join(differences))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    sync(parser.parse_args().check)
