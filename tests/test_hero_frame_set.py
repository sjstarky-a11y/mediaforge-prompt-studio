import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / "app" / "main.py"
INDEX_PATH = ROOT / "app" / "index.html"
SERVICE_PATH = ROOT / "image_flux" / "server.py"


class HeroFrameSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = MAIN_PATH.read_text(encoding="utf-8")
        cls.html = INDEX_PATH.read_text(encoding="utf-8")
        cls.service = SERVICE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.service)

    def test_interface_uses_approved_product_language(self):
        self.assertIn("Hero Frame Set", self.html)
        self.assertIn("Choose your Hero Frame", self.html)
        self.assertIn("Select the image that best represents your scene.", self.html)
        self.assertIn("✓ HERO FRAME APPROVED", self.html)
        self.assertIn("Download selected frame", self.html)

    def test_shot_pack_is_clearly_planned(self):
        self.assertIn("Create Shot Pack · planned", self.html)
        self.assertIn(
            "Generate establishing, action and detail shots from this Hero Frame.",
            self.html,
        )

    def test_first_use_download_is_visible_and_confirmed(self):
        self.assertIn("approximately 12 GB", self.html)
        self.assertIn("window.confirm", self.html)
        self.assertIn('fetch("/api/hero-status"', self.html)

    def test_backend_exposes_job_endpoints(self):
        self.assertIn('@app.post("/api/hero-frame-set")', self.main)
        self.assertIn('@app.get("/api/hero-frame-set/{job_id}")', self.main)
        self.assertIn('@app.post("/v1/hero-sets")', self.service)
        self.assertIn('@app.get("/v1/hero-sets/{job_id}")', self.service)

    def test_service_generates_fixed_three_frame_sequence(self):
        self.assertIn("len(request.seeds) != 3", self.service)
        self.assertIn("height=512", self.service)
        self.assertIn("width=512", self.service)
        self.assertIn("num_inference_steps=4", self.service)
        self.assertIn("guidance_scale=1.0", self.service)


if __name__ == "__main__":
    unittest.main()
