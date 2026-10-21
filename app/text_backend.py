"""Independent local text providers with an explicit, reported CPU fallback."""
import os
import httpx
from model_catalog import build_model_inventory, parse_dmr_model_ids

PUBLIC_INTEL_MODEL = "OpenVINO/Qwen2.5-7B-Instruct-int4-ov"


class TextBackend:
    def __init__(self, dmr_url, management_url, dmr_model, api_key, *,
                 provider=None, intel_url=None, intel_model=None, transport=None):
        self.dmr_url = dmr_url.rstrip("/")
        self.management_url = management_url.rstrip("/")
        self.dmr_model = dmr_model
        self.api_key = api_key
        self.provider = provider or os.getenv("MEDIAFORGE_ACTIVE_TEXT_RUNTIME", "dmr")
        self.intel_url = (intel_url or os.getenv("MEDIAFORGE_INTEL_TEXT_URL", "http://text-intel:8000/v3")).rstrip("/")
        self.intel_model = intel_model or os.getenv("MEDIAFORGE_INTEL_TEXT_MODEL", PUBLIC_INTEL_MODEL)
        self.transport = transport

    @property
    def default_model(self):
        return self.intel_model if self.provider == "intel" else self.dmr_model

    @property
    def readiness_url(self):
        return self.intel_url.rsplit("/v3", 1)[0] + "/v2/health/ready"

    async def intel_ready(self, client):
        try:
            response = await client.get(self.readiness_url, timeout=2)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def complete(self, model, payload):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=180, transport=self.transport) as client:
            if self.provider == "intel" and model == self.intel_model:
                if await self.intel_ready(client):
                    response = await client.post(self.intel_url + "/chat/completions", json=payload)
                    response.raise_for_status()
                    return response.json(), self.intel_model, "Intel GPU / OpenVINO"
                # The configured default remains usable during first download.
                payload = {**payload, "model": self.dmr_model}
                backend = "Docker Model Runner (Intel text model preparing)"
            else:
                backend = "Docker Model Runner"
            response = await client.post(self.dmr_url + "/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            return response.json(), payload["model"], backend

    async def inventory(self, catalog):
        ids = []
        ready = False
        async with httpx.AsyncClient(timeout=5, transport=self.transport) as client:
            for url in dict.fromkeys((self.dmr_url + "/models", self.management_url + "/models")):
                try:
                    response = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
                    response.raise_for_status()
                    ids = parse_dmr_model_ids(response.json())
                    if ids:
                        break
                except httpx.HTTPError:
                    pass
            if self.provider == "intel":
                ready = await self.intel_ready(client)
                ids.insert(0, self.intel_model)
        result = build_model_inventory(ids, self.default_model, catalog, assume_default_installed=False)
        result["source"] = "local text providers"
        result["warning"] = "Intel text model is preparing. Requests temporarily use the local Model Runner fallback." if self.provider == "intel" and not ready else None
        for item in result["installed"]:
            if item["id"] == self.intel_model and self.provider == "intel":
                item["backend"] = "Intel GPU / OpenVINO"
                item["ready"] = ready
                item["installed"] = ready
                item["family"] = "Intel OpenVINO text"
                item["profile"] = "Intel GPU"
                item["display_name"] = "Intel GPU · Local Prompt Doctor" + ("" if ready else " · preparing")
        return result
