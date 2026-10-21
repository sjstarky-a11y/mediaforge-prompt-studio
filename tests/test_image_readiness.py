import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / "app" / "main.py"
INDEX_PATH = ROOT / "app" / "index.html"


class ImageReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "derive_image_readiness_url"
        )
        namespace = {}
        module = ast.Module(body=[function], type_ignores=[])
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        cls.derive_url = staticmethod(namespace["derive_image_readiness_url"])
        cls.html = INDEX_PATH.read_text(encoding="utf-8")

    def test_readiness_url_is_derived_from_image_api(self):
        self.assertEqual(
            self.derive_url("http://image-cuda:8000/v3"),
            "http://image-cuda:8000/v2/health/ready",
        )
        self.assertEqual(
            self.derive_url("http://ovms-sdxl:8000/v3/"),
            "http://ovms-sdxl:8000/v2/health/ready",
        )

    def test_interface_polls_readiness_endpoint(self):
        self.assertIn('fetch("/api/image-status"', self.html)
        self.assertIn("The first download is several gigabytes", self.html)

    def test_preparing_state_is_not_presented_as_failure(self):
        self.assertIn('detailObject.state === "preparing"', self.html)
        self.assertIn("Visual Proof is still being prepared", self.html)


if __name__ == "__main__":
    unittest.main()
