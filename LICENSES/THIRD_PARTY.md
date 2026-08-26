# Third-party software and model notices

MediaForge Prompt Studio Public Test uses third-party runtimes and models that retain their own licenses.

## Docker Model Runner

Used as the local LLM runtime for Public Test v0.1a.

Official documentation:
https://docs.docker.com/ai/model-runner/

## Qwen 2.5 3B Docker model

Model:
`ai/qwen2.5:3B-Q4_K_M`

The verified Docker Hub page for the exact `ai/qwen2.5` repository lists the
model under the Apache 2.0 license. Users should review the license metadata and
terms at the model's download source before use.

Model page:
https://hub.docker.com/r/ai/qwen2.5

## Optional Prompt Doctor models

The v0.2 development catalog can reference additional Qwen and Gemma variants.
No optional model weights are included in this repository. Qwen model pages
identify Apache 2.0 licensing; Gemma variants are governed by the separate
Gemma Terms. `manage-models.ps1` requires explicit acknowledgement before it
downloads a catalog entry with non-Apache terms.

Model pages:

- https://hub.docker.com/r/ai/qwen3
- https://hub.docker.com/r/ai/gemma3-qat

## NVIDIA image runtime

The optional NVIDIA profile uses PyTorch and Hugging Face Diffusers in a
separate CUDA-enabled container. It downloads the configured Stable Diffusion
model on first use; weights are not stored in this repository.

- PyTorch: BSD-style license — https://github.com/pytorch/pytorch/blob/main/LICENSE
- Diffusers: Apache 2.0 — https://github.com/huggingface/diffusers/blob/main/LICENSE
- Transformers: Apache 2.0 — https://github.com/huggingface/transformers/blob/main/LICENSE

The default CUDA image model is `stabilityai/stable-diffusion-xl-base-1.0`.
Its model card identifies the CreativeML Open RAIL++-M license. Users must
review and accept the model terms at the download source:
https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0

## FLUX.2 Klein 4B Hero Frame model

The optional Hero Frame Set downloads `black-forest-labs/FLUX.2-klein-4B`
from Hugging Face only after the user confirms first use. Model weights are not
included in this repository or the release archives. The model card identifies
the license as Apache 2.0. Users should review the current model card and terms
at the download source before use:

https://huggingface.co/black-forest-labs/FLUX.2-klein-4B

## OpenVINO Model Server

Used to serve the Visual Proof Frame image model locally.

The official OpenVINO Model Server repository is licensed under Apache 2.0.

Official license:
https://github.com/openvinotoolkit/model_server/blob/main/LICENSE

## Stable Diffusion XL OpenVINO INT8

Model:
`OpenVINO/stable-diffusion-xl-base-1.0-int8-ov`

The Hugging Face model card identifies the model license as `openrail++`.

Model page:
https://huggingface.co/OpenVINO/stable-diffusion-xl-base-1.0-int8-ov

## Python packages downloaded during build

- FastAPI 0.116.1 — MIT
  https://github.com/fastapi/fastapi/blob/master/LICENSE
- Uvicorn 0.35.0 — BSD 3-Clause
  https://github.com/Kludex/uvicorn/blob/main/LICENSE.md
- HTTPX 0.28.1 — BSD 3-Clause
  https://github.com/encode/httpx/blob/master/LICENSE.md

## Important

The MediaForge proprietary license does not replace or restrict third-party
licenses. This notice is not a substitute for their full terms. The installer
downloads third-party software and models separately; users must review and
comply with the terms presented by each download source. No third-party model
weights are stored in this repository.
