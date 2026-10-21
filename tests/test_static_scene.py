import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from proof_scene import source_scene_fallback


class StaticSceneTests(unittest.TestCase):
    def test_unrecognised_object_keeps_the_complete_explicit_scene(self):
        source = "A single red ceramic cup on a wooden table beside a window, soft daylight."
        result = source_scene_fallback(source, "the principal subject", "the described location")
        self.assertIn(source, result)
        self.assertNotIn("principal subject", result)
        self.assertNotIn("described location", result)

    def test_known_person_and_location_keep_the_sequence_extractor(self):
        self.assertIsNone(source_scene_fallback("A woman enters a room and sits down.", "a woman", "a room"))
