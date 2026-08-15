#!/usr/bin/env bash

# Sets MF_NVIDIA_* variables for a detected CUDA device.
mf_select_nvidia_policy() {
    local compute_capability="$1"
    local vram_gb="$2"

    MF_NVIDIA_ELIGIBLE=false
    MF_NVIDIA_PROFILE=unsupported
    MF_NVIDIA_OFFLOAD=none
    MF_NVIDIA_DISPLAY=CPU
    MF_NVIDIA_REASON=""

    if awk -v value="$compute_capability" 'BEGIN { exit !(value < 6.0) }'; then
        MF_NVIDIA_REASON="CUDA compute capability 6.0 or newer is required."
    elif awk -v value="$vram_gb" 'BEGIN { exit !(value < 4.0) }'; then
        MF_NVIDIA_REASON="At least 4 GB of NVIDIA VRAM is required for the SDXL CUDA profile."
    elif awk -v value="$vram_gb" 'BEGIN { exit !(value < 6.0) }'; then
        MF_NVIDIA_ELIGIBLE=true
        MF_NVIDIA_PROFILE=low_memory
        MF_NVIDIA_OFFLOAD=sequential
        MF_NVIDIA_DISPLAY="GPU + CPU"
        MF_NVIDIA_REASON="Low-memory CUDA profile with sequential CPU offload."
    elif awk -v value="$vram_gb" 'BEGIN { exit !(value < 8.0) }'; then
        MF_NVIDIA_ELIGIBLE=true
        MF_NVIDIA_PROFILE=balanced
        MF_NVIDIA_OFFLOAD=model
        MF_NVIDIA_DISPLAY="GPU + CPU"
        MF_NVIDIA_REASON="Balanced CUDA profile with model CPU offload."
    else
        MF_NVIDIA_ELIGIBLE=true
        MF_NVIDIA_PROFILE=full
        MF_NVIDIA_OFFLOAD=none
        MF_NVIDIA_DISPLAY=GPU
        MF_NVIDIA_REASON="Full CUDA profile."
    fi
}
