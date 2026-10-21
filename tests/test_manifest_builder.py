import unittest

from scripts.build_manifest import canonical_content, build_manifest


class ManifestBuilderTests(unittest.TestCase):
    def test_text_line_endings_are_platform_neutral(self):
        lf = b"first\nsecond\n"
        crlf = b"first\r\nsecond\r\n"
        cr = b"first\rsecond\r"

        self.assertEqual(canonical_content(crlf), lf)
        self.assertEqual(canonical_content(cr), lf)

    def test_manifest_order_is_identical_across_operating_systems(self):
        names = [entry["file"] for entry in build_manifest()]
        self.assertEqual(names, sorted(names))

    def test_binary_content_is_not_modified(self):
        binary = b"\x89PNG\r\n\x1a\n\x00binary\r\n"
        self.assertEqual(canonical_content(binary), binary)


if __name__ == "__main__":
    unittest.main()
