"""Run a reproducible public Proof Frame scenario; evidence stays local."""
import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-url", default="http://127.0.0.1:18889")
    parser.add_argument("--quality", choices=("fast", "quality"), default="fast")
    parser.add_argument("--ready-timeout", type=int, default=600)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "runtime"
    output.mkdir(exist_ok=True)
    prompt = "A single red ceramic cup on a wooden table beside a window, soft daylight, realistic photograph."
    deadline = time.monotonic() + args.ready_timeout
    while True:
        try:
            with urllib.request.urlopen(args.app_url.rstrip("/") + "/api/image-status", timeout=3) as response:
                if json.load(response).get("ready") is True:
                    break
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("The image service did not become ready within the test timeout.")
        time.sleep(2)
    payload = dict(source_prompt=prompt, final_prompt=prompt, mode="cinematic",
                   aspect_ratio="16:9", quality=args.quality, rng_seed=42)
    request = urllib.request.Request(args.app_url.rstrip("/") + "/api/proof-frame",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.load(response)
    elapsed = round(time.perf_counter() - started, 2)
    # The response intentionally remains in the private local runtime directory.
    (output / f"proof-{args.quality}-response.json").write_text(json.dumps(result), encoding="utf-8")
    encoded = result.get("image_base64") or result.get("image_b64") or result.get("image", "")
    if isinstance(encoded, str) and encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[1]
    if not encoded:
        raise RuntimeError("The application did not return a proof image.")
    path = output / f"proof-{args.quality}.png"
    path.write_bytes(base64.b64decode(encoded))
    receipt = {"scenario": "public-red-cup", "seed": 42, "quality": args.quality,
               "elapsed_seconds": elapsed, "image_bytes": path.stat().st_size}
    (output / f"proof-{args.quality}-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
