import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from proof_constraints import apply_visual_proof_constraints  # noqa: E402


class ProofConstraintTests(unittest.TestCase):
    def test_abandoned_cinema_is_visually_anchored(self):
        prompt, negative = apply_visual_proof_constraints(
            "A filmmaker enters an abandoned cinema.",
            "Photorealistic cinematic still of a filmmaker entering an abandoned cinema.",
            "duplicate objects",
        )

        self.assertIn("rows of cinema seats", prompt)
        self.assertIn("projection screen", prompt)
        self.assertIn("visibly abandoned and decayed", prompt)
        self.assertIn("warehouse", negative)
        self.assertIn("industrial hall", negative)

    def test_single_camera_bag_blocks_duplicate_luggage(self):
        prompt, negative = apply_visual_proof_constraints(
            "A filmmaker carries a small camera bag.",
            "Photorealistic cinematic still of a filmmaker.",
            "duplicate objects",
        )

        self.assertIn("Exactly one small camera bag", prompt)
        self.assertIn("No additional bag", prompt)
        self.assertIn("multiple bags", negative)
        self.assertIn("additional backpack", negative)

    def test_plural_camera_bags_are_not_forced_to_one(self):
        prompt, negative = apply_visual_proof_constraints(
            "A filmmaker carries two camera bags.",
            "Photorealistic cinematic still.",
            "duplicate objects",
        )

        self.assertNotIn("Exactly one", prompt)
        self.assertNotIn("multiple bags", negative)


if __name__ == "__main__":
    unittest.main()
