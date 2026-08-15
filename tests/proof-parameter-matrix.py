#!/usr/bin/env python3
"""Generate a controlled OVMS/SDXL parameter matrix without changing MediaForge."""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


MODEL = "OpenVINO/stable-diffusion-xl-base-1.0-int8-ov"
BASELINE_PROMPT = (
    "Photorealistic cinematic still of a filmmaker in an abandoned cinema, "
    "walking into the auditorium carrying a small camera bag. Preserve these "
    "explicit scene details: a small camera bag visible over the shoulder. "
    "One coherent real-world moment, realistic anatomy and architecture."
)
BASELINE_NEGATIVE = (
    "extra people, duplicate person, distorted human anatomy, deformed hands, "
    "surreal architecture, warped furniture, duplicate objects, text, watermark"
)
MINIMAL_PROMPT = (
    "Photorealistic full-body cinematic photograph of one filmmaker walking alone "
    "through the center aisle of an abandoned cinema, carrying one small shoulder "
    "camera bag, with empty rows of worn seats and a projection screen visible."
)
MINIMAL_NEGATIVE = "crowd, audience, illustration, painting, cartoon, text, watermark"


@dataclass(frozen=True)
class Case:
    name: str
    purpose: str
    prompt: str
    negative_prompt: str
    size: str
    steps: int
    guidance: float | None = None
    seed: int = 42


CASES = [
    Case("01_baseline_16", "Current Fast Proof checkpoint", BASELINE_PROMPT, BASELINE_NEGATIVE, "768x768", 16),
    Case("02_baseline_20", "Only steps changed to the model-card example", BASELINE_PROMPT, BASELINE_NEGATIVE, "768x768", 20),
    Case("03_baseline_30", "Only steps increased further", BASELINE_PROMPT, BASELINE_NEGATIVE, "768x768", 30),
    Case("04_minimal_prompt", "Only prompt structure simplified", MINIMAL_PROMPT, BASELINE_NEGATIVE, "768x768", 20),
    Case("05_minimal_negative", "Only negative prompt simplified", MINIMAL_PROMPT, MINIMAL_NEGATIVE, "768x768", 20),
    Case("06_guidance_5", "Explicit lower guidance", MINIMAL_PROMPT, MINIMAL_NEGATIVE, "768x768", 20, 5.0),
    Case("07_guidance_9", "Explicit higher guidance", MINIMAL_PROMPT, MINIMAL_NEGATIVE, "768x768", 20, 9.0),
    Case("08_native_1024", "Only resolution changed to native SDXL size", MINIMAL_PROMPT, MINIMAL_NEGATIVE, "1024x1024", 20),
]


def post_json(url: str, payload: dict, timeout: int) -> tuple[dict, float]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    return result, time.perf_counter() - started


def write_report(output: Path, rows: list[dict]) -> None:
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["case", "purpose", "seconds", "size", "steps", "guidance", "seed", "status"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    cards = []
    for row in rows:
        image = row.get("image")
        image_html = f'<img src="{html.escape(image)}" alt="{html.escape(row["case"])}">' if image else "<p>No image</p>"
        cards.append(
            "<article>"
            f"<h2>{html.escape(row['case'])}</h2>{image_html}"
            f"<p><strong>{html.escape(row['purpose'])}</strong></p>"
            f"<p>{row['seconds']} s · {row['size']} · {row['steps']} steps · guidance {row['guidance']} · seed {row['seed']}</p>"
            f"<p>Status: {html.escape(row['status'])}</p>"
            "</article>"
        )
    document = """<!doctype html><html><head><meta charset="utf-8"><title>MediaForge Proof Matrix</title>
<style>body{font-family:system-ui;background:#101014;color:#eee;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}article{background:#1b1b22;border:1px solid #444;border-radius:12px;padding:14px}img{width:100%;height:auto;border-radius:8px}h1{margin-bottom:6px}p{line-height:1.4}</style></head><body>
<h1>MediaForge OVMS/SDXL controlled Proof matrix</h1><p>Compare one changed variable at a time. Do not select a winner from timing alone.</p><main>""" + "".join(cards) + "</main></body></html>"
    (output / "report.html").write_text(document, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011/v3/images/generations")
    parser.add_argument("--output", default="proof-matrix-results")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--start", type=int, default=1, help="First 1-based case to run")
    parser.add_argument("--end", type=int, default=len(CASES), help="Last 1-based case to run")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected = CASES[max(args.start - 1, 0) : min(args.end, len(CASES))]
    rows: list[dict] = []

    print(f"Endpoint: {args.url}")
    print(f"Output:   {output}")
    print(f"Cases:    {len(selected)}\n")

    for index, case in enumerate(selected, start=max(args.start, 1)):
        payload = {
            "model": MODEL,
            "prompt": case.prompt,
            "negative_prompt": case.negative_prompt,
            "size": case.size,
            "num_inference_steps": case.steps,
            "rng_seed": case.seed,
            "n": 1,
        }
        if case.guidance is not None:
            payload["guidance_scale"] = case.guidance

        request_path = output / f"{case.name}.request.json"
        request_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[{index}/{len(CASES)}] {case.name}: {case.purpose}")

        row = {
            "case": case.name,
            "purpose": case.purpose,
            "seconds": "",
            "size": case.size,
            "steps": case.steps,
            "guidance": "server default" if case.guidance is None else case.guidance,
            "seed": case.seed,
            "status": "pending",
            "image": "",
        }
        try:
            response, seconds = post_json(args.url, payload, args.timeout)
            encoded = response["data"][0]["b64_json"]
            image_name = f"{case.name}.png"
            (output / image_name).write_bytes(base64.b64decode(encoded))
            row.update(seconds=f"{seconds:.2f}", status="ok", image=image_name)
            print(f"  completed in {seconds:.2f} seconds")
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            row.update(status=f"error: {exc}")
            print(f"  ERROR: {exc}")
        rows.append(row)
        write_report(output, rows)

    (output / "matrix.json").write_text(
        json.dumps([asdict(case) for case in selected], indent=2), encoding="utf-8"
    )
    print(f"\nOpen this report: {output / 'report.html'}")
    return 0 if all(row["status"] == "ok" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
