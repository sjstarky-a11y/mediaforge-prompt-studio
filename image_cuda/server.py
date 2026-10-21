import base64
import io
import os
import threading
from typing import Literal

import torch
from diffusers import StableDiffusionXLPipeline
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field


MODEL_ID = os.getenv(
    "MEDIAFORGE_NVIDIA_IMAGE_MODEL",
    "stabilityai/stable-diffusion-xl-base-1.0",
)
REQUESTED_PROFILE = os.getenv("MEDIAFORGE_NVIDIA_PROFILE", "auto").lower()
REQUESTED_OFFLOAD_MODE = os.getenv(
    "MEDIAFORGE_NVIDIA_OFFLOAD_MODE", "auto"
).lower()

app = FastAPI(title="MediaForge NVIDIA Image Service")
pipeline: StableDiffusionXLPipeline | None = None
pipeline_lock = threading.Lock()
runtime_details: dict[str, object] = {}


def select_memory_profile(vram_gb: float) -> tuple[str, str]:
    if vram_gb < 4.0:
        raise RuntimeError("The CUDA SDXL profile requires at least 4 GB of VRAM.")
    if vram_gb < 6.0:
        return "low_memory", "sequential"
    if vram_gb < 8.0:
        return "balanced", "model"
    return "full", "none"


def resolve_memory_profile(vram_gb: float) -> tuple[str, str]:
    automatic_profile, _ = select_memory_profile(vram_gb)
    profile_rank = {"low_memory": 0, "balanced": 1, "full": 2}
    requested_profile = (
        REQUESTED_PROFILE
        if REQUESTED_PROFILE in profile_rank
        else automatic_profile
    )
    profile = (
        requested_profile
        if profile_rank[requested_profile] <= profile_rank[automatic_profile]
        else automatic_profile
    )
    profile_offload = {
        "low_memory": "sequential",
        "balanced": "model",
        "full": "none",
    }[profile]
    offload_rank = {"sequential": 0, "model": 1, "none": 2}
    requested_offload = (
        REQUESTED_OFFLOAD_MODE
        if REQUESTED_OFFLOAD_MODE in offload_rank
        else profile_offload
    )
    offload_mode = (
        requested_offload
        if offload_rank[requested_offload] <= offload_rank[profile_offload]
        else profile_offload
    )
    return profile, offload_mode


class ImageRequest(BaseModel):
    model: str | None = None
    prompt: str = Field(..., min_length=3, max_length=12000)
    negative_prompt: str = Field(default="", max_length=12000)
    size: Literal["512x512", "768x768", "1024x1024"] = "768x768"
    num_inference_steps: int = Field(default=16, ge=1, le=50)
    rng_seed: int = Field(default=42, ge=0, le=2147483647)
    n: int = Field(default=1, ge=1, le=1)


@app.on_event("startup")
def load_pipeline() -> None:
    global pipeline, runtime_details

    if not torch.cuda.is_available():
        raise RuntimeError("NVIDIA CUDA is not available inside the image container.")

    device = torch.cuda.get_device_properties(0)
    compute_capability = float(f"{device.major}.{device.minor}")
    vram_gb = round(device.total_memory / (1024**3), 1)
    if compute_capability < 6.0:
        raise RuntimeError("The CUDA SDXL profile requires compute capability 6.0 or newer.")

    memory_profile, offload_mode = resolve_memory_profile(vram_gb)
    print(
        f"Loading {MODEL_ID} for {device.name} (compute {compute_capability}, "
        f"{vram_gb} GB VRAM) with profile={memory_profile}, offload={offload_mode}."
    )

    loaded = StableDiffusionXLPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    )
    if memory_profile in {"low_memory", "balanced"}:
        loaded.enable_attention_slicing()
        loaded.enable_vae_slicing()

    if memory_profile == "low_memory":
        loaded.enable_vae_tiling()

    if offload_mode == "sequential":
        loaded.enable_sequential_cpu_offload()
    elif offload_mode == "model":
        loaded.enable_model_cpu_offload()
    else:
        loaded.to("cuda")

    pipeline = loaded
    runtime_details = {
        "device": device.name,
        "compute_capability": compute_capability,
        "vram_gb": vram_gb,
        "memory_profile": memory_profile,
        "offload_mode": offload_mode,
        "display_mode": "GPU" if offload_mode == "none" else "GPU + CPU",
    }


@app.get("/v2/health/ready")
def ready() -> Response:
    if pipeline is None or not torch.cuda.is_available():
        return Response(status_code=503)
    return Response(status_code=200, media_type="application/json")


@app.get("/v3/models")
def models() -> dict:
    return {
        "data": [
            {
                "id": MODEL_ID,
                "backend": "NVIDIA CUDA / Diffusers",
                **runtime_details,
            }
        ]
    }


@app.post("/v3/images/generations")
def generate_image(request: ImageRequest) -> dict:
    if pipeline is None:
        raise HTTPException(status_code=503, detail="CUDA image model is still loading.")

    width, height = (int(value) for value in request.size.split("x", 1))
    generator = torch.Generator(device="cuda").manual_seed(request.rng_seed)

    try:
        with pipeline_lock, torch.inference_mode():
            result = pipeline(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt or None,
                width=width,
                height=height,
                num_inference_steps=request.num_inference_steps,
                guidance_scale=7.0,
                generator=generator,
            )
            image = result.images[0]
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        raise HTTPException(
            status_code=507,
            detail="NVIDIA GPU ran out of memory. MediaForge can retry with a lower-memory profile or use the CPU image fallback.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CUDA image generation failed: {exc}") from exc

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    return {
        "created": 0,
        "data": [{"b64_json": encoded}],
        "model": MODEL_ID,
        "backend": "NVIDIA CUDA / Diffusers",
        "runtime": runtime_details,
        "size": request.size,
        "seed": request.rng_seed,
    }
