import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from fidelity_concepts import (  # noqa: E402
    auto_correct_narrow_lighting_review,
    detect_unrequested_creative_issues,
    output_structure_issues,
)


class FidelityConceptTests(unittest.TestCase):
    def test_flags_weak_model_creative_inventions(self):
        issues = detect_unrequested_creative_issues(
            source="A filmmaker enters an abandoned cinema carrying a camera bag.",
            target=(
                "A dimly lit cinema suggests a mystery and a journey. "
                "The filmmaker conveys introspection and determination in a melancholic scene."
            ),
            mode="improve",
        )

        self.assertTrue(any("emotional tone" in issue for issue in issues))
        self.assertTrue(any("narrative premise" in issue for issue in issues))
        self.assertTrue(any("lighting treatment" in issue for issue in issues))

    def test_does_not_flag_explicit_source_direction(self):
        source = (
            "A determined filmmaker enters a dimly lit cinema on a mysterious journey."
        )
        issues = detect_unrequested_creative_issues(
            source=source,
            target=source,
            mode="improve",
        )
        self.assertEqual(issues, [])

    def test_cinematic_mode_allows_lighting_but_not_emotion(self):
        issues = detect_unrequested_creative_issues(
            source="A filmmaker enters a cinema.",
            target="A dimly lit cinema with a melancholic filmmaker.",
            mode="cinematic",
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("emotional tone", issues[0])

    def test_improve_auto_corrects_lighting_only_review(self):
        source = "A filmmaker enters an abandoned cinema carrying a small camera bag."
        target = (
            "PROMPT DIAGNOSIS\n\n- Clear subject.\n- Clear action.\n\n"
            "IMPROVED PROMPT\n\n"
            "A filmmaker enters an abandoned cinema carrying a small camera bag, "
            "capturing the dimly lit interior with clean composition and controlled lighting."
        )
        issues = detect_unrequested_creative_issues(source, target, "improve")

        corrected, corrections = auto_correct_narrow_lighting_review(
            source=source,
            target=target,
            mode="improve",
            issues=issues,
        )

        self.assertNotIn("dimly lit", corrected.lower())
        self.assertIn("capturing the interior", corrected.lower())
        self.assertEqual(corrections, ["specific lighting treatment"])
        self.assertEqual(
            detect_unrequested_creative_issues(source, corrected, "improve"),
            [],
        )

    def test_improve_does_not_auto_correct_mixed_review(self):
        source = "A filmmaker enters an abandoned cinema."
        target = "A determined filmmaker enters a dimly lit abandoned cinema."
        issues = detect_unrequested_creative_issues(source, target, "improve")

        corrected, corrections = auto_correct_narrow_lighting_review(
            source=source,
            target=target,
            mode="improve",
            issues=issues,
        )

        self.assertEqual(corrected, target)
        self.assertEqual(corrections, [])

    def test_improve_preserves_explicit_source_lighting(self):
        source = "A filmmaker enters a dimly lit abandoned cinema."
        target = "A filmmaker enters a dimly lit abandoned cinema."

        corrected, corrections = auto_correct_narrow_lighting_review(
            source=source,
            target=target,
            mode="improve",
            issues=[],
        )

        self.assertEqual(corrected, target)
        self.assertEqual(corrections, [])

    def test_improve_structure_accepts_three_bullets(self):
        result = (
            "PROMPT DIAGNOSIS\n\n- One\n- Two\n- Three\n\n"
            "IMPROVED PROMPT\n\nA safe prompt."
        )
        self.assertEqual(output_structure_issues(result, "improve"), [])

    def test_improve_structure_accepts_one_bullet(self):
        result = (
            "PROMPT DIAGNOSIS\n\n- The prompt is already clear.\n\n"
            "IMPROVED PROMPT\n\nA safe prompt."
        )
        self.assertEqual(output_structure_issues(result, "improve"), [])

    def test_improve_structure_rejects_zero_bullets(self):
        result = (
            "PROMPT DIAGNOSIS\n\nThe prompt is already clear.\n\n"
            "IMPROVED PROMPT\n\nA safe prompt."
        )
        issues = output_structure_issues(result, "improve")
        self.assertEqual(len(issues), 1)
        self.assertIn("detected 0", issues[0])

    def test_improve_structure_rejects_six_bullets(self):
        bullets = "\n".join(f"* Item {index}" for index in range(6))
        result = f"PROMPT DIAGNOSIS\n\n{bullets}\n\nIMPROVED PROMPT\n\nPrompt."
        issues = output_structure_issues(result, "improve")
        self.assertEqual(len(issues), 1)
        self.assertIn("detected 6", issues[0])

    def test_model_adapter_accepts_clean_prompt_without_doctor_headers(self):
        issues = output_structure_issues(
            result=(
                "A filmmaker enters an abandoned cinema carrying a small camera bag, "
                "using clean composition and controlled lighting."
            ),
            mode="improve",
            require_mode_structure=False,
        )
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
