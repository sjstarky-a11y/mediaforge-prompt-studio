import unittest
from pathlib import Path
from scripts.public_sources import is_private_path


class PublicSourceTests(unittest.TestCase):
    def test_private_files_are_excluded_at_any_depth(self):
        for path in (".env.local", "models/private.local.json", "app/local/catalog.json",
                     "app/.env", "data/model.bin", "runtime/selection.json", "app/private.key"):
            self.assertTrue(is_private_path(Path(path)), path)

    def test_public_defaults_and_source_are_allowed(self):
        for path in (".env.example", "models/model-catalog.json", "intel_runtime/probe.py"):
            self.assertFalse(is_private_path(Path(path)), path)
