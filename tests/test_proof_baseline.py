import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / "app" / "main.py"


class ProofBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
        cls.function = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_visual_proof_prompt"
        )

    def test_constraint_expansion_is_not_active(self):
        called_names = {
            node.func.id
            for node in ast.walk(self.function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertNotIn("apply_visual_proof_constraints", called_names)

    def test_original_negative_prompt_is_preserved(self):
        strings = " ".join(
            node.value
            for node in ast.walk(self.function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
        self.assertIn("extra people", strings)
        self.assertIn("duplicate objects", strings)
        self.assertIn("text, watermark", strings)

    def test_proof_builder_returns_direct_single_frame_prompt(self):
        returns = [
            node for node in ast.walk(self.function) if isinstance(node, ast.Return)
        ]
        self.assertEqual(len(returns), 1)
        value = returns[0].value
        self.assertIsInstance(value, ast.Tuple)
        self.assertEqual(
            [element.id for element in value.elts if isinstance(element, ast.Name)],
            ["single_frame_prompt", "selection_reason", "negative_prompt"],
        )


if __name__ == "__main__":
    unittest.main()
