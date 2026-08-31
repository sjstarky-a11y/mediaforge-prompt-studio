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
        self.public = (SOLOHOST / "config_options.yml").read_text(encoding="utf-8")
        self.compose = (SOLOHOST / "docker-compose.yml").read_text(encoding="utf-8")

    def test_profile_sources_are_valid(self):
        ast.parse(self.main)
        self.assertIn("value: core", self.core)
        self.assertIn("value: visual-proof", self.hero)
        self.assertIn("name: MEDIAFORGE_VISUAL_PROOF_MODE", self.public)
        self.assertIn("value: disabled", self.public)
        self.assertIn("value: enabled", self.public)

    def test_public_profile_avoids_reserved_select_field(self):
        self.assertIn("- name: COMPOSE_PROFILES", self.public)
        self.assertIn("value: enabled", self.public)
        fields = self.public.split("fields:", 1)[1]
        self.assertNotIn("name: COMPOSE_PROFILES", fields)
        self.assertIn("default: disabled", fields)

    def test_public_profile_offers_cpu_limits(self):
        for limit in ('"4.0"', '"8.0"', '"12.0"', '"16.0"'):
            self.assertIn(f"value: {limit}", self.public)

    def test_compose_uses_public_versioned_images(self):
        self.assertNotIn("build:", self.compose)
        self.assertIn(
            "aerialcroatia/mediaforge-prompt-studio:0.3-solohost.4",
            self.compose,
        )
        self.assertIn(
            "aerialcroatia/mediaforge-image-flux:0.3-solohost.4",
            self.compose,
        )
        self.assertIn(
            'profiles: ["${MEDIAFORGE_VISUAL_PROOF_MODE:-disabled}"]',
            self.compose,
        )

    def test_enabled_mode_is_an_accepted_runtime_flag(self):
        self.assertIn('"enabled"', self.main)
        self.assertIn(
            "MEDIAFORGE_VISUAL_PROOF_ENABLED=${MEDIAFORGE_VISUAL_PROOF_MODE:-disabled}",
            self.compose,
        )

    def test_only_hero_visual_path_is_presented(self):
        self.assertNotIn('id="fastProofMode"', self.html)
        self.assertIn('id="heroProofMode"', self.html)

    def test_review_approval_reaches_hero_backend(self):
        self.assertIn('id="approveReviewBtn"', self.html)
        self.assertIn("user_approved_addition: userApprovedAddition", self.html)
        self.assertIn("user_approved_addition=req.user_approved_addition", self.main)
        self.assertIn("Source conflicts are never bypassed", self.main)


if __name__ == "__main__":
    unittest.main()
