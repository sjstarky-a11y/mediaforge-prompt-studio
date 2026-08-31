import base64
import gc
import io
import os
import threading
import time
import uuid
from collections import OrderedDict

import torch
from diffusers import Flux2KleinPipeline
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


MODEL_ID = os.getenv(
    "MEDIAFORGE_HERO_MODEL",
    "black-forest-labs/FLUX.2-klein-4B",
)
DEVICE_MODE = os.getenv("MEDIAFORGE_HERO_DEVICE", "cpu").lower()
HF_HOME = os.getenv("HF_HOME", "/models/huggingface")
MAX_JOBS = 10

app = FastAPI(title="MediaForge Hero Frame Service")


class HeroSetRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=12000)
    seeds: list[int] = Field(default_factory=lambda: [42, 43, 44])


_state_lock = threading.Lock()
_generation_lock = threading.Lock()
_pipeline = None
_active_job_id = None
_service_state = {
    "state": "available",
    "message": "Optional Visual Proof is available. The model downloads on first use.",
}
_jobs: OrderedDict[str, dict] = OrderedDict()


def _set_service_state(state: str, message: str) -> None:
    with _state_lock:
        _service_state["state"] = state
        _service_state["message"] = message


def _update_job(job_id: str, **values) -> None:
    with _state_lock:
        if job_id in _jobs:
            _jobs[job_id].update(values)


def _public_job(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "state": job["state"],
        "message": job["message"],
        "progress": job["progress"],
        "total": job["total"],
        "size": "512x512",
        "images": job["images"],
        "error": job.get("error"),
        "cancel_requested": job.get("cancel_requested", False),
    }


def _load_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    _set_service_state(
        "loading",
        "Downloading FLUX.2 model (approximately 12 GB) and loading it locally. "
        "This happens only on first use.",
    )

    use_cuda = DEVICE_MODE == "cuda"
    if use_cuda and not torch.cuda.is_available():
        raise RuntimeError("CUDA was selected but is not available inside the container.")

    dtype = torch.float16 if use_cuda else torch.bfloat16
    pipeline = Flux2KleinPipeline.from_pretrained(
        MODEL_ID,
        dtype=dtype,
        cache_dir=HF_HOME,
        low_cpu_mem_usage=True,
    )

    if use_cuda:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        if vram_gb < 6:
            pipeline.enable_sequential_cpu_offload(gpu_id=0)
        elif vram_gb < 13:
            pipeline.enable_model_cpu_offload(gpu_id=0)
        else:
            pipeline.to("cuda")
        pipeline.vae.enable_slicing()
        pipeline.vae.enable_tiling()
    else:
        pipeline.to("cpu")

    _pipeline = pipeline
    _set_service_state("ready", "Hero Frame model is ready.")
    return _pipeline


def _generate_job(job_id: str, prompt: str, seeds: list[int]) -> None:
    global _active_job_id
    total = len(seeds)
    job_label = "Proof Frame" if total == 1 else "Hero Frame Set"
    try:
        with _generation_lock:
            _update_job(
                job_id,
                state="loading",
                message="Preparing Hero Frame model. First use may download approximately 12 GB.",
            )
            pipeline = _load_pipeline()
            with _state_lock:
                cancel_requested = _jobs.get(job_id, {}).get("cancel_requested", False)
            if cancel_requested:
                _update_job(
                    job_id,
                    state="cancelled",
                    message=f"{job_label} cancelled before image generation.",
                )
                return
            images = []
            _set_service_state("generating", f"Generating {job_label}.")

            for index, seed in enumerate(seeds, start=1):
                with _state_lock:
                    cancel_requested = _jobs.get(job_id, {}).get("cancel_requested", False)
                if cancel_requested:
                    _update_job(
                        job_id,
                        state="cancelled",
                        message=f"{job_label} stopped after the current completed frame.",
                        images=list(images),
                    )
                    return
                _update_job(
                    job_id,
                    state="generating",
                    message=f"Generating frame {index} of {total}...",
                    progress=index - 1,
                )
                generator_device = "cuda" if DEVICE_MODE == "cuda" else "cpu"
                generator = torch.Generator(device=generator_device).manual_seed(seed)
                started = time.perf_counter()
                image = pipeline(
                    prompt=prompt,
                    height=512,
                    width=512,
                    num_inference_steps=4,
                    guidance_scale=1.0,
                    generator=generator,
                ).images[0]
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                images.append(
                    {
                        "index": index,
                        "seed": seed,
                        "image_b64": base64.b64encode(buffer.getvalue()).decode("ascii"),
                        "seconds": round(time.perf_counter() - started, 2),
                    }
                )
                _update_job(job_id, images=list(images), progress=index)
                gc.collect()
                if DEVICE_MODE == "cuda":
                    torch.cuda.empty_cache()

                with _state_lock:
                    cancel_requested = _jobs.get(job_id, {}).get("cancel_requested", False)
                if cancel_requested:
                    _update_job(
                        job_id,
                        state="cancelled",
                        message=f"{job_label} stopped after the current completed frame.",
                        images=list(images),
                    )
                    return

            _update_job(
                job_id,
                state="completed",
                message=(
                    "Proof Frame is ready."
                    if total == 1
                    else "Choose your Hero Frame."
                ),
                progress=total,
                images=images,
            )
            _set_service_state("ready", "Hero Frame model is ready.")
    except Exception as exc:
        message = f"Hero Frame generation failed: {exc}"
        _update_job(job_id, state="error", message=message, error=str(exc))
        _set_service_state("error", message)
    finally:
        with _state_lock:
            was_cancelled = _jobs.get(job_id, {}).get("state") == "cancelled"
            if _active_job_id == job_id:
                _active_job_id = None
        if was_cancelled and _pipeline is not None:
            _set_service_state("ready", "Hero Frame model is ready.")


@app.get("/v1/status")
def status():
    with _state_lock:
        state = dict(_service_state)
        active_job = _jobs.get(_active_job_id) if _active_job_id else None
    return {
        **state,
        "ready": _pipeline is not None,
        "model": MODEL_ID,
        "device": DEVICE_MODE,
        "download_gb_approx": 12,
        "size": "512x512",
        "frame_options": [1, 3],
        "active_job": _public_job(dict(active_job)) if active_job else None,
    }


@app.post("/v1/hero-sets")
def create_hero_set(request: HeroSetRequest):
    global _active_job_id
    total = len(request.seeds)
    if total not in {1, 3} or len(set(request.seeds)) != total:
        raise HTTPException(status_code=422, detail="One or three unique seeds are required.")
    if any(seed < 0 or seed > 2147483647 for seed in request.seeds):
        raise HTTPException(status_code=422, detail="Seeds must be between 0 and 2147483647.")
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "state": "queued",
        "message": "Proof Frame queued." if total == 1 else "Hero Frame Set queued.",
        "progress": 0,
        "total": total,
        "images": [],
        "error": None,
        "cancel_requested": False,
    }
    with _state_lock:
        if _active_job_id is not None:
            active_job = _jobs.get(_active_job_id)
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Another Visual Proof job is already being generated.",
                    "job": _public_job(dict(active_job)) if active_job else None,
                },
            )
        _active_job_id = job_id
        _jobs[job_id] = job
        while len(_jobs) > MAX_JOBS:
            _jobs.popitem(last=False)

    worker = threading.Thread(
        target=_generate_job,
        args=(job_id, request.prompt, request.seeds),
        daemon=True,
    )
    worker.start()
    return JSONResponse(status_code=202, content=_public_job(job))


@app.get("/v1/hero-sets/{job_id}")
def hero_set_status(job_id: str):
    with _state_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Hero Frame Set job not found.")
        return _public_job(dict(job))


@app.post("/v1/hero-sets/{job_id}/cancel")
def cancel_hero_set(job_id: str):
    with _state_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Hero Frame Set job not found.")
        if job["state"] in {"completed", "cancelled", "error"}:
            return _public_job(dict(job))
        job["cancel_requested"] = True
        job["state"] = "cancelling"
        job["message"] = "Stopping after the current frame finishes..."
        return _public_job(dict(job))
