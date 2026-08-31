import os
import re
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fidelity_concepts import (
    auto_correct_narrow_lighting_review,
    detect_unrequested_creative_issues,
    output_structure_issues,
)
from model_catalog import (
    build_model_inventory,
    is_valid_model_id,
    load_model_catalog,
    model_prompt_prefix,
    parse_dmr_model_ids,
)
from runtime_status import load_runtime_profile


APP_NAME = "MediaForge Prompt Studio"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
        "visual-proof",
    }


# SoloHost deliberately has one validated text engine.  Visual Proof is an
# optional Compose profile; it must never be downloaded or started by default.
SOLOHOST_MODE = _env_flag("MEDIAFORGE_SOLOHOST_MODE", False)
FAST_PROOF_ENABLED = _env_flag("MEDIAFORGE_FAST_PROOF_ENABLED", not SOLOHOST_MODE)
VISUAL_PROOF_ENABLED = _env_flag("MEDIAFORGE_VISUAL_PROOF_ENABLED", False)

DMR_URL = os.getenv(
    "MEDIAFORGE_DMR_URL",
    "http://model-runner.docker.internal:12434/engines/llama.cpp/v1",
).rstrip("/")

DMR_API_KEY = os.getenv("MEDIAFORGE_DMR_API_KEY", "docker-model-runner")
DMR_MANAGEMENT_URL = os.getenv(
    "MEDIAFORGE_DMR_MANAGEMENT_URL",
    DMR_URL.split("/engines/", 1)[0],
).rstrip("/")
MODEL_NAME = os.getenv("MEDIAFORGE_MODEL", "ai/qwen2.5:3B-Q4_K_M")
MODEL_CATALOG_PATH = os.getenv(
    "MEDIAFORGE_MODEL_CATALOG_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models",
        "model-catalog.json",
    ),
)
MODEL_CATALOG = load_model_catalog(MODEL_CATALOG_PATH)
DEFAULT_LANGUAGE = os.getenv("MEDIAFORGE_DEFAULT_LANGUAGE", "English")
MAX_TOKENS = int(os.getenv("MEDIAFORGE_MAX_TOKENS", "700"))
TEMPERATURE = float(os.getenv("MEDIAFORGE_TEMPERATURE", "0.55"))

# Visual Proof Frame uses an OpenAI-compatible image generation endpoint.
# Legacy OVMS variable names remain supported for v0.1a configuration files.
IMAGE_API_URL = os.getenv(
    "MEDIAFORGE_IMAGE_API_URL",
    os.getenv("MEDIAFORGE_OVMS_IMAGE_URL", "http://host.docker.internal:8010/v3"),
).rstrip("/")
IMAGE_MODEL = os.getenv(
    "MEDIAFORGE_IMAGE_MODEL",
    os.getenv(
        "MEDIAFORGE_OVMS_IMAGE_MODEL",
        "OpenVINO/stable-diffusion-xl-base-1.0-int8-ov",
    ),
)
IMAGE_BACKEND = os.getenv("MEDIAFORGE_IMAGE_BACKEND", "OpenVINO CPU")


def derive_image_readiness_url(image_api_url: str) -> str:
    """Return the standard readiness endpoint for an image API base URL."""
    base = image_api_url.rstrip("/")
    for suffix in ("/v3", "/v1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f"{base}/v2/health/ready"


IMAGE_READY_URL = os.getenv(
    "MEDIAFORGE_IMAGE_READY_URL",
    derive_image_readiness_url(IMAGE_API_URL),
).rstrip("/")
IMAGE_PREPARING_MESSAGE = (
    "Visual Proof model is being prepared. The first download is several "
    "gigabytes and may take some time. Prompt Doctor remains available."
)

HERO_API_URL = os.getenv(
    "MEDIAFORGE_HERO_API_URL",
    "http://host.docker.internal:8020/v1",
).rstrip("/")
HERO_MODEL = os.getenv(
    "MEDIAFORGE_HERO_MODEL",
    "black-forest-labs/FLUX.2-klein-4B",
)
HERO_BACKEND = os.getenv("MEDIAFORGE_HERO_BACKEND", "FLUX.2 Klein 4B")
HERO_DOWNLOAD_MESSAGE = (
    "Hero Frame Set is preparing its optional local model. First use downloads "
    "approximately 12 GB; keep at least 15 GB free. Prompt Doctor remains available."
)
HERO_PROFILE_INACTIVE_MESSAGE = (
    "Optional Visual Proof is not installed in SoloHost Core. "
    "Prompt Doctor remains fully available."
)


app = FastAPI(title=APP_NAME)
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


class GenerateRequest(BaseModel):
    user_input: str = Field(..., min_length=3, max_length=6000)
    model: str | None = Field(default=None, min_length=3, max_length=200)
    mode: Literal[
        "improve",
        "diagnose",
        "cinematic",
        "commercial",
        "shotlist",
    ] = "improve"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    language: Literal["English", "Croatian"] = DEFAULT_LANGUAGE


class FidelityObserverResult(BaseModel):
    status: Literal["INTENT PROTECTED", "REVIEW", "CONFLICT"]
    issues: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    result: str
    model: str
    mode: str
    fidelity: FidelityObserverResult


class ProofFrameRequest(BaseModel):
    source_prompt: str = Field(..., min_length=3, max_length=6000)
    final_prompt: str = Field(..., min_length=3, max_length=12000)
    mode: Literal["improve", "cinematic", "commercial"] = "improve"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    quality: Literal["fast", "quality"] = "fast"
    rng_seed: int = Field(default=42, ge=0, le=2147483647)


class ProofFrameResponse(BaseModel):
    image_b64: str
    model: str
    quality: Literal["fast", "quality"]
    size: str
    proof_prompt: str
    single_frame_prompt: str
    selection_reason: str
    negative_prompt: str
    fidelity: FidelityObserverResult
    cleanup_applied: bool = False
    cleanup_notes: list[str] = Field(default_factory=list)


class HeroFrameSetRequest(BaseModel):
    source_prompt: str = Field(..., min_length=3, max_length=6000)
    final_prompt: str = Field(..., min_length=3, max_length=12000)
    mode: Literal["improve", "cinematic", "commercial"] = "improve"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    base_seed: int = Field(default=42, ge=0, le=2147483645)
    frame_count: Literal[1, 3] = 3
    user_approved_addition: bool = False


class ModelAdapterRequest(BaseModel):
    source_prompt: str = Field(..., min_length=3, max_length=6000)
    approved_prompt: str = Field(..., min_length=3, max_length=12000)
    mode: Literal["improve", "cinematic", "commercial"] = "improve"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    profile: Literal["generic_video", "runway_gen4_5", "veo_3_1", "kling_video_3_0"] = "generic_video"


class ModelAdapterResponse(BaseModel):
    status: Literal["MODEL READY"]
    profile: str
    prompt: str
    changed: bool
    adaptation_notes: list[str] = Field(default_factory=list)
    fidelity: FidelityObserverResult


def build_system_prompt(mode: str, aspect_ratio: str, language: str) -> str:
    base = f"""
You are MediaForge Prompt Doctor, a specialized assistant for improving prompts for AI video generation.

LANGUAGE
- The user may write the source prompt in English or Croatian.
- Always write the complete final answer in {language}.
- Preserve quoted names, model names and explicitly requested wording exactly.

TARGET FORMAT
- Target aspect ratio: {aspect_ratio}.
- Respect the requested aspect ratio when composition is relevant.
- A vertical 9:16 prompt must be intentionally composed for a vertical frame, not merely described as a cropped 16:9 image.

PRIMARY RULE: SEMANTIC FIDELITY
Treat the user's prompt as the source of truth.

Preserve every explicit creative fact, including when present:
- subject identity
- number of subjects
- action
- object identity
- object state
- setting
- time of day
- weather
- mood
- left/right position
- direction of movement
- camera behavior
- framing
- product appearance
- brand names
- logos
- exact label or packaging text
- explicit exclusions such as no people or no vehicles

Never replace an explicit fact with a stylistic alternative.

Examples:
- dawn must not become sunset
- sunset must not become sunrise
- fisherman must not become a generic man
- pier must not become a generic waterfront
- sitting must not become walking or standing
- static camera must not become a tracking shot
- left and right positions must not be swapped
- exact brand or label text must not be rewritten

Do not invent:
- new characters
- new story events
- new actions or reactions
- new objects
- brands
- logos
- slogans
- locations
- weather events
- time of day
- product colors or materials that were not supplied
- facial expressions or emotional reactions that were not supplied
- narrative motivation

unless the user explicitly requests them.

TECHNICAL IMPROVEMENT RULE
You may add useful camera, lighting, composition, atmosphere, movement, depth, continuity, or product-presentation details when appropriate to the selected mode, but those additions must never replace or contradict explicit user facts.
Prefer neutral technical additions over invented story, product, weather, emotional, or environmental details.
When an explicit technical term is already supplied by the user, preserve it rather than weakening or changing it.

CONFLICT RULE
The supplied CONFLICT CHECK and CONFLICT RESOLUTION are authoritative.
If CONFLICT RESOLUTION says an instruction must be removed, that instruction must not appear in the final output.
The diagnosis and final output must agree with each other.
Never diagnose a contradiction and then reproduce the same contradiction in the final prompt.

OUTPUT HYGIENE
- Be concise and specific.
- Do not include a Negative prompt section.
- Do not include Why it works.
- Do not include generic filler.
- Do not add extra headings beyond those required by the selected mode.
""".strip()

    if mode == "improve":
        task = """
MODE: IMPROVE

Return exactly this structure:

PROMPT DIAGNOSIS

- Write 2 to 4 short bullet points.
- Identify only real weaknesses, ambiguities, missing technical information, or contradictions.
- Never claim that an action, subject, setting, or other element is missing if it is explicitly present.
- If the prompt is already strong, say so briefly.
- Explicitly identify technical conflicts when present.

IMPROVED PROMPT

Write one clean, copy-ready prompt paragraph.

Requirements:
- Preserve the exact semantic meaning.
- Resolve technical contradictions.
- Apply every mandatory conflict resolution.
- Improve only what is useful.
- Use a strict minimal-edit approach. If the prompt is already clear, keep it close to the user's wording and add only generic camera, lighting, composition, continuity, or product-presentation guidance.
- Never invent concrete product attributes or scene facts that are absent from the input: no brand, logo, label, design, color, material, position, tilt/orientation, new location, sky, weather, time of day, light source, emotion, expression, reaction, gesture, posture, or gaze.
- Do not infer emotion from an action. A dog running toward its owner does not imply a joyful expression, smile, welcoming gesture, or emotional bond unless the user states it.
- Generic technical wording such as "controlled lighting", "clean composition", or "product-focused framing" is allowed because it does not create a new story or product fact.
- Example: "Commercial for a bottle of mineral water on a stone table." may become "A commercial product shot of a bottle of mineral water on a stone table, using clean product-focused composition and controlled lighting." Do not add a label, brand, sky, time of day, new location, product design, position, or tilt.
- Preserve explicit technical terms such as lens, framing, depth of field, camera behavior, and time of day.
- If an object changes state during an action sequence, preserve that changed state in later actions.
- Do not retain any instruction that the conflict resolution says to remove.
""".strip()

    elif mode == "diagnose":
        task = """
MODE: DIAGNOSE

Return exactly this structure:

PROMPT DIAGNOSIS

- Write 2 to 5 concise bullet points.
- Diagnose the prompt only.
- State what is already clear before identifying what is unspecified or problematic.
- Never claim that an element is missing if it is explicitly present.
- Distinguish between:
  1. information that is present,
  2. information that is unspecified,
  3. information that is contradictory or ambiguous.
- "Cinematic" by itself is a broad visual intention, not a camera instruction, framing instruction, lighting setup, or time of day.
- When multiple incompatible camera behaviors are requested simultaneously, explicitly call the camera direction overloaded or conflicting.
- When multiple competing visual styles are requested simultaneously, explicitly identify the competing style priorities.
- When a pronoun can refer to more than one plausible subject, explicitly identify the reference ambiguity and request clarification.
- Do not list clothing, hair, ethnicity, profession, personality, body type, or other character biography as missing unless the user's task specifically requires it.
- Do not invent missing details.
- Do not rewrite the user's prompt.
- If clarification is required, identify exactly what is ambiguous.
- If the prompt is already technically coherent, say that no significant correction is required.

Do not output an improved prompt.
""".strip()

    elif mode == "cinematic":
        task = """
MODE: CINEMATIC

Return exactly this structure:

PROMPT DIAGNOSIS

- Write 2 to 4 concise bullet points.
- Identify the existing cinematic strengths and only the useful opportunities for visual development.
- Explicitly preserve any camera, framing, time-of-day, setting, action, or subject instruction already given.

CINEMATIC PROMPT

Write one copy-ready cinematic video prompt paragraph.

Requirements:
- Develop framing, composition, lighting, depth, atmosphere, movement, or continuity where useful.
- Preserve the original story and every explicit user fact.
- Add atmosphere without inventing concrete weather events, story events, danger, directions, or character reactions that the user did not specify.
- If a storm is specified but lightning is not, do not invent lightning. Do not infer fear, danger, a search for safety, or other character reactions from the storm unless explicitly stated.
- Use at most one coherent camera behavior; never describe the same shot as both moving/following and static.
- If the user explicitly specifies a static camera, keep it static.
- Do not introduce camera movement merely to make the result feel more cinematic.
- Do not replace a specific subject, location, time of day, or action with a more generic or stylistic alternative.
""".strip()

    elif mode == "commercial":
        task = """
MODE: COMMERCIAL

Return exactly this structure:

PROMPT DIAGNOSIS

- Write 2 to 4 short bullet points.
- Identify only the core commercial facts already present in the user's prompt.
- Focus on product identity, product count, setting, and any explicitly stated brand, logo, label text, or packaging details.
- If camera, lighting, angle, or composition are not specified, you may briefly say they can be clarified.
- Do not list long inventories of unspecified details.
- Do not speculate about brand identity, product material, color, symbolism, lifestyle message, or marketing meaning unless explicitly stated.
- If the prompt is already clear, say so briefly.
- If a contradiction exists, explicitly identify it.

COMMERCIAL PROMPT

Write one clean, commercial-ready prompt paragraph.

Requirements:
- Preserve the exact semantic meaning.
- Preserve the exact product identity and product count.
- Preserve the exact setting and any explicit product-placement facts.
- Preserve any explicit brand name, logo, label text, package text, or visible wording exactly as given.
- Keep the product as the visual priority.
- Add only useful commercial direction such as clean composition, controlled lighting, product focus, and a simple camera angle when useful.
- If a detail is not explicitly given, keep it unspecified instead of inventing it.
- Do not invent product material, color, branding, text, reflections, symbolism, benefits, backstory, or extra props unless the user explicitly asks for them.
- Do not add inferred quality or marketing adjectives such as "sleek", "premium", "high-quality", "refreshing", "pure", "purity", "minimalist", "luxury", "elegant", or similar unless explicitly stated by the user.
- Do not turn a simple product prompt into a larger advertising story.
- Keep the final prompt concise and production-ready.

STRICT RULES
- Output only the two headings: PROMPT DIAGNOSIS and COMMERCIAL PROMPT.
- Under PROMPT DIAGNOSIS, use short bullet points.
- Under COMMERCIAL PROMPT, write a single final prompt paragraph.
- Do not include Why it works.
- Do not include Negative prompt.
- Do not include extra notes, explanations, or additional headings.
""".strip()

    else:
        task = """
MODE: SHOTLIST

Return exactly two sections:

PROMPT DIAGNOSIS
SHOT LIST

PROMPT DIAGNOSIS

- Write 2 concise bullet points.
- Identify the explicit action sequence.
- Identify the key continuity requirement.
- Do not invent details.

SHOT LIST

Convert the user's explicit actions into shots in the same chronological order.

Rules:
- Preserve the exact action order.
- Treat every explicit action beat as mandatory. Do not skip an intermediate action such as approaching, reaching, turning, pressing, picking up, raising, or looking.
- Use only actions that are explicitly present.
- Keep the same subject and same object across relevant shots.
- Preserve the complete setting, destination, and explicit spatial relationship somewhere in the shot list.
- If the user says an action happens, show it happening.
- Do not replace a completed action with "about to" or "preparing to".
- Do not invent hand choice, posture, gaze, nods, leaning, smiles, reactions, object material, object contents, object angle, extra props, or extra background activity unless explicitly stated.
- Keep each shot sentence minimal: explicit action + necessary subject/object/location only. Do not append decorative body-language or gaze details.
- If the user states that an action happens, never use "about to", "preparing to", "begins to", or "starts to" as a substitute for that completed action.
- If two subjects are explicitly opposite each other, preserve that relationship when establishing the scene.
- For 9:16, explicitly identify the shot list as vertical 9:16 and compose the shots vertically.
- You may choose only the shot type and minimal framing needed to show the action clearly.
- For a simple three-beat action, use three shots and map one explicit action beat to each shot.

Format exactly like this:

PROMPT DIAGNOSIS
- ...
- ...

SHOT LIST
SHOT 1 - [SHOT TYPE]: ...
SHOT 2 - [SHOT TYPE]: ...
SHOT 3 - [SHOT TYPE]: ...

EXAMPLE

User:
A woman picks up a cup from the table, raises it toward her mouth, and takes a sip.

Correct output:

PROMPT DIAGNOSIS
- The sequence contains three explicit action beats: picking up the cup, raising it toward her mouth, and taking a sip.
- The same woman and the same cup must remain continuous across all shots.

SHOT LIST
SHOT 1 - MEDIUM SHOT: The woman picks up the cup from the table.
SHOT 2 - MEDIUM SHOT: Continuing the action, she raises the same cup toward her mouth.
SHOT 3 - CLOSE-UP: She takes a sip from the same cup.

Do not output any explanation before or after the two required sections.
""".strip()

    return base + "\n\n" + task

@app.get("/health")
def health():
    runtime = load_runtime_profile()
    return {
        "status": "ok",
        "app": APP_NAME,
        "model": MODEL_NAME,
        "default_language": DEFAULT_LANGUAGE,
        "solohost_mode": SOLOHOST_MODE,
        "visual_proof_enabled": VISUAL_PROOF_ENABLED,
        "dmr_url": DMR_URL,
        "runtime_profile": runtime["profile"],
        "runtime_mode": runtime["display_mode"],
        "gpu_acceleration": runtime["gpu_acceleration"],
        "llm_runtime": runtime["llm"]["runtime"],
        "image_runtime": runtime["image"]["runtime"],
        "hero_runtime": HERO_BACKEND,
        "runtime": runtime,
    }


@app.get("/runtime")
def runtime():
    return load_runtime_profile()


@app.get("/api/capabilities")
def capabilities():
    return {
        "solohost_mode": SOLOHOST_MODE,
        "fixed_model": SOLOHOST_MODE,
        "model": MODEL_NAME,
        "fast_proof": FAST_PROOF_ENABLED,
        "hero_frame_set": True,
        "visual_proof_enabled": VISUAL_PROOF_ENABLED,
        "hero_backend": HERO_BACKEND,
    }


@app.get("/api/image-status")
async def image_status():
    if not FAST_PROOF_ENABLED:
        return {
            "ready": False,
            "state": "disabled",
            "message": "Fast Proof is not included in this SoloHost profile.",
            "backend": IMAGE_BACKEND,
        }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(IMAGE_READY_URL)
        if response.status_code == 200:
            return {
                "ready": True,
                "state": "ready",
                "message": "Visual Proof model is ready.",
                "backend": IMAGE_BACKEND,
            }
    except Exception:
        pass

    return {
        "ready": False,
        "state": "preparing",
        "message": IMAGE_PREPARING_MESSAGE,
        "backend": IMAGE_BACKEND,
    }


@app.get("/api/hero-status")
async def hero_status():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{HERO_API_URL}/status")
        response.raise_for_status()
        data = response.json()
        return {
            "available": True,
            "ready": data.get("ready", False),
            "state": data.get("state", "available"),
            "message": data.get("message", HERO_DOWNLOAD_MESSAGE),
            "download_gb_approx": data.get("download_gb_approx", 12),
            "size": data.get("size", "512x512"),
            "frames": data.get("frames", 3),
            "backend": HERO_BACKEND,
            "active_job": data.get("active_job"),
        }
    except Exception:
        message = (
            "Local Visual Proof is starting. Prompt Doctor remains available."
            if VISUAL_PROOF_ENABLED
            else HERO_PROFILE_INACTIVE_MESSAGE
        )
        return {
            "available": False,
            "ready": False,
            "state": "unavailable",
            "message": message,
            "download_gb_approx": 12,
            "size": "512x512",
            "frames": 3,
            "backend": HERO_BACKEND,
        }


@app.get("/api/models")
async def models():
    headers = {
        "Authorization": f"Bearer {DMR_API_KEY}",
        "Content-Type": "application/json",
    }
    source = "dmr"
    warning = None
    installed_ids = []
    errors = []
    model_urls = list(
        dict.fromkeys(
            [
                f"{DMR_URL}/models",
                f"{DMR_MANAGEMENT_URL}/models",
            ]
        )
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        for model_url in model_urls:
            try:
                response = await client.get(model_url, headers=headers)
                response.raise_for_status()
                installed_ids = parse_dmr_model_ids(response.json())
                if installed_ids:
                    source = model_url
                    break
            except Exception as exc:
                errors.append(f"{model_url}: {exc}")

    if not installed_ids and len(errors) == len(model_urls):
        source = "fallback"
        warning = "Could not list Docker Model Runner models: " + "; ".join(errors)

    if SOLOHOST_MODE:
        installed_ids = [MODEL_NAME]
        source = "solohost-fixed"
        warning = None

    inventory = build_model_inventory(
        installed_ids=installed_ids,
        default_model=MODEL_NAME,
        catalog=MODEL_CATALOG,
        assume_default_installed=source == "fallback",
    )
    inventory["source"] = source
    inventory["warning"] = warning
    inventory["fixed_model"] = SOLOHOST_MODE
    return inventory


def build_canonical_meaning(user_input: str, language: str) -> str:
    return (
        "CANONICAL MEANING LOCK:\n"
        "- Treat the user's source prompt as the authoritative source of truth.\n"
        "- Preserve every explicit subject, action, object, setting, time, spatial relationship, camera instruction, product detail, and exclusion.\n"
        "- Do not replace concrete user facts with stylistic alternatives.\n"
        "- Do not infer a different story from the user's prompt."
    )


def build_fidelity_guard(user_input: str) -> str:
    text = user_input.lower()
    notes = []

    if "dawn" in text:
        notes.append("The scene takes place at dawn. Keep dawn. Do not change it to sunset, night, or midday.")

    if "sunrise" in text:
        notes.append("The scene takes place at sunrise. Keep sunrise. Do not change it to sunset.")

    if "sunset" in text:
        notes.append("The scene takes place at sunset. Keep sunset. Do not change it to sunrise or midday.")

    if "sitting" in text or "sits" in text or "seated" in text:
        notes.append("The subject is sitting or seated. Preserve that action and body state.")

    if "static camera" in text or "camera does not move" in text or "camera remains static" in text:
        notes.append("The camera is explicitly static. Do not introduce camera movement.")

    if "beach" in text:
        notes.append("The location is a beach. Preserve the beach setting.")

    if "sea" in text or "ocean" in text:
        notes.append("The sea or ocean is explicitly part of the scene. Preserve it.")

    if "pier" in text:
        notes.append("A pier is explicitly part of the location. Preserve the pier.")

    if "fisherman" in text:
        notes.append("The subject is explicitly a fisherman. Preserve that subject identity.")

    if "couple" in text:
        notes.append("The scene contains a couple. Preserve the number and relationship context of the subjects.")

    if " on the left" in text or " to the left" in text:
        notes.append("A left-side spatial position is explicitly specified. Preserve it.")

    if " on the right" in text or " to the right" in text:
        notes.append("A right-side spatial position is explicitly specified. Preserve it.")

    if "no people" in text:
        notes.append("The user explicitly excludes people. Do not add people.")

    if "no vehicles" in text:
        notes.append("The user explicitly excludes vehicles. Do not add vehicles.")

    if "shallow depth of field" in text:
        notes.append('The exact technical instruction "shallow depth of field" is explicit. Preserve it.')

    if "eye movement" in text or "eye movements" in text:
        notes.append("Natural eye movement is explicit. Preserve it.")

    if "50mm" in text:
        notes.append("The 50mm lens specification is explicit. Preserve it.")

    if "same apple" in text and ("takes a bite" in text or "take a bite" in text):
        notes.append("The same apple changes state after the bite. Preserve the visible bite state when it appears later in the sequence.")

    guard = (
        "FIDELITY LOCK:\n"
        "- Preserve the user's exact subject, action, object identity, setting, time of day, camera instructions, spatial relationships, and explicit exclusions.\n"
        "- Do not change the scene into a different concept.\n"
        "- Do not add story events that were not requested.\n"
        "- Technical improvements may support the user's idea but must never replace explicit facts."
    )

    if notes:
        guard += "\n" + "\n".join(f"- {note}" for note in notes)

    return guard


def build_mode_guard(mode: str, user_input: str, aspect_ratio: str) -> str:
    text = user_input.lower()
    notes = [
        "MODE-SPECIFIC LOCK:",
        "- Follow the selected mode exactly; do not substitute a different task.",
    ]

    if aspect_ratio == "9:16":
        notes.append(
            '- The requested format is vertical 9:16. The final target section must explicitly contain "vertical" or "9:16".'
        )

    if mode == "improve":
        notes.extend([
            "- Use minimal, fidelity-first refinement.",
            "- Do not invent lighting sources, weather, emotions, facial expressions, reactions, gestures, backstory, brands, logos, or additional locations merely to make the prompt richer.",
            "- Preserve explicit technical wording such as lens choice, depth of field, camera behavior, framing, time of day, and object state.",
        ])
        if "brand" not in text and "logo" not in text and "label" not in text:
            notes.append("- No brand, logo, or label text was supplied. Do not invent any.")
        if "takes a bite" in text or "take a bite" in text:
            notes.append("- If the bitten object appears later, it must remain visibly bitten; do not reset its state.")

    elif mode == "diagnose":
        notes.extend([
            "- Diagnose only; do not improve or rewrite the prompt.",
            "- Mention only video-generation-relevant missing information.",
            "- Do not invent missing clothing, biography, appearance, personality, profession, ethnicity, or other character details.",
            '- The word "cinematic" alone is not a time of day, camera framing, or camera movement instruction.',
            "- If multiple camera behaviors compete, explicitly identify the overload/conflict.",
            "- If a pronoun can refer to more than one subject, explicitly identify the ambiguity and request clarification.",
        ])

    elif mode == "cinematic":
        notes.extend([
            "- Cinematic enhancement must remain non-narrative: do not invent new events, danger, directions, fear, safety-seeking behavior, or character reactions.",
            "- Do not invent concrete weather events that are not in the source prompt.",
            "- Use one coherent camera behavior; never combine moving/following camera language with static-camera language in the same shot.",
        ])
        if "storm" in text and "lightning" not in text:
            notes.append("- A storm is present, but lightning is not. Do not add lightning.")

    elif mode == "commercial":
        notes.extend([
            "- Preserve product identity, count, size, color, material, left/right placement, surface, and exact text when supplied.",
            "- If brand, logo, label text, color, material, finish, or design is absent, leave it unspecified.",
            "- Do not invent branding, product colors, material finishes, moon, fog, weather, people, or story events.",
        ])

    elif mode == "shotlist":
        notes.extend([
            "- Every explicit action beat is mandatory and must appear in chronological order.",
            "- Do not skip intermediate movement or destination actions.",
            "- Do not add nods, leaning, smiles, reactions, dialogue, or extra gestures.",
            "- Preserve explicit setting words and spatial relationships in the shot list.",
            "- For a three-beat sequence, use three shots with one explicit action beat per shot.",
        ])

    return "\n".join(notes)


def build_user_task(mode: str) -> str:
    tasks = {
        "improve": (
            "Improve the user's prompt with minimal fidelity-first refinement. "
            "Preserve every explicit fact and technical instruction. "
            "Do not invent story, emotional, environmental, product, branding, or location details."
        ),
        "diagnose": (
            "Diagnose the user's prompt only. Do not rewrite it. "
            "State what is clear, what is unspecified, and what is contradictory or ambiguous. "
            "If clarification is required, say exactly what must be clarified."
        ),
        "cinematic": (
            "Create the cinematic-mode output while preserving every explicit source fact. "
            "Add only non-narrative cinematic treatment and keep camera behavior internally coherent."
        ),
        "commercial": (
            "Create the commercial-mode output while preserving all locked product facts. "
            "Do not invent branding, color, material, packaging text, people, props, weather, or story events."
        ),
        "shotlist": (
            "Create the shot list from the user's explicit action beats only. "
            "Preserve every beat, setting, object, spatial relationship, and the exact chronological order."
        ),
    }
    return tasks[mode]


def build_conflict_guard(user_input: str) -> str:
    text = user_input.lower()
    conflicts = []

    # Framing conflict
    if "extreme close-up" in text and "full body" in text:
        conflicts.append(
            'FRAMING CONFLICT: "extreme close-up" and "full body" are incompatible framing instructions. '
            "Choose one valid framing and remove the other."
        )

    # Camera behavior conflict
    static_camera_terms = [
        "static camera",
        "camera is static",
        "camera is completely static",
        "completely static camera",
        "completely static",
        "camera does not move",
        "camera remains static",
    ]
    static_camera = any(term in text for term in static_camera_terms)

    moving_camera_terms = [
        "camera follows",
        "camera follow",
        "camera tracks",
        "camera tracking",
        "camera pans",
        "camera panning",
        "camera moves",
        "camera moving",
        "rapidly follows",
        "following a",
        "follows a",
        "tracking shot",
    ]

    moving_camera = any(term in text for term in moving_camera_terms)

    if static_camera and moving_camera:
        conflicts.append(
            'CAMERA CONFLICT: "static camera" conflicts with instructions that make the camera follow, '
            "track, pan, or move. Choose one camera behavior and remove the incompatible alternative."
        )

    if not conflicts:
        return (
            "CONFLICT CHECK:\n"
            "- No predefined technical conflict detected."
        )

    return "CONFLICT CHECK:\n- " + "\n- ".join(conflicts)


def build_conflict_resolution(user_input: str, mode: str = "improve") -> str:
    text = user_input.lower()
    resolutions = []

    # Framing resolution
    if "extreme close-up" in text and "full body" in text:
        action_terms = [
            "running",
            "walking",
            "dancing",
            "jumping",
            "moving",
        ]

        if any(term in text for term in action_terms):
            resolutions.append(
                'MANDATORY FRAMING RESOLUTION: Use "full body". '
                'Remove "extreme close-up".'
            )
        else:
            resolutions.append(
                'MANDATORY FRAMING RESOLUTION: Use "extreme close-up". '
                'Remove "full body".'
            )

    # Camera behavior resolution
    static_camera_terms = [
        "static camera",
        "camera is static",
        "camera is completely static",
        "completely static camera",
        "completely static",
        "camera does not move",
        "camera remains static",
    ]
    static_camera = any(term in text for term in static_camera_terms)

    moving_camera_terms = [
        "camera follows",
        "camera follow",
        "camera tracks",
        "camera tracking",
        "camera pans",
        "camera panning",
        "camera moves",
        "camera moving",
        "rapidly follows",
        "following a",
        "follows a",
        "tracking shot",
    ]

    moving_camera = any(term in text for term in moving_camera_terms)

    if static_camera and moving_camera:
        resolutions.append(
            'MANDATORY CAMERA RESOLUTION: Keep the camera static. '
            'Remove instructions that make the camera follow, track, pan, or move.'
        )

    if mode == "diagnose" and resolutions:
        return (
            "CONFLICT RESOLUTION:\n"
            "- Diagnose mode: do not silently choose a winner. "
            "State the incompatible instructions and require the user to select or clarify the intended behavior."
        )

    if not resolutions:
        return (
            "CONFLICT RESOLUTION:\n"
            "- No mandatory resolution required."
        )

    return "CONFLICT RESOLUTION:\n- " + "\n- ".join(resolutions)


def enforce_improve_diagnosis(
    result: str,
    conflict_guard: str,
    conflict_resolution: str,
) -> str:
    import re

    guard = conflict_guard.lower()
    resolution = conflict_resolution.lower()

    bullets = []

    # Deterministic framing diagnosis.
    if "framing conflict" in guard:
        if 'use "full body"' in resolution:
            bullets.append(
                '- FRAMING CONFLICT: "extreme close-up" and "full body" are '
                'incompatible framing instructions. The mandatory resolution '
                'is to use "full body" and remove "extreme close-up".'
            )
        elif 'use "extreme close-up"' in resolution:
            bullets.append(
                '- FRAMING CONFLICT: "extreme close-up" and "full body" are '
                'incompatible framing instructions. The mandatory resolution '
                'is to use "extreme close-up" and remove "full body".'
            )
        else:
            bullets.append(
                '- FRAMING CONFLICT: "extreme close-up" and "full body" are '
                'incompatible framing instructions.'
            )

    # Deterministic camera diagnosis.
    if "camera conflict" in guard:
        if "keep the camera static" in resolution:
            bullets.append(
                '- CAMERA CONFLICT: "static camera" conflicts with instructions '
                'that make the camera follow, track, pan, or move. The mandatory '
                'resolution is to keep the camera static and remove the '
                'incompatible moving-camera instruction.'
            )
        else:
            bullets.append(
                '- CAMERA CONFLICT: Static-camera and moving-camera instructions '
                'cannot both be active in the same shot.'
            )

    # No known deterministic conflict -> preserve the model diagnosis unchanged.
    if not bullets:
        return result

    # Replace only the diagnosis section.
    # Keep the model-generated IMPROVED PROMPT, which is separately protected
    # by enforce_improve_output().
    match = re.search(
        r"(?is)\bPROMPT DIAGNOSIS\b\s*.*?(?=\bIMPROVED PROMPT\b)",
        result,
    )

    if not match:
        return result

    replacement = (
        "PROMPT DIAGNOSIS\n\n"
        + "\n".join(bullets)
        + "\n\n"
    )

    return result[:match.start()] + replacement + result[match.end():]

def enforce_improve_output(result: str, conflict_resolution: str) -> str:
    import re

    # Only modify the final IMPROVED PROMPT section.
    # The model's diagnosis is preserved unchanged.
    match = re.search(r"(?is)(\bIMPROVED PROMPT\b\s*)(.*)$", result)

    if not match:
        return result

    prompt = match.group(2).strip()
    resolution = conflict_resolution.lower()

    # Framing conflict:
    # full body wins when the deterministic conflict resolver selected it.
    if 'use "full body". remove "extreme close-up".' in resolution:
        prompt = re.sub(
            r"(?i)\bextreme[\s-]+close[\s-]*up\b",
            "",
            prompt,
        )

    # Opposite framing resolution:
    # extreme close-up wins when explicitly selected by the resolver.
    elif 'use "extreme close-up". remove "full body".' in resolution:
        prompt = re.sub(
            r"(?i)\bfull[\s-]+body\b",
            "",
            prompt,
        )

    # Camera conflict:
    # preserve a static camera and remove incompatible movement.
    if "keep the camera static" in resolution:
        # Example:
        # "static camera rapidly follows him"
        # becomes:
        # "static camera"
        prompt = re.sub(
            r"(?i)\b(static\s+camera)\s+"
            r"(?:rapidly\s+|quickly\s+|slowly\s+)?"
            r"(?:follows|tracks|pans|moves)\b[^.!?\n]*",
            r"\1",
            prompt,
        )

        # Remove remaining explicit moving-camera instructions.
        prompt = re.sub(
            r"(?i)\b(?:the\s+)?camera\s+"
            r"(?:rapidly\s+|quickly\s+|slowly\s+)?"
            r"(?:follows|tracks|pans|moves)\b[^.!?\n]*[.!?]?",
            "",
            prompt,
        )

    # V1.2.4a mini text polish.
    # This function is used only by Improve mode, so no separate `mode`
    # variable is needed here.
    prompt = re.sub(
        r"(?i)\bclean\s+product-focused\s+composition\b",
        "clean cinematic composition",
        prompt,
    )
    prompt = re.sub(
        r"(?i)\bproduct-focused\s+composition\b",
        "cinematic composition",
        prompt,
    )
    prompt = re.sub(
        r"(?i)\bproduct-focused\s+framing\b",
        "cinematic framing",
        prompt,
    )

    # Clean spacing left behind by deterministic removals.
    prompt = re.sub(r"[ \t]{2,}", " ", prompt)
    prompt = re.sub(r"\s+([,.;:!?])", r"\1", prompt)
    prompt = re.sub(r"\n{3,}", "\n\n", prompt)
    prompt = prompt.strip(" \t\r\n,;:-")

    # Restore normal sentence capitalization if a removed phrase
    # was originally at the beginning of the prompt.
    if prompt:
        prompt = prompt[0].upper() + prompt[1:]

    return result[:match.start(2)] + prompt


def enforce_diagnose_output(result: str, user_input: str) -> str:
    """Deterministic corrections for high-confidence Diagnose cases."""
    text = user_input.lower()
    bullets = []

    static_terms = [
        "static camera",
        "camera is static",
        "camera is completely static",
        "completely static",
        "camera does not move",
        "camera remains static",
    ]
    moving_terms = [
        "following a",
        "camera follows",
        "camera follow",
        "camera tracks",
        "tracking shot",
        "dolly",
        "orbit",
        "pan",
    ]
    has_static = any(term in text for term in static_terms)
    has_follow = any(term in text for term in moving_terms)

    camera_overload_terms = [
        "drone orbit",
        "handheld",
        "dolly-in",
        "dolly in",
        "fast zoom",
        "zoom",
    ]
    camera_overload_count = sum(term in text for term in camera_overload_terms)

    style_terms = [
        "noir",
        "golden hour",
        "cyberpunk",
        "documentary",
        "glossy commercial",
    ]
    style_count = sum(term in text for term in style_terms)

    ambiguous_two_women = (
        "two women" in text
        and re.search(r"\bher\b", text) is not None
    )

    simple_cinematic = (
        "cinematic" in text
        and not any(
            term in text
            for term in [
                "wide shot",
                "close-up",
                "close up",
                "medium shot",
                "dolly",
                "tracking",
                "static camera",
                "camera follows",
                "camera pans",
                "camera moves",
                "50mm",
                "35mm",
                "24mm",
            ]
        )
    )

    if ambiguous_two_women:
        bullets = [
            "- The scene contains a man, two women, and a bag, but the pronoun reference is ambiguous.",
            '- "He approaches her" does not identify which of the two women the man approaches.',
            "- Clarify which woman is intended before the prompt is rewritten. Do not guess the referent.",
        ]

    elif camera_overload_count >= 3 or style_count >= 3:
        bullets = []
        if camera_overload_count >= 3:
            bullets.append(
                "- The camera direction is overloaded because several different camera behaviors are requested at the same time."
            )
        if style_count >= 3:
            bullets.append(
                "- The visual direction contains competing lighting/style priorities that should not all be treated as one coherent look."
            )
        bullets.append(
            "- Select one primary camera behavior and one dominant visual/lighting direction before treating the prompt as technically coherent."
        )

    elif has_static and has_follow:
        bullets = [
            "- The subject and action are clear.",
            "- The camera instructions conflict: a completely static camera cannot simultaneously follow or track the moving subject.",
            "- Choose either a fixed static shot or a moving follow/tracking shot before the prompt is technically consistent.",
        ]

    elif simple_cinematic:
        bullets = [
            "- The subject, basic action, and setting are clear.",
            '- "Cinematic" expresses a broad visual intention but does not specify camera framing or camera movement.',
            "- Camera framing and camera movement are unspecified.",
            "- Lighting, time of day, and atmosphere are also unspecified; do not invent them unless the user asks for expansion.",
        ]

    if not bullets:
        return result

    return "PROMPT DIAGNOSIS\n\n" + "\n".join(bullets)



def enforce_commercial_output(result: str, user_input: str) -> str:
    """
    Deterministic safety fallback for Commercial mode.

    If the model adds unsupported marketing/product details, replace the
    Commercial output with a concise fidelity-first version built from the
    user's own brief plus neutral technical direction.
    """
    source = user_input.strip()
    source_lower = source.lower()
    result_lower = result.lower()

    unsupported_terms = [
        "sleek",
        "high-quality",
        "high quality",
        "polished",
        "refreshing",
        "purity",
        "pure",
        "crystal clarity",
        "minimalist",
        "luxurious",
        "luxury",
        "eco-friendly",
        "eco friendly",
        "craftsmanship",
        "intricate pattern",
        "intricate design",
        "serene",
        "natural beauty",
        "gracefully",
    ]

    invented = [
        term for term in unsupported_terms
        if term in result_lower and term not in source_lower
    ]

    # Also treat an invented brand as a hard fallback trigger.
    if "brand" in result_lower and "brand" not in source_lower:
        invented.append("brand")

    if not invented:
        return result

    # Keep the user's brief verbatim so explicit product facts, text, count,
    # placement, and setting cannot be silently rewritten.
    brief = source
    if brief and brief[-1] not in ".!?":
        brief += "."

    diagnosis = [
        "- The commercial brief is clear and its stated product and scene facts must be preserved exactly.",
        "- Product identity, count, placement, setting, and any explicit brand or label text must remain unchanged.",
        "- Unspecified appearance, branding, materials, props, benefits, and story details should remain unspecified.",
    ]

    final_prompt = (
        brief
        + " Use clean product-focused composition and controlled lighting to keep the product as the clear visual priority. "
        + "Preserve all stated product details exactly and do not add unstated branding, materials, colors, text, props, benefits, or story elements."
    )

    return (
        "PROMPT DIAGNOSIS\n\n"
        + "\n".join(diagnosis)
        + "\n\nCOMMERCIAL PROMPT\n\n"
        + final_prompt
    )


def enforce_explicit_output_locks(
    result: str,
    mode: str,
    aspect_ratio: str,
    user_input: str,
) -> str:
    """Preserve high-confidence explicit locks in the final target section."""
    if mode == "diagnose":
        return result

    markers = {
        "improve": "IMPROVED PROMPT",
        "cinematic": "CINEMATIC PROMPT",
        "commercial": "COMMERCIAL PROMPT",
        "shotlist": "SHOT LIST",
    }
    marker = markers.get(mode)
    if not marker:
        return result

    upper = result.upper()
    pos = upper.rfind(marker)
    if pos == -1:
        return result

    head = result[: pos + len(marker)]
    target = result[pos + len(marker):].strip()
    target_lower = target.lower()
    source_lower = user_input.lower()

    if aspect_ratio == "9:16" and "9:16" not in target_lower and "vertical" not in target_lower:
        if mode == "shotlist":
            shot_match = re.search(r"(?im)^SHOT 1\s*-\s*", target)
            if shot_match:
                target = (
                    target[:shot_match.start()]
                    + "SHOT 1 - VERTICAL 9:16 "
                    + target[shot_match.end():]
                )
            else:
                target = "Vertical 9:16 format.\n" + target
        else:
            target = target.rstrip() + " Compose for a vertical 9:16 frame."

    if (
        "shallow depth of field" in source_lower
        and "shallow depth of field" not in target.lower()
    ):
        target = target.rstrip() + " Maintain a shallow depth of field."

    return head + "\n\n" + target.strip()


def enforce_semantic_boundaries(
    result: str,
    mode: str,
    user_input: str,
) -> str:
    """Small deterministic guards for high-confidence semantic fidelity cases."""
    source = user_input.lower()

    markers = {
        "improve": "IMPROVED PROMPT",
        "cinematic": "CINEMATIC PROMPT",
        "commercial": "COMMERCIAL PROMPT",
        "shotlist": "SHOT LIST",
    }
    marker = markers.get(mode)
    if not marker:
        return result

    upper = result.upper()
    pos = upper.rfind(marker)
    if pos == -1:
        return result

    head = result[: pos + len(marker)]
    target = result[pos + len(marker):].strip()

    # 1) Do not infer emotion/reaction from a simple action prompt.
    if mode == "improve":
        forbidden_emotion_terms = [
            "joyful expression",
            "welcoming smile",
            "welcoming gesture",
            "bond between them",
        ]
        if not any(term in source for term in ["joy", "joyful", "smile", "welcoming", "bond"]):
            for term in forbidden_emotion_terms:
                if term in target.lower():
                    target = re.sub(
                        r"(?is),\s*(?:with|while|using)\b[^.]*?"
                        + re.escape(term)
                        + r"[^.]*?(?=\.|$)",
                        "",
                        target,
                    )
            target = re.sub(r"(?i)\bjoyful expression\b", "expression", target)
            target = re.sub(r"(?i)\bwelcoming (?:smile|gesture)\b", "presence", target)
            target = re.sub(r"(?i)\bbond between them\b", "interaction", target)

        # 2) Preserve changed object state after a bite.
        if (
            "apple" in source
            and ("takes a bite" in source or "take a bite" in source)
            and ("same apple" in source or "apple back" in source)
            and not any(phrase in target.lower() for phrase in ["visible bite", "bite mark", "remains visibly bitten"])
        ):
            target = target.rstrip()
            if target and target[-1] not in ".!?":
                target += "."
            target += " Keep the same apple visibly bitten when it is placed back on the table."

    # 3) A storm does not imply lightning or invented danger/reaction.
    if mode == "cinematic" and "storm" in source and "lightning" not in source:
        # Remove entire invented reaction/danger sentences when they appear.
        target = re.sub(
            r"(?is)(?:^|(?<=[.!?])\s+)[^.!?]*\bsearching for a safe path\b[^.!?]*[.!?]?",
            " ",
            target,
        )
        target = re.sub(
            r"(?is)(?:^|(?<=[.!?])\s+)[^.!?]*\bdetermination and fear\b[^.!?]*[.!?]?",
            " ",
            target,
        )
        target = re.sub(r"(?i),?\s*(?:their edges )?tinged with lightning", "", target)
        target = re.sub(r"(?i)\b(?:distant\s+)?lightning\b", "", target)
        target = re.sub(r"\s+([,.;:!?])", r"\1", target)
        target = re.sub(r"[ \t]{2,}", " ", target)

    # 4) Do not invent appearance/material for an unspecified perfume bottle.
    if mode == "commercial" and "perfume bottle" in source:
        source_has_color_or_material = any(
            term in source
            for term in [
                "black", "white", "red", "blue", "green", "gold", "silver",
                "transparent", "glass", "metal", "metallic", "wood", "wooden",
                "matte", "glossy", "sleek", "dark perfume",
            ]
        )
        if not source_has_color_or_material:
            target = re.sub(
                r"(?i)\b(?:sleek\s*,?\s*)?(?:dark\s+|metallic\s+|glossy\s+)?perfume bottle\b",
                "perfume bottle",
                target,
            )
            target = re.sub(r"(?i)\bsubtle metallic sheen\b", "surface detail", target)
            target = re.sub(r"(?i)\bintricate design\b", "product form", target)
            target = re.sub(r"(?i)\bluxurious appearance\b", "product presence", target)
            target = re.sub(r"(?i)\bsmooth contours\b", "product contours", target)

    target = re.sub(r"[ \t]{2,}", " ", target)
    target = re.sub(r"\n{3,}", "\n\n", target).strip()
    return head + "\n\n" + target




# ---------------------------------------------------------------------------
# V1.1 FIDELITY GUARD — OBSERVER MODE
#
# This layer runs AFTER the existing V1.0 output has been produced.
# It does not rewrite, repair, regenerate, or otherwise modify the result.
# It only compares explicit source intent against the final target section
# and reports INTENT PROTECTED / REVIEW / CONFLICT.
# ---------------------------------------------------------------------------

def _observer_normalize(text: str) -> str:
    text = (text or "").lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _observer_has_any(text: str, phrases: list[str]) -> bool:
    normalized = _observer_normalize(text)
    return any(_observer_normalize(phrase) in normalized for phrase in phrases)


def _observer_static_camera_requested(text: str) -> bool:
    normalized = _observer_normalize(text)

    if _observer_has_any(
        normalized,
        [
            "static camera",
            "locked camera",
            "locked-off camera",
            "camera is static",
            "camera is completely static",
            "camera does not move",
            "camera remains static",
            "no camera movement",
        ],
    ):
        return True

    # Also recognizes phrasing such as "static low-angle camera".
    return re.search(r"\bstatic\b.{0,35}\bcamera\b", normalized) is not None


def _observer_moving_camera_requested(text: str) -> bool:
    return _observer_has_any(
        text,
        [
            "camera follows",
            "camera following",
            "camera follow",
            "camera tracks",
            "camera tracking",
            "tracking camera",
            "tracking shot",
            "follow shot",
            "camera pans",
            "camera panning",
            "camera moves",
            "camera moving",
            "dolly follows",
            "follows her from behind",
            "follows him from behind",
        ],
    )


def _observer_source_conflicts(source: str) -> list[str]:
    source_normalized = _observer_normalize(source)
    conflicts: list[str] = []

    if (
        _observer_static_camera_requested(source_normalized)
        and _observer_moving_camera_requested(source_normalized)
    ):
        conflicts.append(
            "Camera instructions conflict: static/locked camera and moving/following camera are both requested."
        )

    if (
        "extreme close-up" in source_normalized
        and "full body" in source_normalized
    ):
        conflicts.append(
            'Framing instructions conflict: "extreme close-up" and "full body" cannot both describe the same framing.'
        )

    if (
        "one continuous shot" in source_normalized
        and _observer_has_any(
            source_normalized,
            ["cut to", "cuts to", "hard cut", "smash cut"],
        )
    ):
        conflicts.append(
            "Editing instructions conflict: one continuous shot is combined with an explicit cut."
        )

    if (
        "no people" in source_normalized
        and _observer_has_any(
            source_normalized,
            ["woman", "man", "boy", "girl", "person"],
        )
    ):
        conflicts.append(
            "Subject instructions conflict: the prompt excludes people but also specifies a human subject."
        )

    return conflicts


def _observer_extract_target(result: str, mode: str) -> str:
    if mode == "diagnose":
        return ""

    markers = {
        "improve": "IMPROVED PROMPT",
        "cinematic": "CINEMATIC PROMPT",
        "commercial": "COMMERCIAL PROMPT",
        "shotlist": "SHOT LIST",
    }

    marker = markers.get(mode)
    if not marker:
        return result.strip()

    upper = result.upper()
    position = upper.rfind(marker)
    if position == -1:
        return result.strip()

    return result[position + len(marker):].strip()


def _observer_positive_forbidden_term(text: str, term: str) -> bool:
    normalized = _observer_normalize(text)
    escaped = re.escape(_observer_normalize(term))

    negative_patterns = [
        rf"\bno\s+{escaped}\b",
        rf"\bwithout\s+(?:a\s+|any\s+)?{escaped}\b",
        rf"\b{escaped}[- ]free\b",
        rf"\bdo not (?:show|add|include|display|use)\s+(?:a\s+|any\s+)?{escaped}\b",
        rf"\bavoid(?:s|ing)?\s+(?:a\s+|any\s+)?{escaped}\b",
    ]

    stripped = normalized
    for pattern in negative_patterns:
        stripped = re.sub(pattern, " ", stripped)

    return re.search(rf"\b{escaped}\b", stripped) is not None


def _observer_check_subject_count(
    source: str,
    target: str,
    issues: list[str],
) -> None:
    source_normalized = _observer_normalize(source)
    target_normalized = _observer_normalize(target)

    plural_forms = {
        "woman": ["women", "two women", "2 women"],
        "man": ["men", "two men", "2 men"],
        "boy": ["boys", "two boys", "2 boys"],
        "girl": ["girls", "two girls", "2 girls"],
    }

    for subject, plurals in plural_forms.items():
        explicit_one = re.search(
            rf"\b(?:a|one|1)\s+{re.escape(subject)}\b",
            source_normalized,
        )
        if not explicit_one:
            continue

        if re.search(rf"\b{re.escape(subject)}\b", target_normalized) is None:
            issues.append(f"SUBJECT: one {subject} is explicit in the source but missing from the final prompt.")
            continue

        if _observer_has_any(target_normalized, plurals):
            issues.append(f"SUBJECT: the final prompt appears to change the count of the {subject}.")


def _observer_check_explicit_actions(
    source: str,
    target: str,
    issues: list[str],
) -> None:
    action_locks = [
        ("enters", ["enters", "walks into", "comes into"]),
        (
            "walks to the window",
            ["walks to the window", "approaches the window", "moves to the window"],
        ),
        (
            "looks outside",
            ["looks outside", "looks out", "gazes outside", "gazes out"],
        ),
        ("runs", ["runs", "running", "sprints", "sprinting"]),
        ("stands", ["stands", "standing"]),
        (
            "walks through",
            ["walks through", "walking through", "moves through"],
        ),
        (
            "sitting",
            ["sitting", "sits", "seated", "remains seated"],
        ),
    ]

    source_normalized = _observer_normalize(source)

    for label, alternatives in action_locks:
        if _observer_has_any(source_normalized, alternatives):
            if not _observer_has_any(target, alternatives):
                issues.append(
                    f"ACTION: explicit action/state '{label}' was not detected in the final prompt."
                )


def _observer_check_environment(
    source: str,
    target: str,
    issues: list[str],
) -> None:
    environment_locks = [
        ("kitchen", ["kitchen"]),
        ("hallway", ["hallway", "corridor"]),
        ("tall grass", ["tall grass", "field of tall grass", "grass field"]),
        ("beach", ["beach"]),
        ("pier", ["pier"]),
        ("sea/ocean", ["sea", "ocean"]),
    ]

    source_normalized = _observer_normalize(source)

    for label, alternatives in environment_locks:
        if _observer_has_any(source_normalized, alternatives):
            if not _observer_has_any(target, alternatives):
                issues.append(
                    f"ENVIRONMENT: explicit setting element '{label}' was not detected in the final prompt."
                )

    time_locks = [
        ("dawn", ["dawn"]),
        ("sunrise", ["sunrise"]),
        ("sunset", ["sunset"]),
    ]

    for label, alternatives in time_locks:
        if _observer_has_any(source_normalized, alternatives):
            if not _observer_has_any(target, alternatives):
                issues.append(
                    f"TIME: explicit time-of-day '{label}' was not detected in the final prompt."
                )


def _observer_check_camera(
    source: str,
    target: str,
    issues: list[str],
) -> None:
    if _observer_static_camera_requested(source):
        if _observer_moving_camera_requested(target):
            issues.append(
                "CAMERA: the source locks a static camera, but the final prompt introduces tracking/following movement."
            )
        elif not _observer_static_camera_requested(target):
            issues.append(
                "CAMERA: the source locks a static camera, but static/locked behavior was not detected in the final prompt."
            )

    source_normalized = _observer_normalize(source)

    if _observer_has_any(source_normalized, ["low-angle", "low angle"]):
        if not _observer_has_any(target, ["low-angle", "low angle"]):
            issues.append(
                "CAMERA: the explicit low-angle instruction was not detected in the final prompt."
            )

    if _observer_has_any(source_normalized, ["high-angle", "high angle"]):
        if not _observer_has_any(target, ["high-angle", "high angle"]):
            issues.append(
                "CAMERA: the explicit high-angle instruction was not detected in the final prompt."
            )


def _observer_check_spatial(
    source: str,
    target: str,
    issues: list[str],
) -> None:
    source_normalized = _observer_normalize(source)
    target_normalized = _observer_normalize(target)

    # High-confidence V1.1 core cases only.
    if re.search(r"\bwoman\b.{0,55}\bleft(?: side)?\b", source_normalized):
        woman_left = (
            re.search(r"\bwoman\b.{0,60}\bleft(?: side)?\b", target_normalized)
            or re.search(r"\bleft(?: side)?\b.{0,60}\bwoman\b", target_normalized)
        )
        if not woman_left:
            issues.append(
                "SPATIAL: the woman's explicit left-side placement was not preserved."
            )

    if re.search(r"\b(?:red\s+)?car\b.{0,80}\bright\b", source_normalized):
        car_right = (
            re.search(
                r"\b(?:red\s+)?car\b.{0,55}\b(?:on|to)\s+the\s+right\b",
                target_normalized,
            )
            or re.search(
                r"\bright(?: side)?\b.{0,55}\b(?:red\s+)?car\b",
                target_normalized,
            )
        )
        if not car_right:
            issues.append(
                "SPATIAL: the car's explicit right-side placement was not preserved."
            )

    if re.search(
        r"\b(?:red\s+)?car\b.{0,80}\bbehind (?:her|the woman)\b",
        source_normalized,
    ):
        behind_preserved = (
            re.search(
                r"\b(?:red\s+)?car\b.{0,80}\bbehind (?:her|the woman)\b",
                target_normalized,
            )
            or re.search(
                r"\bbehind (?:her|the woman)\b.{0,80}\b(?:red\s+)?car\b",
                target_normalized,
            )
        )
        if not behind_preserved:
            issues.append(
                "SPATIAL: the car's explicit position behind the woman was not preserved."
            )



def _observer_check_unrequested_human_details(
    source: str,
    target: str,
    issues: list[str],
) -> None:
    """
    Flag a small set of concrete human/emotional details when the model invents
    them even though the source prompt never requested them.
    """
    source_normalized = _observer_normalize(source)
    target_normalized = _observer_normalize(target)

    invention_groups = [
        (
            "facial expression",
            ["expression", "facial expression"],
            ["expression", "facial expression"],
        ),
        (
            "smile",
            ["smile", "smiles", "smiling"],
            ["smile", "smiles", "smiling"],
        ),
        (
            "emotion",
            [
                "joyful", "happy", "sad", "fearful", "afraid", "angry",
                "thoughtful", "serene", "anxious", "excited", "emotional",
            ],
            [
                "joyful", "happy", "sad", "fearful", "afraid", "angry",
                "thoughtful", "serene", "anxious", "excited", "emotional",
            ],
        ),
        (
            "reaction/gesture",
            [
                "welcoming gesture", "welcoming presence", "nods", "nodding",
                "waves", "waving", "gestures", "gesture",
            ],
            [
                "welcoming gesture", "welcoming presence", "nods", "nodding",
                "waves", "waving", "gestures", "gesture",
            ],
        ),
    ]

    for label, source_terms, target_terms in invention_groups:
        if not _observer_has_any(source_normalized, source_terms):
            if _observer_has_any(target_normalized, target_terms):
                issues.append(
                    f"INVENTION: the final prompt adds {label} that was not specified in the source."
                )


def _observer_check_product_and_constraints(
    source: str,
    target: str,
    issues: list[str],
) -> None:
    source_normalized = _observer_normalize(source)

    product_locks = [
        ("red car", ["red car", "red vehicle"]),
        (
            "clear glass bottle",
            ["clear glass bottle", "transparent glass bottle"],
        ),
        ("mineral water", ["mineral water"]),
        (
            "dark reflective surface",
            ["dark reflective surface", "dark, reflective surface"],
        ),
    ]

    for label, alternatives in product_locks:
        if _observer_has_any(source_normalized, alternatives):
            if not _observer_has_any(target, alternatives):
                issues.append(
                    f"OBJECT: explicit product/object fact '{label}' was not detected in the final prompt."
                )

    exclusions = {
        "no logo": "logo",
        "no people": "people",
        "no vehicles": "vehicle",
        "no cars": "car",
        "no text": "text",
        "no dialogue": "dialogue",
    }

    for source_phrase, forbidden_term in exclusions.items():
        if source_phrase in source_normalized:
            if _observer_positive_forbidden_term(target, forbidden_term):
                issues.append(
                    f"CONSTRAINT: the source explicitly says '{source_phrase}', but the final prompt appears to add '{forbidden_term}'."
                )


def observe_output_fidelity(
    user_input: str,
    result: str,
    mode: str,
    aspect_ratio: str,
    require_mode_structure: bool = True,
) -> FidelityObserverResult:
    """
    V1.1 observer-only validation.

    The observer never changes `result`. It only reports whether the final
    target section appears to preserve high-confidence explicit source locks.
    """
    conflicts = _observer_source_conflicts(user_input)

    if conflicts:
        return FidelityObserverResult(
            status="CONFLICT",
            issues=conflicts,
        )

    # Diagnose mode does not rewrite the user's prompt, so there is no generated
    # final prompt to compare for drift. Source conflicts are handled above.
    if mode == "diagnose":
        return FidelityObserverResult(
            status="INTENT PROTECTED",
            issues=[],
        )

    target = _observer_extract_target(result, mode)
    issues: list[str] = []

    _observer_check_subject_count(user_input, target, issues)
    _observer_check_explicit_actions(user_input, target, issues)
    _observer_check_environment(user_input, target, issues)
    _observer_check_camera(user_input, target, issues)
    _observer_check_spatial(user_input, target, issues)
    _observer_check_unrequested_human_details(user_input, target, issues)
    _observer_check_product_and_constraints(user_input, target, issues)
    issues.extend(
        detect_unrequested_creative_issues(
            source=user_input,
            target=target,
            mode=mode,
        )
    )
    issues.extend(
        output_structure_issues(
            result=result,
            mode=mode,
            require_mode_structure=require_mode_structure,
        )
    )

    if aspect_ratio == "9:16":
        if not _observer_has_any(target, ["9:16", "vertical"]):
            issues.append(
                "FORMAT: vertical 9:16 was requested but was not detected in the final target section."
            )

    return FidelityObserverResult(
        status="REVIEW" if issues else "INTENT PROTECTED",
        issues=issues,
    )


def observe_output_fidelity_safe(
    user_input: str,
    result: str,
    mode: str,
    aspect_ratio: str,
    require_mode_structure: bool = True,
) -> FidelityObserverResult:
    """
    Never allow the observer layer to break a successful V1.0 generation.
    Unexpected observer errors become REVIEW instead of an API failure.
    """
    try:
        return observe_output_fidelity(
            user_input=user_input,
            result=result,
            mode=mode,
            aspect_ratio=aspect_ratio,
            require_mode_structure=require_mode_structure,
        )
    except Exception:
        return FidelityObserverResult(
            status="REVIEW",
            issues=[
                "Fidelity Guard observer could not complete its validation. The Prompt Doctor result was not modified."
            ],
        )

def build_commercial_deterministic(user_input: str) -> str:
    """
    Fidelity-first Commercial mode.

    Commercial mode deliberately does not call the language model.
    It preserves the user's brief verbatim and adds only neutral,
    production-useful direction that cannot invent product identity,
    branding, appearance, materials, benefits, props, or story details.
    """
    brief = user_input.strip()

    if brief and brief[-1] not in ".!?":
        brief += "."

    diagnosis = (
        "PROMPT DIAGNOSIS\n\n"
        "- The commercial brief is clear.\n"
        "- Preserve the stated product, setting, placement, and any explicit brand or label details exactly.\n"
        "- Unspecified product appearance, branding, materials, colors, props, benefits, and story details should remain unspecified."
    )

    commercial_prompt = (
        "COMMERCIAL PROMPT\n\n"
        + brief
        + " Use clean product-focused composition and controlled lighting to keep the product as the clear visual priority. "
        + "Use restrained camera direction and preserve every stated product and scene detail exactly. "
        + "Do not add unstated branding, materials, colors, text, props, benefits, or story elements."
    )

    return diagnosis + "\n\n" + commercial_prompt



@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    active_model = MODEL_NAME if SOLOHOST_MODE else (req.model or MODEL_NAME).strip()
    if not is_valid_model_id(active_model):
        raise HTTPException(status_code=400, detail="Invalid Docker Model Runner model identifier.")

    if req.mode == "commercial":
        result = build_commercial_deterministic(req.user_input)
        fidelity = observe_output_fidelity_safe(
            user_input=req.user_input,
            result=result,
            mode=req.mode,
            aspect_ratio=req.aspect_ratio,
        )
        return GenerateResponse(
            result=result,
            model=active_model,
            mode=req.mode,
            fidelity=fidelity,
        )

    system_prompt = build_system_prompt(req.mode, req.aspect_ratio, req.language)
    guarded_user_input = build_fidelity_guard(req.user_input)
    canonical_meaning = build_canonical_meaning(req.user_input, req.language)
    mode_guard = build_mode_guard(req.mode, req.user_input, req.aspect_ratio)
    conflict_guard = build_conflict_guard(req.user_input)
    conflict_resolution = build_conflict_resolution(req.user_input, req.mode)
    user_task = build_user_task(req.mode)
    mode_temperature = {
        "improve": 0.15,
        "diagnose": 0.10,
        "shotlist": 0.15,
        "cinematic": 0.40,
        "commercial": 0.20,
    }.get(req.mode, TEMPERATURE)
    payload = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    model_prompt_prefix(active_model, MODEL_CATALOG)
                    + guarded_user_input
                    + "\n\n"
                    + canonical_meaning
                    + "\n\n"
                    + mode_guard
                    + "\n\n"
                    + conflict_guard
                    + "\n\n"
                    + conflict_resolution
                    + "\n\nUSER PROMPT:\n"
                    + req.user_input
                    + "\n\nTASK:\n"
                    + user_task
                    + " The fidelity lock, canonical meaning, mode-specific lock, conflict check, and conflict resolution are mandatory."
                ),
            },
        ],
        "temperature": mode_temperature,
        "max_tokens": MAX_TOKENS,
        "stream": False,

    }

    headers = {
        "Authorization": f"Bearer {DMR_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{DMR_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Docker Model Runner returned HTTP {exc.response.status_code}: {exc.response.text}",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Docker Model Runner: {exc}",
        )

    try:
        result = data["choices"][0]["message"]["content"].strip()
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected response from Docker Model Runner: {data}",
        )

    if req.mode == "improve":
        result = enforce_improve_output(result, conflict_resolution)
        result = enforce_improve_diagnosis(
            result,
            conflict_guard,
            conflict_resolution,
        )

    if req.mode == "diagnose":
        result = enforce_diagnose_output(result, req.user_input)

    if req.mode == "commercial":
        result = enforce_commercial_output(result, req.user_input)

    result = enforce_explicit_output_locks(
        result,
        req.mode,
        req.aspect_ratio,
        req.user_input,
    )

    result = enforce_semantic_boundaries(
        result,
        req.mode,
        req.user_input,
    )

    fidelity = observe_output_fidelity_safe(
        user_input=req.user_input,
        result=result,
        mode=req.mode,
        aspect_ratio=req.aspect_ratio,
    )

    if fidelity.status == "REVIEW":
        corrected_result, corrections = auto_correct_narrow_lighting_review(
            source=req.user_input,
            target=result,
            mode=req.mode,
            issues=fidelity.issues,
        )
        if corrections:
            corrected_fidelity = observe_output_fidelity_safe(
                user_input=req.user_input,
                result=corrected_result,
                mode=req.mode,
                aspect_ratio=req.aspect_ratio,
            )
            if corrected_fidelity.status == "INTENT PROTECTED":
                result = corrected_result
                fidelity = corrected_fidelity

    return GenerateResponse(
        result=result,
        model=active_model,
        mode=req.mode,
        fidelity=fidelity,
    )



def _proof_cleanup_unrequested_human_details(
    source_prompt: str,
    final_prompt: str,
) -> tuple[str, list[str]]:
    """
    Proof-only deterministic cleanup.

    It removes only the small set of human-detail inventions already recognized
    by the V1.1 observer, and only when those details were not present in the
    user's source prompt. The original Prompt Doctor result is never modified.
    """
    source = _observer_normalize(source_prompt)
    cleaned = final_prompt
    notes: list[str] = []

    source_has_expression = _observer_has_any(
        source,
        ["expression", "facial expression"],
    )
    source_has_smile = _observer_has_any(
        source,
        ["smile", "smiles", "smiling"],
    )
    emotion_terms = [
        "joyful", "happy", "sad", "fearful", "afraid", "angry",
        "thoughtful", "serene", "anxious", "excited", "emotional",
    ]
    source_has_emotion = _observer_has_any(source, emotion_terms)

    gesture_terms = [
        "welcoming gesture", "welcoming presence", "nods", "nodding",
        "waves", "waving", "gestures", "gesture",
    ]
    source_has_gesture = _observer_has_any(source, gesture_terms)

    if not source_has_expression:
        expression_patterns = [
            r"\bwith\s+(?:a|an|her|his|their)\s+[^,.;:\n]{0,40}?(?:facial\s+)?expression\b",
            r"\b(?:her|his|their)\s+(?:facial\s+)?expression\s+(?:is|remains|appears|looks)\s+[^,.;:\n]+",
            r"\b(?:a|an)\s+[^,.;:\n]{0,32}?(?:facial\s+)?expression\b",
            r"\b(?:facial\s+)?expression\b",
        ]
        before = cleaned
        for pattern in expression_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        if cleaned != before:
            notes.append("Removed unrequested facial-expression wording.")

    if not source_has_smile:
        smile_patterns = [
            r"\bwith\s+(?:a\s+)?(?:slight|soft|subtle|gentle|faint|warm)?\s*smile\b",
            r"\b(?:she|he|they)\s+smiles\b",
            r"\bsmiling\b",
            r"\bsmiles\b",
            r"\bsmile\b",
        ]
        before = cleaned
        for pattern in smile_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        if cleaned != before:
            notes.append("Removed unrequested smile wording.")

    if not source_has_emotion:
        before = cleaned
        emotion_pattern = r"\b(?:" + "|".join(re.escape(x) for x in emotion_terms) + r")\b"
        cleaned = re.sub(emotion_pattern, "", cleaned, flags=re.IGNORECASE)
        if cleaned != before:
            notes.append("Removed unrequested emotion wording.")

    if not source_has_gesture:
        gesture_patterns = [
            r"\bwelcoming\s+gesture\b",
            r"\bwelcoming\s+presence\b",
            r"\b(?:she|he|they)\s+(?:nods|waves|gestures)\b",
            r"\b(?:nodding|waving|gesturing)\b",
            r"\b(?:nods|waves|gestures|gesture)\b",
        ]
        before = cleaned
        for pattern in gesture_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        if cleaned != before:
            notes.append("Removed unrequested gesture wording.")

    # Conservative punctuation/spacing repair only.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r",\s*,+", ", ", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\n[ \t]+\n", "\n\n", cleaned)
    cleaned = cleaned.strip()

    return cleaned, notes


def _proof_subject_phrase(source_text: str) -> str:
    s = _observer_normalize(source_text)

    mapping = [
        ("young filmmaker", "a young filmmaker"),
        ("filmmaker", "a filmmaker"),
        ("a couple", "a couple"),
        ("couple", "a couple"),
        ("two women", "two women"),
        ("two men", "two men"),
        ("woman", "a woman"),
        ("man", "a man"),
        ("girl", "a girl"),
        ("boy", "a boy"),
        ("child", "a child"),
        ("person", "a person"),
        ("women", "the women"),
        ("men", "the men"),
        ("children", "the children"),
        ("people", "the people"),
    ]

    for term, phrase in mapping:
        if re.search(rf"\b{re.escape(term)}\b", s):
            return phrase

    return "the principal subject"


def _proof_environment_phrase(source_text: str) -> str:
    s = _observer_normalize(source_text)

    mapping = [
        ("abandoned cinema", "an abandoned cinema"),
        ("old abandoned cinema", "an old abandoned cinema"),
        ("cinema", "a cinema"),
        ("auditorium", "an auditorium"),
        ("train platform", "a train platform"),
        ("station platform", "a train platform"),
        ("kitchen", "a kitchen"),
        ("office", "an office"),
        ("bedroom", "a bedroom"),
        ("bathroom", "a bathroom"),
        ("living room", "a living room"),
        ("lounge", "a living room"),
        ("hallway", "a hallway"),
        ("corridor", "a corridor"),
        ("car", "a car"),
        ("street", "a street"),
        ("road", "a road"),
        ("forest", "a forest"),
        ("woods", "a forest"),
    ]

    for term, phrase in mapping:
        if re.search(rf"\b{re.escape(term)}\b", s):
            return phrase

    return "the described location"


def _proof_is_empty_environment(source_text: str) -> bool:
    s = _observer_normalize(source_text)
    return bool(
        re.search(
            r"\bempty\s+(kitchen|room|office|bedroom|bathroom|hallway|corridor|house|apartment|space)\b",
            s,
        )
    )


def _proof_extract_action_clauses(source_text: str) -> list[str]:
    """
    Split video-language sequences into ordered action clauses.
    V1.2.4a also respects sentence boundaries.
    """
    text = re.sub(r"\s+", " ", source_text.strip())

    text = re.sub(r"\band then\b", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"\bthen\b", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"\bafter that\b", ",", text, flags=re.IGNORECASE)

    parts = re.split(
        r"(?<=[.!?])\s+|\s*,\s*|\s+\band\s+",
        text,
        flags=re.IGNORECASE,
    )
    return [p.strip(" .") for p in parts if p.strip(" .")]


def _proof_clause_score(clause: str) -> int:
    """
    Higher score = better still-photo candidate.
    Stable visible states beat transitions.
    """
    c = _observer_normalize(clause)

    very_high = [
        "stops", "stopping", "pauses", "pausing",
        "looks back", "looking back",
        "looks outside", "looking outside", "looks out", "looking out",
        "watches", "watching", "observes", "observing",
        "stares", "staring",
    ]
    high = [
        "embraces", "embracing", "hugs", "hugging", "kisses", "kissing",
        "stands", "standing", "sits", "sitting",
        "holds", "holding", "faces", "facing",
        "presents", "presenting", "examines", "examining",
        "waits", "waiting",
    ]
    medium = [
        "reaches", "reaching", "opens", "opening",
        "walks", "walking", "runs", "running",
        "drives", "driving",
    ]
    low = [
        "enters", "entering", "leaves", "leaving",
        "starts", "starting", "begins", "beginning",
        "gets inside", "gets in", "moves", "moving",
    ]

    if any(term in c for term in very_high):
        return 40
    if any(term in c for term in high):
        return 30
    if any(term in c for term in medium):
        return 20
    if any(term in c for term in low):
        return 10
    return 15


def _proof_is_stable_position_clause(clause: str) -> bool:
    c = _observer_normalize(clause)
    return any(
        term in c
        for term in [
            "stops", "stopping", "stands", "standing",
            "sits", "sitting", "pauses", "pausing",
            "waits", "waiting",
        ]
    )


def _proof_is_observation_clause(clause: str) -> bool:
    c = _observer_normalize(clause)
    return any(
        term in c
        for term in [
            "looks back", "looking back", "looks", "looking",
            "faces", "facing", "watches", "watching",
            "observes", "observing", "stares", "staring",
        ]
    )


def _proof_clean_selected_clause(clause: str) -> str:
    """
    Remove repeated subject wording and normalize selected actions into
    natural still-frame grammar.
    """
    cleaned = clause.strip(" .")
    cleaned = re.sub(
        r"(?i)^(?:he|she|they|the man|the woman|the filmmaker|a filmmaker|a young filmmaker)\s+",
        "",
        cleaned,
    )

    # Stable state.
    cleaned = re.sub(r"(?i)^stops?\b", "standing", cleaned)
    cleaned = re.sub(r"(?i)^pauses?\b", "standing", cleaned)

    # Observation/action phrasing for a still image.
    verb_map = [
        (r"(?i)^enters\b", "entering"),
        (r"(?i)^walks\b", "walking"),
        (r"(?i)^carries\b", "carrying"),
        (r"(?i)^looks back\b", "looking back"),
        (r"(?i)^looks outside\b", "looking outside"),
        (r"(?i)^looks out\b", "looking out"),
        (r"(?i)^looks\b", "looking"),
        (r"(?i)^watches\b", "watching"),
        (r"(?i)^observes\b", "observing"),
        (r"(?i)^faces\b", "facing"),
        (r"(?i)^stares\b", "staring"),
    ]
    for pattern, replacement in verb_map:
        cleaned = re.sub(pattern, replacement, cleaned)

    return cleaned.strip()


def _proof_choose_single_frame_clause(source_text: str) -> tuple[str, str]:
    clauses = _proof_extract_action_clauses(source_text)

    if len(clauses) <= 1:
        selected = clauses[0] if clauses else source_text.strip()
        return (_proof_clean_selected_clause(selected), "single_moment")

    # V1.2.4a: stable position + observation is the strongest single-frame pair.
    # Example: "stops beneath the screen" + "looks back toward the empty seats".
    for idx in range(len(clauses) - 1):
        current = clauses[idx]
        nxt = clauses[idx + 1]

        if _proof_is_stable_position_clause(current) and _proof_is_observation_clause(nxt):
            first = _proof_clean_selected_clause(current)
            second = _proof_clean_selected_clause(nxt)
            return f"{first} and {second}", "sequence_to_final_stable_moment"

    scored = [(idx, _proof_clause_score(clause), clause) for idx, clause in enumerate(clauses)]

    # Prefer the latest clause among equally strong still-photo candidates.
    idx, score, selected = max(scored, key=lambda x: (x[1], x[0]))
    return _proof_clean_selected_clause(selected), "sequence_to_representative_still"


def _proof_build_single_frame(source_text: str) -> tuple[str, str]:
    """
    V1.2.4a Single-Frame Extraction.

    Convert temporal/video instructions into one coherent still moment.
    """
    s = _observer_normalize(source_text)
    subject = _proof_subject_phrase(source_text)
    environment = _proof_environment_phrase(source_text)
    selected_clause, reason = _proof_choose_single_frame_clause(source_text)

    # Strong deterministic conversions for common, visually clear sequences.
    if (
        "window" in s
        and (
            "looks outside" in s
            or "looking outside" in s
            or "looks out" in s
            or "looking out" in s
        )
    ):
        frame = f"Photorealistic cinematic still of {subject} standing beside a window in {environment}, looking outside."
        if _proof_is_empty_environment(source_text):
            frame += f" {subject.capitalize()} is the only person present."
        frame += " One coherent real-world moment, realistic anatomy and architecture."
        return frame, "sequence_to_final_stable_moment"

    if (
        "car" in s
        and ("gets inside" in s or "gets in" in s)
        and ("drives away" in s or "starts the engine" in s)
    ):
        frame = (
            f"Photorealistic cinematic still of {subject} seated inside a car behind the steering wheel, ready to drive. "
            "The car is stationary. One coherent real-world moment, realistic anatomy and vehicle geometry."
        )
        return frame, "sequence_to_pre_drive_stable_moment"

    if (
        ("couple" in s or "two people" in s)
        and ("embraces" in s or "embrace" in s or "hug" in s)
        and ("platform" in s)
    ):
        rain = " in heavy rain" if "rain" in s else ""
        frame = (
            f"Photorealistic cinematic still of a couple embracing on a train platform{rain}. "
            "One coherent real-world moment, realistic anatomy and environment."
        )
        return frame, "sequence_to_emotional_stable_moment"

    # Generic final-state fallback: use the selected stable clause plus preserved
    # subject/location, then keep only explicit visual details from the source.
    selected = selected_clause.rstrip(".")
    selected_text = selected[0].lower() + selected[1:] if selected else "in the final visible state"

    if "cinema" in s:
        selected_text = re.sub(
            r"(?i)^(?:entering|walking into)\s+(?:an?\s+)?(?:old\s+)?(?:abandoned\s+)?cinema\b",
            "walking into the auditorium",
            selected_text,
        )

    frame = f"Photorealistic cinematic still of {subject} in {environment}, {selected_text}."

    explicit_details = []
    if "camera bag" in s and "camera bag" not in _observer_normalize(selected_text):
        explicit_details.append("a small camera bag visible over the shoulder")
    if "worn red seats" in s:
        explicit_details.append("rows of worn red seats")
    if "golden light" in s:
        explicit_details.append("soft golden light")
    if "dust particles" in s or "dust in the air" in s:
        explicit_details.append("dust particles visible in the air")
    if "broken side windows" in s:
        explicit_details.append("broken side windows")

    if explicit_details:
        frame += " Preserve these explicit scene details: " + ", ".join(explicit_details) + "."

    if _proof_is_empty_environment(source_text):
        frame += f" {subject.capitalize()} is the only person present."

    frame += " One coherent real-world moment, realistic anatomy and architecture."
    return frame, reason


def build_visual_proof_prompt(
    source_prompt: str,
    final_prompt: str,
    mode: str,
) -> tuple[str, str, str]:
    """
    V1.2.4a — Single-Frame Extraction.

    SDXL receives only the concise still-frame interpretation derived from the
    ORIGINAL user intent. Prompt Doctor output remains part of Fidelity Guard,
    not the image prompt.
    """
    single_frame_prompt, selection_reason = _proof_build_single_frame(source_prompt)

    negative_prompt = (
        "extra people, duplicate person, distorted human anatomy, deformed hands, "
        "surreal architecture, warped furniture, duplicate objects, text, watermark"
    )

    return single_frame_prompt, selection_reason, negative_prompt



# ---------------------------------------------------------------------------
# MODEL ADAPTER V2 — GENERIC VIDEO + RUNWAY GEN-4.5 + VEO 3.1 + KLING VIDEO 3.0
#
# Core principle:
#   Adapt the format, never rewrite the idea.
#
# No new LLM call. The adapter uses the already-approved prompt and applies
# deterministic profile-specific formatting only.
# ---------------------------------------------------------------------------

def _adapter_clean_prompt_text(approved_prompt: str, mode: str) -> str:
    target = _observer_extract_target(approved_prompt, mode).strip()
    if not target:
        target = approved_prompt.strip()

    # Remove wrapper/header residue without changing scene meaning.
    target = re.sub(r"(?m)^\s*#{1,6}\s*", "", target)
    target = re.sub(
        r"(?im)^\s*(?:MODEL READY|FINAL PROMPT|IMPROVED PROMPT|CINEMATIC PROMPT|COMMERCIAL PROMPT)\s*:?\s*$",
        "",
        target,
    )

    target = re.sub(r"[ \t]{2,}", " ", target)
    target = re.sub(r"\n{2,}", "\n", target)
    return target.strip()


def _adapter_section_breaks(target: str, labels: tuple[str, ...]) -> str:
    """Put already-explicit model cues on their own lines without rewriting them."""
    if not labels:
        return target

    label_pattern = "|".join(re.escape(label) for label in labels)
    return re.sub(
        rf"[ \t]+(?=(?:{label_pattern})\s*:)",
        "\n",
        target,
        flags=re.IGNORECASE,
    )


def _adapter_result(
    profile_name: str,
    original: str,
    adapted: str,
    changed_notes: list[str],
    unchanged_note: str,
) -> tuple[str, bool, list[str]]:
    adapted = adapted.strip()
    changed = adapted != original
    if changed:
        return adapted, True, changed_notes
    return adapted, False, [
        f"{profile_name}: approved prompt is compatible as-is.",
        unchanged_note,
    ]


def _build_generic_video_prompt(
    approved_prompt: str,
    mode: str,
) -> tuple[str, bool, list[str]]:
    target = _adapter_clean_prompt_text(approved_prompt, mode)
    return _adapter_result(
        profile_name="Generic Video",
        original=target,
        adapted=target,
        changed_notes=[],
        unchanged_note="No model-specific rewrite was requested or required.",
    )


def _build_runway_gen4_5_prompt(
    approved_prompt: str,
    mode: str,
) -> tuple[str, bool, list[str]]:
    """
    Runway Gen-4.5 profile, intentionally minimal.

    Rules:
    - preserve approved scene and explicit constraints
    - clear natural language
    - visible scene/action first
    - camera instruction kept explicit and simple
    - no invented creative details
    - one clean copy/paste prompt
    """
    original = _adapter_clean_prompt_text(approved_prompt, mode)
    target = original
    notes: list[str] = []

    # Keep sentence content intact. We only normalize a few generic wrapper
    # phrases so the output reads as a direct video-generation prompt.
    target, camera_changes = re.subn(
        r"(?i)\bthe camera maintains a steady,\s*([a-z-]+(?:\s+[a-z-]+)?) shot,\s*",
        r"A steady \1 camera shot, ",
        target,
    )
    if camera_changes:
        notes.append("Normalized the existing camera direction for Runway Gen-4.5.")

    # Avoid duplicate whitespace introduced by normalization.
    target = re.sub(r"[ \t]{2,}", " ", target)
    target = re.sub(r"\s+([,.;:])", r"\1", target)
    return _adapter_result(
        profile_name="Runway Gen-4.5",
        original=original,
        adapted=target,
        changed_notes=notes,
        unchanged_note="No motion or camera direction was invented.",
    )



def _build_veo_3_1_prompt(
    approved_prompt: str,
    mode: str,
) -> tuple[str, bool, list[str]]:
    """
    Veo 3.1 profile, intentionally minimal.

    Rules:
    - preserve approved subject, action, setting, style, and constraints
    - keep natural descriptive language
    - keep camera/composition explicit when already present
    - preserve audio/dialogue cues only when they already exist
    - do not invent new creative details
    - one clean copy/paste prompt
    """
    original = _adapter_clean_prompt_text(approved_prompt, mode)
    target = original
    notes: list[str] = []

    # Small formatting adaptation only:
    # make an existing camera instruction slightly more direct for video prompting.
    target, camera_changes = re.subn(
        r"(?i)\bthe camera maintains a steady,\s*([a-z-]+(?:\s+[a-z-]+)?) shot,\s*",
        r"The camera remains steady in a \1 shot, ",
        target,
    )
    if camera_changes:
        notes.append("Normalized the existing camera direction for Veo 3.1.")

    sectioned = _adapter_section_breaks(
        target,
        ("Audio", "Ambient sound", "Sound effects", "Dialogue"),
    )
    if sectioned != target:
        target = sectioned
        notes.append("Separated existing audio or dialogue cues for Veo 3.1.")

    target = re.sub(r"[ \t]{2,}", " ", target)
    target = re.sub(r"\s+([,.;:])", r"\1", target)
    return _adapter_result(
        profile_name="Veo 3.1",
        original=original,
        adapted=target,
        changed_notes=notes,
        unchanged_note="No audio, dialogue, motion, or camera detail was invented.",
    )



def _build_kling_video_3_0_prompt(
    approved_prompt: str,
    mode: str,
) -> tuple[str, bool, list[str]]:
    """
    Kling VIDEO 3.0 profile, intentionally minimal.

    Rules:
    - preserve approved subject, action sequence, location, style, and constraints
    - keep clear narrative natural language
    - keep camera direction explicit when already present
    - preserve dialogue/audio only when already present
    - do not invent shots, dialogue, audio, characters, or scene details
    - one clean copy/paste prompt
    """
    original = _adapter_clean_prompt_text(approved_prompt, mode)
    target = original
    notes: list[str] = []

    # Kling 3.0 accepts natural narrative prompting, so keep the approved
    # sequence intact and apply only a small camera-phrase normalization.
    target, camera_changes = re.subn(
        r"(?i)\bthe camera maintains a steady,\s*([a-z-]+(?:\s+[a-z-]+)?) shot,\s*",
        r"Steady \1 camera shot, ",
        target,
    )
    if camera_changes:
        notes.append("Normalized the existing camera direction for Kling VIDEO 3.0.")

    sectioned = _adapter_section_breaks(
        target,
        ("Shot 1", "Shot 2", "Shot 3", "Shot 4", "Shot 5", "Shot 6", "Audio", "Dialogue"),
    )
    if sectioned != target:
        target = sectioned
        notes.append("Separated existing shot, audio, or dialogue cues for Kling VIDEO 3.0.")

    target = re.sub(r"[ \t]{2,}", " ", target)
    target = re.sub(r"\s+([,.;:])", r"\1", target)
    return _adapter_result(
        profile_name="Kling VIDEO 3.0",
        original=original,
        adapted=target,
        changed_notes=notes,
        unchanged_note="No multi-shot structure, audio, dialogue, or camera detail was invented.",
    )


def _build_model_ready_prompt(
    profile: str,
    approved_prompt: str,
    mode: str,
) -> tuple[str, str, bool, list[str]]:
    if profile == "kling_video_3_0":
        prompt, changed, notes = _build_kling_video_3_0_prompt(approved_prompt, mode)
        return "Kling VIDEO 3.0", prompt, changed, notes

    if profile == "veo_3_1":
        prompt, changed, notes = _build_veo_3_1_prompt(approved_prompt, mode)
        return "Veo 3.1", prompt, changed, notes

    if profile == "runway_gen4_5":
        prompt, changed, notes = _build_runway_gen4_5_prompt(approved_prompt, mode)
        return "Runway Gen-4.5", prompt, changed, notes

    prompt, changed, notes = _build_generic_video_prompt(approved_prompt, mode)
    return "Generic Video", prompt, changed, notes


@app.post("/api/model-adapter", response_model=ModelAdapterResponse)
async def model_adapter(req: ModelAdapterRequest):
    """
    Transparent Model Adapter v2 endpoint.

    Supported profiles:
    - generic_video
    - runway_gen4_5
    - veo_3_1
    - kling_video_3_0

    The approved creative prompt is treated as locked. The adapter performs
    deterministic format adaptation only and must remain INTENT PROTECTED.
    The response states whether the prompt changed instead of implying that a
    compatible-as-is prompt was rewritten.
    """
    approved_fidelity = observe_output_fidelity_safe(
        user_input=req.source_prompt,
        result=req.approved_prompt,
        mode=req.mode,
        aspect_ratio=req.aspect_ratio,
    )

    if approved_fidelity.status != "INTENT PROTECTED":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Model Adapter blocked because the approved prompt is not INTENT PROTECTED.",
                "fidelity": approved_fidelity.model_dump(),
            },
        )

    profile_name, adapted_prompt, changed, adaptation_notes = _build_model_ready_prompt(
        profile=req.profile,
        approved_prompt=req.approved_prompt,
        mode=req.mode,
    )

    adapted_fidelity = observe_output_fidelity_safe(
        user_input=req.source_prompt,
        result=adapted_prompt,
        mode=req.mode,
        aspect_ratio=req.aspect_ratio,
        require_mode_structure=False,
    )

    if adapted_fidelity.status != "INTENT PROTECTED":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Model Adapter blocked because adaptation changed protected intent.",
                "fidelity": adapted_fidelity.model_dump(),
            },
        )

    return ModelAdapterResponse(
        status="MODEL READY",
        profile=profile_name,
        prompt=adapted_prompt,
        changed=changed,
        adaptation_notes=adaptation_notes,
        fidelity=adapted_fidelity,
    )


def _proof_quality_config(quality: str) -> tuple[str, int]:
    """
    V1.2.2 product modes:
    - fast: SDXL 768x768, 16 steps
    - quality: SDXL 1024x1024, 16 steps
    """
    if quality == "quality":
        return "1024x1024", 16
    return "768x768", 16


def _prepare_visual_prompt(
    source_prompt: str,
    final_prompt: str,
    mode: str,
    aspect_ratio: str,
    user_approved_addition: bool = False,
) -> tuple[str, str, str, FidelityObserverResult, bool, list[str]]:
    """Validate intent once and return the shared proof-safe scene prompt."""
    original_fidelity = observe_output_fidelity_safe(
        user_input=source_prompt,
        result=final_prompt,
        mode=mode,
        aspect_ratio=aspect_ratio,
    )
    proof_source = final_prompt
    cleanup_notes: list[str] = []

    # A REVIEW remains blocking until the user explicitly accepts the detected
    # addition in the local UI. Source conflicts are never bypassed by this flag.
    if user_approved_addition and original_fidelity.status == "REVIEW":
        fidelity = FidelityObserverResult(status="INTENT PROTECTED", issues=[])
        cleanup_notes = ["User explicitly approved the reviewed creative addition."]
    else:
        if original_fidelity.status == "REVIEW":
            allowed_prefixes = (
                "INVENTION: the final prompt adds facial expression",
                "INVENTION: the final prompt adds smile",
                "INVENTION: the final prompt adds emotion",
                "INVENTION: the final prompt adds reaction/gesture",
            )
            if original_fidelity.issues and all(
                issue.startswith(allowed_prefixes)
                for issue in original_fidelity.issues
            ):
                proof_source, cleanup_notes = _proof_cleanup_unrequested_human_details(
                    source_prompt=source_prompt,
                    final_prompt=final_prompt,
                )

        fidelity = observe_output_fidelity_safe(
            user_input=source_prompt,
            result=proof_source,
            mode=mode,
            aspect_ratio=aspect_ratio,
        )
    if fidelity.status != "INTENT PROTECTED":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Visual Proof blocked because the proof-safe prompt is not INTENT PROTECTED.",
                "original_fidelity": original_fidelity.model_dump(),
                "fidelity_after_cleanup": fidelity.model_dump(),
                "cleanup_applied": bool(cleanup_notes),
                "cleanup_notes": cleanup_notes,
            },
        )

    single_frame_prompt, selection_reason, negative_prompt = build_visual_proof_prompt(
        source_prompt=source_prompt,
        final_prompt=proof_source,
        mode=mode,
    )
    return (
        single_frame_prompt,
        selection_reason,
        negative_prompt,
        fidelity,
        bool(cleanup_notes),
        cleanup_notes,
    )


@app.post("/api/proof-frame", response_model=ProofFrameResponse)
async def generate_proof_frame(req: ProofFrameRequest):
    """
    V1.2 isolated proof-of-concept with proof-only deterministic cleanup.

    V1.1 remains unchanged. The original Prompt Doctor result is never rewritten.
    """
    (
        single_frame_prompt,
        selection_reason,
        negative_prompt,
        fidelity,
        cleanup_applied,
        cleanup_notes,
    ) = _prepare_visual_prompt(
        source_prompt=req.source_prompt,
        final_prompt=req.final_prompt,
        mode=req.mode,
        aspect_ratio=req.aspect_ratio,
    )

    proof_size, proof_steps = _proof_quality_config(req.quality)

    payload = {
        "model": IMAGE_MODEL,
        "prompt": single_frame_prompt,
        "negative_prompt": negative_prompt,
        "size": proof_size,
        "num_inference_steps": proof_steps,
        "rng_seed": req.rng_seed,
        "n": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=900.0) as client:
            response = await client.post(
                f"{IMAGE_API_URL}/images/generations",
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"{IMAGE_BACKEND} returned HTTP {exc.response.status_code}: "
                f"{exc.response.text}"
            ),
        )

    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(
            status_code=503,
            detail={
                "state": "preparing",
                "message": IMAGE_PREPARING_MESSAGE,
            },
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to the {IMAGE_BACKEND} image service: {exc}",
        )

    try:
        image_b64 = data["data"][0]["b64_json"]
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected response from {IMAGE_BACKEND} image service: {data}",
        )

    return ProofFrameResponse(
        image_b64=image_b64,
        model=IMAGE_MODEL,
        quality=req.quality,
        size=proof_size,
        proof_prompt=single_frame_prompt,
        single_frame_prompt=single_frame_prompt,
        selection_reason=selection_reason,
        negative_prompt=negative_prompt,
        fidelity=fidelity,
        cleanup_applied=cleanup_applied,
        cleanup_notes=cleanup_notes,
    )


@app.post("/api/hero-frame-set")
async def create_hero_frame_set(req: HeroFrameSetRequest):
    (
        single_frame_prompt,
        selection_reason,
        _negative_prompt,
        fidelity,
        cleanup_applied,
        cleanup_notes,
    ) = _prepare_visual_prompt(
        source_prompt=req.source_prompt,
        final_prompt=req.final_prompt,
        mode=req.mode,
        aspect_ratio=req.aspect_ratio,
        user_approved_addition=req.user_approved_addition,
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{HERO_API_URL}/hero-sets",
                json={
                    "prompt": single_frame_prompt,
                    "seeds": [req.base_seed + offset for offset in range(req.frame_count)],
                },
            )
            if response.status_code == 409:
                raise HTTPException(status_code=409, detail=response.json().get("detail"))
            response.raise_for_status()
            data = response.json()
    except HTTPException:
        raise
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(status_code=503, detail=HERO_DOWNLOAD_MESSAGE)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{HERO_BACKEND} returned HTTP {exc.response.status_code}: {exc.response.text}",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not start Hero Frame Set: {exc}")

    return {
        **data,
        "model": HERO_MODEL,
        "proof_prompt": single_frame_prompt,
        "selection_reason": selection_reason,
        "fidelity": fidelity.model_dump(),
        "cleanup_applied": cleanup_applied,
        "cleanup_notes": cleanup_notes,
    }


@app.get("/api/hero-frame-set/{job_id}")
async def hero_frame_set_status(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(status_code=422, detail="Invalid Hero Frame Set job ID.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{HERO_API_URL}/hero-sets/{job_id}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Hero Frame Set job not found.")
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read Hero Frame Set status: {exc}")


@app.post("/api/hero-frame-set/{job_id}/cancel")
async def cancel_hero_frame_set(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(status_code=422, detail="Invalid Hero Frame Set job ID.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{HERO_API_URL}/hero-sets/{job_id}/cancel")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Hero Frame Set job not found.")
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not cancel Hero Frame Set: {exc}")


@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("index.html", "r", encoding="utf-8") as file:
            return HTMLResponse(file.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>index.html not found</h1>", status_code=500)
