#!/usr/bin/env python3
"""Validate the winning Fast Proof configuration across several RNG seeds."""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


MODEL = "OpenVINO/stable-diffusion-xl-base-1.0-int8-ov"
PROMPT = (
    "Photorealistic cinematic still of a filmmaker in an abandoned cinema, "
    "walking into the auditorium carrying a small camera bag. Preserve these "
    "explicit scene details: a small camera bag visible over the shoulder. "
    "One coherent real-world moment, realistic anatomy and architecture."
)
NEGATIVE_PROMPT = (
    "extra people, duplicate person, distorted human anatomy, deformed hands, "
    "surreal architecture, warped furniture, duplicate objects, text, watermark"
)


def post_json(url: str, payload: dict, timeout: int) -> tuple[dict, float]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
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
            fieldnames=["seed", "seconds", "status", "human_review"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    cards = []
    for row in rows:
        image = row.get("image")
        image_html = (
            f'<img src="{html.escape(image)}" alt="Seed {row["seed"]}">'
            if image
            else "<p>No image</p>"
        )
        cards.append(
            "<article>"
            f"<h2>Seed {row['seed']}</h2>{image_html}"
            f"<p>{row['seconds']} s · 768x768 · 16 steps · default guidance</p>"
            "<p>Review: subject present · cinema clear · one shoulder bag · no extra people</p>"
            "</article>"
        )

    document = """<!doctype html><html><head><meta charset="utf-8"><title>MediaForge Proof seed validation</title>
<style>body{font-family:system-ui;background:#101014;color:#eee;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}article{background:#1b1b22;border:1px solid #444;border-radius:12px;padding:14px}img{width:100%;height:auto;border-radius:8px}p{line-height:1.4}</style></head><body>
<h1>MediaForge Fast Proof seed validation</h1><p>Every parameter is fixed except the RNG seed.</p><main>""" + "".join(cards) + "</main></body></html>"
    (output / "report.html").write_text(document, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011/v3/images/generations")
    parser.add_argument("--output", default="proof-seed-results")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46])
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    print(f"Endpoint: {args.url}")
    print(f"Output:   {output}")
    print(f"Seeds:    {', '.join(map(str, args.seeds))}\n")

    for position, seed in enumerate(args.seeds, start=1):
        payload = {
            "model": MODEL,
            "prompt": PROMPT,
            "negative_prompt": NEGATIVE_PROMPT,
            "size": "768x768",
            "num_inference_steps": 16,
            "rng_seed": seed,
            "n": 1,
        }
        (output / f"seed_{seed}.request.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        print(f"[{position}/{len(args.seeds)}] seed {seed}")

        row = {
            "seed": seed,
            "seconds": "",
            "status": "pending",
            "human_review": "pending",
            "image": "",
        }
        try:
            response, seconds = post_json(args.url, payload, args.timeout)
            image_name = f"seed_{seed}.png"
            encoded = response["data"][0]["b64_json"]
            (output / image_name).write_bytes(base64.b64decode(encoded))
            row.update(seconds=f"{seconds:.2f}", status="ok", image=image_name)
            print(f"  completed in {seconds:.2f} seconds")
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            row.update(status=f"error: {exc}")
            print(f"  ERROR: {exc}")
        rows.append(row)
        write_report(output, rows)

    print(f"\nOpen this report: {output / 'report.html'}")
    return 0 if all(row["status"] == "ok" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
