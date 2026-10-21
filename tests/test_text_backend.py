import json
import sys
import unittest
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from text_backend import TextBackend, PUBLIC_INTEL_MODEL
from runtime_tools.policy import select_text_runtime


class TextSelectionTests(unittest.TestCase):
    def test_large_verified_intel_uses_gpu_for_text(self):
        self.assertEqual(select_text_runtime({"selected": "intel", "memory_bytes": 24*1024**3}), "intel")

    def test_smaller_intel_keeps_memory_for_images(self):
        self.assertEqual(select_text_runtime({"selected": "intel", "memory_bytes": 8*1024**3}), "dmr")

    def test_explicit_model_runner_selection_is_respected(self):
        self.assertEqual(select_text_runtime({"selected": "intel", "memory_bytes": 24*1024**3}, "dmr"), "dmr")

    def test_forced_intel_without_a_verified_profile_fails(self):
        with self.assertRaises(ValueError):
            select_text_runtime({"selected": "cpu"}, "intel")


class TextBackendTests(unittest.IsolatedAsyncioTestCase):
    def backend(self, handler):
        return TextBackend("http://dmr/v1", "http://dmr", "ai/public:3B", "local",
                           provider="intel", intel_url="http://intel/v3",
                           transport=httpx.MockTransport(handler))

    async def test_ready_intel_receives_the_request_and_actual_backend_is_returned(self):
        requests = []
        def handler(request):
            requests.append(request)
            if request.url.path.endswith("ready"):
                return httpx.Response(200)
            return httpx.Response(200, json={"choices": [{"message": {"content": "test"}}]})
        provider = self.backend(handler)
        _, model, backend = await provider.complete(PUBLIC_INTEL_MODEL, {"model": PUBLIC_INTEL_MODEL})
        self.assertEqual(model, PUBLIC_INTEL_MODEL)
        self.assertEqual(backend, "Intel GPU / OpenVINO")
        self.assertEqual(str(requests[-1].url), "http://intel/v3/chat/completions")

    async def test_preparing_intel_uses_and_reports_local_fallback(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(503) if request.url.host == "intel" else httpx.Response(200, json={"choices": []})
        provider = self.backend(handler)
        _, model, backend = await provider.complete(PUBLIC_INTEL_MODEL, {"model": PUBLIC_INTEL_MODEL})
        self.assertEqual(model, "ai/public:3B")
        self.assertIn("preparing", backend)
        self.assertEqual(json.loads(requests[-1].content)["model"], "ai/public:3B")

    async def test_selected_dmr_model_stays_on_its_own_provider(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"choices": []})
        provider = self.backend(handler)
        await provider.complete("ai/public:3B", {"model": "ai/public:3B"})
        self.assertEqual(requests[-1].url.host, "dmr")
        self.assertEqual(len(requests), 1)


class OutputLanguageTests(unittest.TestCase):
    def test_requested_language_is_explicit_after_mode_instructions(self):
        import ast
        source = Path(__file__).resolve().parents[1] / "app/main.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_system_prompt")
        namespace = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
        for mode in ("improve", "diagnose", "cinematic", "commercial", "shotlist"):
            prompt = namespace["build_system_prompt"](mode, "16:9", "Croatian")
            self.assertIn("OUTPUT LANGUAGE: Croatian", prompt.split("\n\n")[-1])
            self.assertIn("only the fixed section headings stay in English", prompt)
