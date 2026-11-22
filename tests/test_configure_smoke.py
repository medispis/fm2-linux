from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from configure_smoke import replace_once


class ConfigureSmokeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "template"

    def test_replace_twice_then_leave_unchanged(self):
        self.path.write_text("src/main.cpp\nsrc/main.cpp\n")
        for _ in range(2):
            replace_once(self.path, "src/main.cpp\n", "../../src/main.cpp)\n", count=2)
        self.assertEqual(self.path.read_text(), "../../src/main.cpp)\n../../src/main.cpp)\n")

    def test_reject_unexpected_template(self):
        self.path.write_text("customized\n")
        with self.assertRaisesRegex(ValueError, "unexpected ReXGlue template"):
            replace_once(self.path, "original", "replacement")
        self.assertEqual(self.path.read_text(), "customized\n")
