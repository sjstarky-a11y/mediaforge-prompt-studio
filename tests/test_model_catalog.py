import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from model_catalog import (  # noqa: E402
    build_model_inventory,
    is_valid_model_id,
    load_model_catalog,
    model_prompt_prefix,
    parse_dmr_model_ids,
)


class ModelCatalogTests(unittest.TestCase):
    def test_dmr_payload_parses_unique_model_ids(self):
        payload = {
            "data": [
                {"id": "ai/qwen2.5:3B-Q4_K_M"},
                {"id": "ai/qwen3:8B-Q4_K_M"},
                {"id": "ai/qwen2.5:3B-Q4_K_M"},
                {"id": "not a valid model"},
            ]
        }

        self.assertEqual(
            parse_dmr_model_ids(payload),
            ["ai/qwen2.5:3B-Q4_K_M", "ai/qwen3:8B-Q4_K_M"],
        )

    def test_dmr_raw_array_payload_parses(self):
        payload = [
            {
                "id": "sha256:41045df49cc0",
                "tags": ["docker.io/ai/qwen2.5:3B-Q4_K_M"],
            },
            "ai/qwen3:8B-Q4_K_M",
        ]

        self.assertEqual(
            parse_dmr_model_ids(payload),
            ["ai/qwen2.5:3B-Q4_K_M", "ai/qwen3:8B-Q4_K_M"],
        )

    def test_dmr_native_payload_ignores_digest_and_reads_all_tags(self):
        payload = [
            {
                "id": "sha256:dbe29fa01698",
                "tags": [
                    "docker.io/ai/gemma3:1B-Q4_K_M",
                    "docker.io/studio/custom-model:q4",
                ],
            }
        ]

        self.assertEqual(
            parse_dmr_model_ids(payload),
            ["ai/gemma3:1B-Q4_K_M", "studio/custom-model:q4"],
        )

    def test_inventory_preserves_custom_installed_models(self):
        catalog = {
            "models": [
                {
                    "id": "ai/qwen2.5:3B-Q4_K_M",
                    "display_name": "Qwen 2.5 3B",
                    "profile": "Light",
                }
            ]
        }

        inventory = build_model_inventory(
            ["custom/studio-model:q4"],
            "ai/qwen2.5:3B-Q4_K_M",
            catalog,
        )

        ids = [item["id"] for item in inventory["installed"]]
        self.assertEqual(
            ids,
            ["ai/qwen2.5:3B-Q4_K_M", "custom/studio-model:q4"],
        )
        self.assertEqual(inventory["installed"][1]["validation"], "unverified")

    def test_custom_model_names_are_human_readable(self):
        inventory = build_model_inventory(
            ["ai/gemma3:1B-Q4_K_M", "ai/gemma4:4B-Q4_K_XL"],
            "ai/gemma3:1B-Q4_K_M",
            {"models": []},
        )

        self.assertEqual(
            [item["display_name"] for item in inventory["installed"]],
            ["Gemma 3 1B", "Gemma 4 4B"],
        )

    def test_qwen3_catalog_entry_disables_thinking(self):
        catalog = {
            "models": [
                {"id": "ai/qwen3:8B-Q4_K_M", "prompt_mode": "no_think"}
            ]
        }

        self.assertEqual(
            model_prompt_prefix("ai/qwen3:8B-Q4_K_M", catalog),
            "/no_think\n",
        )
        self.assertEqual(model_prompt_prefix("custom/model:q4", catalog), "")

    def test_catalog_loader_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "catalog.json"
            path.write_text("{invalid", encoding="utf-8")
            catalog = load_model_catalog(path)

        self.assertEqual(catalog["models"], [])

    def test_model_identifier_validation(self):
        self.assertTrue(is_valid_model_id("ai/qwen2.5:3B-Q4_K_M"))
        self.assertTrue(is_valid_model_id("studio/custom-model:q4"))
        self.assertFalse(is_valid_model_id("qwen-without-namespace"))
        self.assertFalse(is_valid_model_id("ai/model tag"))


if __name__ == "__main__":
    unittest.main()
