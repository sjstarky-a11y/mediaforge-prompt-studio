import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from runtime_tools.policy import select_backend, selection_env
from runtime_tools.profile import build_profile, parse_dmr_status
from runtime_tools.diagnostics import shareable_report


class BackendSelectionTests(unittest.TestCase):
    def intel(self):
        return dict(available=True, compute_test_passed=True, device="GPU.1",
                    name="Intel test GPU", memory_bytes=24*1024**3)

    def test_detection_alone_does_not_enable_gpu(self):
        report = {"available": True, "device": "GPU.0", "memory_bytes": 24*1024**3}
        self.assertEqual(select_backend("auto", {}, report)["selected"], "cpu")

    def test_intel_probe_selects_the_tested_device(self):
        result = select_backend("auto", {}, self.intel())
        self.assertEqual(result["selected"], "intel")
        self.assertEqual(selection_env(result, "wsl")["MEDIAFORGE_IMAGE_DEVICE"], "GPU.1")
        self.assertEqual(selection_env(result, "wsl")["MEDIAFORGE_COMPOSE_FILE"], "docker-compose.intel-wsl.yml")

    def test_nvidia_priority_and_explicit_intel_override(self):
        candidate = {"available": True, "compute_capability": 8.6, "memory_bytes": 8*1024**3}
        self.assertEqual(select_backend("auto", candidate, self.intel())["selected"], "nvidia")
        self.assertEqual(select_backend("intel", candidate, self.intel())["selected"], "intel")

    def test_old_cuda_device_is_not_selected_even_when_docker_can_see_it(self):
        candidate = {"available": True, "compute_capability": 5.0, "memory_bytes": 8*1024**3}
        self.assertEqual(select_backend("auto", candidate, {})["selected"], "cpu")

    def test_missing_driver_falls_back_only_in_auto_mode(self):
        self.assertEqual(select_backend("auto", {}, {})["selected"], "cpu")
        with self.assertRaises(ValueError):
            select_backend("intel", {}, {})

    def test_unknown_or_low_memory_remains_cpu(self):
        report = self.intel()
        for memory in (0, 4*1024**3):
            report["memory_bytes"] = memory
            self.assertEqual(select_backend("auto", {}, report)["selected"], "cpu")

    def test_explicit_cpu_bypasses_available_accelerators(self):
        self.assertEqual(select_backend("cpu", {"available": True}, self.intel())["selected"], "cpu")

    def test_dmr_running_service_with_stopped_engine_is_unavailable(self):
        report = parse_dmr_status("Docker Model Runner is running\nllama.cpp Stopped llama.cpp b1-cuda", "CPU", [])
        self.assertEqual(report["status"], "Unavailable")
        self.assertFalse(report["gpu_acceleration"])

    def test_configured_gpu_without_probe_is_not_reported_as_accelerated(self):
        report = build_profile({"MEDIAFORGE_ACTIVE_IMAGE_RUNTIME": "intel"}, {}, "", {})
        self.assertFalse(report["gpu_acceleration"])
        self.assertEqual(report["image"]["status"], "Unverified")

    def test_text_cpu_and_image_intel_are_reported_independently(self):
        selection = select_backend("auto", {}, self.intel())
        report = build_profile(selection_env(selection), {}, "Docker Model Runner is running\nllama.cpp Running llama.cpp b1-cpu", selection)
        self.assertEqual(report["gpu_acceleration_scope"], "image")
        self.assertEqual(report["llm"]["backend"], "CPU")
        self.assertFalse(report["image"]["model_ready"])

    def test_shareable_diagnostics_drop_private_fields_even_when_nested(self):
        secret = "private-model-name-and-path"
        report = shareable_report({"model": secret, "platform": secret, "package_version": secret, "llm": {"model": secret, "status": "Running", "backend": "CPU", "error": secret}, "image": {"backend": secret}})
        self.assertNotIn(secret, str(report))
        self.assertEqual(report["components"]["llm"]["backend"], "CPU")


if __name__ == "__main__":
    unittest.main()
