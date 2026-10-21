"""System endpoints independent of prompt-processing and model workflows."""
import httpx
from fastapi import APIRouter
from runtime_status import load_runtime_profile


def system_router(app_name, model_name, dmr_url, hero_backend, image_backend,
                  image_ready_url, preparing_message, text_backend=None):
    router = APIRouter()

    @router.get("/health")
    def health():
        runtime = load_runtime_profile()
        return {"status": "ok", "app": app_name, "model": model_name,
                "dmr_url": dmr_url, "runtime_profile": runtime["profile"],
                "runtime_mode": runtime["display_mode"],
                "gpu_acceleration": runtime["gpu_acceleration"],
                "llm_runtime": runtime["llm"]["runtime"],
                "image_runtime": runtime["image"]["runtime"],
                "hero_runtime": hero_backend, "runtime": runtime}

    async def image_ready():
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                response = await client.get(image_ready_url)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    @router.get("/runtime")
    async def runtime():
        profile = load_runtime_profile()
        profile["image"]["model_ready"] = await image_ready()
        if text_backend and text_backend.provider == "intel":
            async with httpx.AsyncClient(timeout=2) as client:
                profile["llm"]["model_ready"] = await text_backend.intel_ready(client)
        return profile

    @router.get("/api/image-status")
    async def image_status():
        ready = await image_ready()
        return {"ready": ready, "state": "ready" if ready else "preparing",
                "message": "Visual Proof model is ready." if ready else preparing_message,
                "backend": image_backend}

    return router
