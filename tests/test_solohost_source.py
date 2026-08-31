import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLOHOST = ROOT / "solohost"


class SoloHostSourceTests(unittest.TestCase):
    def setUp(self):
        self.main = (SOLOHOST / "app" / "main.py").read_text(encoding="utf-8")
        self.html = (SOLOHOST / "app" / "index.html").read_text(encoding="utf-8")
        self.hero_server = (SOLOHOST / "image_flux" / "server.py").read_text(encoding="utf-8")
        self.core = (SOLOHOST / "config_options.core.yml").read_text(encoding="utf-8")
        self.hero = (SOLOHOST / "config_options.hero.yml").read_text(encoding="utf-8")
        self.public = (SOLOHOST / "config_options.yml").read_text(encoding="utf-8")
        self.compose = (SOLOHOST / "docker-compose.yml").read_text(encoding="utf-8")

    def test_profile_sources_are_valid(self):
        ast.parse(self.main)
        ast.parse(self.hero_server)
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
            "aerialcroatia/mediaforge-prompt-studio:0.3-solohost.7",
            self.compose,
        )
        self.assertIn(
            "aerialcroatia/mediaforge-image-flux:0.3-solohost.7",
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

    def test_single_and_hero_visual_paths_share_optional_service(self):
        self.assertNotIn('id="fastProofMode"', self.html)
        self.assertIn('id="singleProofMode"', self.html)
        self.assertIn('id="heroProofMode"', self.html)
        self.assertIn("Generate One Proof Frame", self.html)
        self.assertIn("Generate Hero Frame Set", self.html)
        self.assertIn('frame_count: frameCount', self.html)
        self.assertIn('frame_count: Literal[1, 3] = 3', self.main)
        self.assertIn('total not in {1, 3}', self.hero_server)
        self.assertIn('"total": job["total"]', self.hero_server)
        self.assertIn("local_files_only=True", self.hero_server)
        self.assertIn('"downloaded": downloaded', self.hero_server)
        self.assertIn("data.ready === true || data.downloaded === true", self.html)

    def test_review_approval_reaches_hero_backend(self):
        self.assertIn('id="approveReviewBtn"', self.html)
        self.assertIn("user_approved_addition: userApprovedAddition", self.html)
        self.assertIn("user_approved_addition=req.user_approved_addition", self.main)
        self.assertIn("Source conflicts are never bypassed", self.main)


if __name__ == "__main__":
    unittest.main()
