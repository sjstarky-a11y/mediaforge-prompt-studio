#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/runtime-policy.sh"

assert_equal() {
    [ "$1" = "$2" ] || { printf 'Expected %s, got %s\n' "$2" "$1" >&2; exit 1; }
}

mf_select_nvidia_policy 5.2 8
assert_equal "$MF_NVIDIA_ELIGIBLE" false
assert_equal "$MF_NVIDIA_PROFILE" unsupported

mf_select_nvidia_policy 6.1 3.9
assert_equal "$MF_NVIDIA_ELIGIBLE" false

mf_select_nvidia_policy 6.1 4.0
assert_equal "$MF_NVIDIA_ELIGIBLE" true
assert_equal "$MF_NVIDIA_PROFILE" low_memory
assert_equal "$MF_NVIDIA_OFFLOAD" sequential

mf_select_nvidia_policy 7.5 6.0
assert_equal "$MF_NVIDIA_PROFILE" balanced
assert_equal "$MF_NVIDIA_OFFLOAD" model

mf_select_nvidia_policy 8.9 8.0
assert_equal "$MF_NVIDIA_PROFILE" full
assert_equal "$MF_NVIDIA_OFFLOAD" none

printf 'Linux NVIDIA runtime policy tests passed.\n'
