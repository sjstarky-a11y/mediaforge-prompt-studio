"""Host-independent runtime tools, executable in the application container."""
import argparse
import json
from pathlib import Path

from .policy import select_backend, selection_env, select_text_runtime
from .profile import build_profile
from .diagnostics import shareable_report


def read_json(path):
    try:
        value = Path(path).read_text(encoding="utf-8-sig")
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def read_env(path):
    result = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
    return result


def update_env(path, values):
    path = Path(path)
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    result, written = [], set()
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in values and not line.lstrip().startswith("#"):
            if key not in written:
                result.append(key + "=" + str(values[key]))
                written.add(key)
        else:
            result.append(line)
    result.extend(key + "=" + str(value) for key, value in values.items() if key not in written)
    path.write_text("\n".join(result) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("select", "profile", "diagnostics"))
    parser.add_argument("--root", default="/workspace")
    parser.add_argument("--mode", default="auto")
    parser.add_argument("--transport", choices=("linux", "wsl"), default="linux")
    args = parser.parse_args()
    root = Path(args.root)
    runtime = root / "runtime"
    runtime.mkdir(exist_ok=True)
    if args.command == "select":
        try:
            selection = select_backend(args.mode, read_json(runtime / "nvidia-probe.json"), read_json(runtime / "intel-probe.json"))
            env = read_env(root / ".env")
            text_runtime = select_text_runtime(selection, env.get("MEDIAFORGE_TEXT_RUNTIME", "auto"))
        except ValueError as exc:
            parser.exit(2, str(exc) + "\n")
        profiles = [p.strip() for p in env.get("COMPOSE_PROFILES", "").split(",") if p.strip() and p.strip() != "intel-text"]
        if text_runtime == "intel":
            profiles.append("intel-text")
        update_env(root / ".env", {**selection_env(selection, args.transport),
                                   "MEDIAFORGE_ACTIVE_TEXT_RUNTIME": text_runtime,
                                   "COMPOSE_PROFILES": ",".join(profiles)})
        selection["text_runtime"] = text_runtime
        (runtime / "selection.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
        print(f"Selected image runtime: {selection['selected']}. {selection['reason']}")
    elif args.command == "diagnostics":
        report = shareable_report(read_json(runtime / "runtime-profile.json"))
        (runtime / "doctor-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    else:
        status_path = runtime / "dmr-status.txt"
        status = status_path.read_text(encoding="utf-8-sig") if status_path.exists() else ""
        profile = build_profile(read_env(root / ".env"), read_json(runtime / "hardware-profile.json"), status, read_json(runtime / "selection.json"))
        (runtime / "runtime-profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        print(profile["summary"])


if __name__ == "__main__":
    main()
