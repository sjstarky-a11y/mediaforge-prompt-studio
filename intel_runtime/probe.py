"""Check Intel GPU execution without downloading or inspecting user models."""
import json
import os


def probe():
    import numpy as np
    import openvino as ov
    from openvino import opset13 as ops

    core = ov.Core()
    devices = []
    for device in core.available_devices:
        if not device.startswith("GPU"):
            continue
        if device == "GPU":
            device = "GPU.0"
        name = str(core.get_property(device, "FULL_DEVICE_NAME"))
        try:
            memory = int(core.get_property(device, "GPU_DEVICE_TOTAL_MEM_SIZE"))
        except RuntimeError:
            memory = 0
        discrete = "DISCRETE" in str(core.get_property(device, "DEVICE_TYPE")).upper()
        devices.append({"id": device, "name": name, "memory_bytes": memory, "discrete": discrete})
    requested = os.getenv("MEDIAFORGE_INTEL_DEVICE", "auto")
    candidates = [d for d in devices if requested == "auto" or d["id"] == requested]
    if not candidates:
        raise RuntimeError("The requested Intel GPU is not visible to OpenVINO.")
    # Prefer dedicated memory capacity; never assume GPU.0 is the intended card.
    selected = max(candidates, key=lambda d: (d["discrete"], d["memory_bytes"]))
    parameter = ops.parameter([1], np.float32)
    model = ov.Model([ops.multiply(parameter, parameter)], [parameter], "mediaforge_probe")
    compiled = core.compile_model(model, selected["id"])
    execution = list(compiled.get_property("EXECUTION_DEVICES"))
    result = float(compiled([np.array([2.0], dtype=np.float32)])[0][0])
    if result != 4.0 or not execution or any(not str(d).startswith("GPU") for d in execution):
        raise RuntimeError("GPU calculation did not execute exclusively on the selected GPU.")
    return {"available": True, "compute_test_passed": True, "device": selected["id"],
            "name": selected["name"], "memory_bytes": selected["memory_bytes"],
            "execution_devices": execution, "devices": devices, "runtime_version": ov.__version__}


if __name__ == "__main__":
    try:
        report = probe()
    except Exception:
        # Paths and runtime exception text can contain local/private information.
        report = {"available": False, "compute_test_passed": False,
                  "reason": "Intel GPU execution check failed. Check the driver and container GPU access."}
    print(json.dumps(report))
    raise SystemExit(0 if report["available"] else 1)
