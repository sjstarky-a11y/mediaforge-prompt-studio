import gzip
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_release import (
    LINUX,
    WINDOWS,
    _deterministic_gzip,
    build_releases,
    collect_source_files,
    package_name,
    sha256_file,
)


ROOT = Path(__file__).resolve().parent.parent


class ReleaseBuilderTests(unittest.TestCase):
    def test_gzip_stream_is_platform_neutral_and_valid(self):
        payload = b"MediaForge deterministic release\n" * 5000
        encoded = _deterministic_gzip(payload)

        self.assertEqual(encoded[0:3], b"\x1f\x8b\x08")
        self.assertEqual(encoded[4:8], b"\x00\x00\x00\x00")
        self.assertEqual(encoded[9], 0xFF)
        self.assertEqual(gzip.decompress(encoded), payload)

    def test_platform_packages_keep_only_relevant_launchers(self):
        windows = {path.as_posix() for path in collect_source_files(ROOT, WINDOWS)}
        linux = {path.as_posix() for path in collect_source_files(ROOT, LINUX)}

        self.assertIn("MediaForge-Windows.cmd", windows)
        self.assertIn("PACKAGING-V0.2.md", windows)
        self.assertIn("install.ps1", windows)
        self.assertNotIn("install.sh", windows)
        self.assertIn("install.sh", linux)
        self.assertIn("PACKAGING-V0.2.md", linux)
        self.assertIn("scripts/mediaforge-common.sh", linux)
        self.assertNotIn("install.ps1", linux)

    def test_release_names_are_platform_specific(self):
        self.assertEqual(
            package_name("v0.2-dev", WINDOWS),
            "MediaForge-Prompt-Studio-v0.2-dev-Windows-x64",
        )
        self.assertEqual(
            package_name("v0.2-dev", LINUX),
            "MediaForge-Prompt-Studio-v0.2-dev-Linux-x86_64",
        )

    def test_release_archives_are_reproducible_and_have_matching_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = build_releases(ROOT, base / "first", "v0.2-test")
            second = build_releases(ROOT, base / "second", "v0.2-test")

            first_bytes = {path.name: path.read_bytes() for path in first}
            second_bytes = {path.name: path.read_bytes() for path in second}
            self.assertEqual(first_bytes, second_bytes)

            checksum_file = next(path for path in first if path.name.startswith("SHA256SUMS"))
            checksum_lines = checksum_file.read_text(encoding="utf-8").splitlines()
            expected = {
                path.name: sha256_file(path)
                for path in first
                if path != checksum_file
            }
            actual = {}
            for line in checksum_lines:
                digest, name = line.split("  ", 1)
                actual[name] = digest
            self.assertEqual(actual, expected)

    def test_release_info_does_not_claim_models_are_bundled(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = build_releases(ROOT, Path(temporary), "v0.2-test")
            windows_zip = next(path for path in artifacts if path.suffix == ".zip")

            import zipfile

            with zipfile.ZipFile(windows_zip) as archive:
                info_name = next(name for name in archive.namelist() if name.endswith("/RELEASE-INFO.json"))
                info = json.loads(archive.read(info_name))
                self.assertTrue(
                    all(member.compress_type == zipfile.ZIP_STORED for member in archive.infolist())
                )
            self.assertFalse(info["models_included"])
            self.assertEqual(info["runtime_selection"], "automatic CPU or NVIDIA")


if __name__ == "__main__":
    unittest.main()
