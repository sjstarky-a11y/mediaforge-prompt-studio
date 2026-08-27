import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLOHOST = ROOT / "solohost"


class SoloHostSourceTests(unittest.TestCase):
    def setUp(self):
        self.main = (SOLOHOST / "app" / "main.py").read_text(encoding="utf-8")
        self.html = (SOLOHOST / "app" / "index.html").read_text(encoding="utf-8")
        self.core = (SOLOHOST / "config_options.core.yml").read_text(encoding="utf-8")
        self.hero = (SOLOHOST / "config_options.hero.yml").read_text(encoding="utf-8")
        self.compose = (SOLOHOST / "docker-compose.yml").read_text(encoding="utf-8")

    def test_profile_sources_are_valid(self):
        ast.parse(self.main)
        self.assertIn('value: core', self.core)
        self.assertIn('value: visual-proof', self.hero)
        self.assertIn('profiles: ["visual-proof"]', self.compose)

    def test_only_hero_visual_path_is_presented(self):
        self.assertNotIn('id="fastProofMode"', self.html)
        self.assertIn('id="heroProofMode"', self.html)

    def test_review_approval_reaches_hero_backend(self):
        self.assertIn('id="approveReviewBtn"', self.html)
        self.assertIn('user_approved_addition: userApprovedAddition', self.html)
        self.assertIn('user_approved_addition=req.user_approved_addition', self.main)
        self.assertIn('Source conflicts are never bypassed', self.main)


if __name__ == "__main__":
    unittest.main()
