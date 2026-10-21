"""Public local text scenario; optionally require actual Intel inference."""
import argparse
import json
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-url", default="http://127.0.0.1:18889")
    parser.add_argument("--language", choices=("English", "Croatian"), default="English")
    parser.add_argument("--require-intel", action="store_true")
    args = parser.parse_args()
    if args.require_intel:
        deadline = time.monotonic() + 600
        while True:
            try:
                with urllib.request.urlopen(args.app_url + "/runtime", timeout=5) as response:
                    profile = json.load(response)
                if profile["llm"].get("model_ready") is True:
                    break
            except (OSError, ValueError, KeyError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("Intel text model did not become ready.")
            time.sleep(2)
    source = ("A red ceramic cup stands on a wooden table beside a window in soft daylight."
              if args.language == "English" else
              "Crvena keramička šalica stoji na drvenom stolu pokraj prozora. Meko dnevno svjetlo.")
    payload = dict(user_input=source, mode="improve", language=args.language, aspect_ratio="16:9")
    request = urllib.request.Request(args.app_url + "/api/generate", data=json.dumps(payload).encode(),
                                    headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    elapsed = round(time.perf_counter() - started, 2)
    if not result.get("result") or args.require_intel and result.get("backend") != "Intel GPU / OpenVINO":
        raise RuntimeError("Requested Intel text inference was not confirmed.")
    output = Path(__file__).resolve().parents[1] / "runtime"
    output.mkdir(exist_ok=True)
    (output / f"text-{args.language.lower()}-response.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    receipt = {"scenario": "public-red-cup", "language": args.language, "backend": result.get("backend"),
               "elapsed_seconds": elapsed, "output_characters": len(result["result"]),
               "fidelity": result.get("fidelity", {}).get("status")}
    (output / f"text-{args.language.lower()}-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
