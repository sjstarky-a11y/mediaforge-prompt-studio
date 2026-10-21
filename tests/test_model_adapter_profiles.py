import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / "app" / "main.py"
FUNCTIONS = {
    "_observer_extract_target",
    "_adapter_clean_prompt_text",
    "_adapter_section_breaks",
    "_adapter_result",
    "_build_generic_video_prompt",
    "_build_runway_gen4_5_prompt",
    "_build_veo_3_1_prompt",
    "_build_kling_video_3_0_prompt",
    "_build_model_ready_prompt",
}


def load_adapter_functions() -> dict[str, object]:
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS
    ]
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {"re": re}
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)
    return namespace


class ModelAdapterProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.functions = load_adapter_functions()
        cls.build = staticmethod(cls.functions["_build_model_ready_prompt"])

    def test_simple_prompt_is_transparently_compatible_for_every_profile(self):
        source = (
            "A filmmaker enters an abandoned cinema carrying a small camera bag, "
            "using a clean composition and controlled lighting."
        )

        for profile in (
            "generic_video",
            "runway_gen4_5",
            "veo_3_1",
            "kling_video_3_0",
        ):
            with self.subTest(profile=profile):
                _, prompt, changed, notes = self.build(profile, source, "improve")
                self.assertEqual(prompt, source)
                self.assertFalse(changed)
                self.assertIn("compatible as-is", " ".join(notes))

    def test_explicit_camera_direction_gets_profile_specific_formatting(self):
        source = (
            "A filmmaker enters an abandoned cinema. "
            "The camera maintains a steady, low-angle shot, following the filmmaker."
        )

        outputs = {}
        for profile in ("runway_gen4_5", "veo_3_1", "kling_video_3_0"):
            name, prompt, changed, notes = self.build(profile, source, "improve")
            outputs[profile] = prompt
            self.assertTrue(changed, name)
            self.assertTrue(notes, name)
            self.assertIn("filmmaker", prompt.lower())

        self.assertEqual(len(set(outputs.values())), 3)
        self.assertIn("A steady low-angle camera shot", outputs["runway_gen4_5"])
        self.assertIn("The camera remains steady in a low-angle shot", outputs["veo_3_1"])
        self.assertIn("Steady low-angle camera shot", outputs["kling_video_3_0"])

    def test_veo_separates_only_existing_audio_and_dialogue_cues(self):
        source = (
            "A filmmaker enters an abandoned cinema. "
            "Audio: quiet footsteps. Dialogue: \"Is anyone here?\""
        )
        _, prompt, changed, notes = self.build("veo_3_1", source, "improve")

        self.assertTrue(changed)
        self.assertIn("\nAudio: quiet footsteps.", prompt)
        self.assertIn("\nDialogue: \"Is anyone here?\"", prompt)
        self.assertIn("audio or dialogue", " ".join(notes).lower())

    def test_kling_separates_only_existing_shot_structure(self):
        source = (
            "Shot 1: A filmmaker enters an abandoned cinema. "
            "Shot 2: The filmmaker stops beneath the projection screen."
        )
        _, prompt, changed, notes = self.build("kling_video_3_0", source, "improve")

        self.assertTrue(changed)
        self.assertIn("\nShot 2:", prompt)
        self.assertIn("shot", " ".join(notes).lower())

    def test_simple_prompt_does_not_gain_model_specific_inventions(self):
        source = "A filmmaker enters an abandoned cinema carrying a small camera bag."

        for profile in ("runway_gen4_5", "veo_3_1", "kling_video_3_0"):
            with self.subTest(profile=profile):
                _, prompt, _, _ = self.build(profile, source, "improve")
                self.assertNotIn("Audio:", prompt)
                self.assertNotIn("Dialogue:", prompt)
                self.assertNotIn("Shot 1:", prompt)
                self.assertNotIn("camera shot", prompt.lower())


if __name__ == "__main__":
    unittest.main()
