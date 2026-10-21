import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.linux_profile import _installed_model_count, parse_dmr_status, read_env


class LinuxProfileTests(unittest.TestCase):
    def test_cpu_variant_is_reported(self):
        status = """Docker Model Runner is running
llama.cpp  Running  llama.cpp b9879-cpu (sha256:test)
"""
        result = parse_dmr_status(status, "Test CPU", [])
        self.assertEqual(result["status"], "Running")
        self.assertEqual(result["backend"], "CPU")
        self.assertEqual(result["runtime"], "CPU / llama.cpp")
        self.assertEqual(result["accelerator"], "Test CPU")

    def test_cuda_variant_uses_nvidia_inventory(self):
        status = """Docker Model Runner is running
llama.cpp  Running  llama.cpp b9879-cuda (sha256:test)
"""
        gpus = [{"Name": "NVIDIA Test GPU", "Vendor": "NVIDIA"}]
        result = parse_dmr_status(status, "Test CPU", gpus)
        self.assertEqual(result["backend"], "CUDA")
        self.assertEqual(result["accelerator"], "NVIDIA Test GPU")
        self.assertTrue(result["gpu_acceleration"])

    def test_failed_model_runner_is_degraded(self):
        result = parse_dmr_status("Docker Model Runner is not running", "CPU", [])
        self.assertEqual(result["status"], "Unavailable")
        self.assertIsNone(result["variant"])

    def test_env_reader_accepts_utf8_bom_and_last_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("\ufeffVALUE=first\n# comment\nVALUE=second\n", encoding="utf-8")
            self.assertEqual(read_env(path)["VALUE"], "second")

    @patch("scripts.linux_profile._run")
    def test_installed_model_count_uses_docker_cli_in_wsl(self, run_mock):
        run_mock.return_value = (0, "ai/qwen2.5:3B-Q4_K_M\nai/gemma3:1B-Q4_K_M\n")
        self.assertEqual(_installed_model_count(), 2)


if __name__ == "__main__":
    unittest.main()
