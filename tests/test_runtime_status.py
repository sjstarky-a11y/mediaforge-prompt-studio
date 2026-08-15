import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from runtime_status import load_runtime_profile  # noqa: E402


class RuntimeStatusTests(unittest.TestCase):
    def test_missing_profile_returns_safe_fallback(self):
        profile = load_runtime_profile(Path("missing-runtime-profile.json"))

        self.assertEqual(profile["profile"], "Unknown")
        self.assertFalse(profile["gpu_acceleration"])
        self.assertEqual(profile["llm"]["backend"], "Unknown")
        self.assertEqual(profile["image"]["backend"], "CPU")

    def test_hybrid_profile_is_loaded_and_normalized(self):
        source = {
            "schema_version": 1,
            "profile": "Hybrid",
            "summary": "HYBRID · NVIDIA LLM · CPU IMAGE",
            "display_mode": "GPU + CPU",
            "gpu_acceleration": True,
            "gpu_acceleration_scope": "llm",
            "llm": {
                "status": "Running",
                "engine": "llama.cpp",
                "backend": "CUDA",
                "runtime": "NVIDIA CUDA",
                "accelerator": "NVIDIA GeForce GTX 1050",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runtime-profile.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            profile = load_runtime_profile(path)

        self.assertEqual(profile["profile"], "Hybrid")
        self.assertTrue(profile["gpu_acceleration"])
        self.assertEqual(profile["display_mode"], "GPU + CPU")
        self.assertEqual(profile["llm"]["backend"], "CUDA")
        self.assertEqual(profile["image"]["runtime"], "CPU / OpenVINO SDXL INT8")

    def test_invalid_json_does_not_break_health(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runtime-profile.json"
            path.write_text("{invalid", encoding="utf-8")
            profile = load_runtime_profile(path)

        self.assertEqual(profile["summary"], "RUNTIME DETECTION PENDING")
        self.assertEqual(profile["display_mode"], "CPU")


if __name__ == "__main__":
    unittest.main()
