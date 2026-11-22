import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile


spec = importlib.util.spec_from_file_location(
    "prepare_strings", Path(__file__).resolve().parents[1] / "tools" / "prepare_strings.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PrepareStringsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.tables = self.root / "Media" / "StringTables"
        self.tables.mkdir(parents=True)

    def make_zip(self, *entries):
        with ZipFile(self.tables / "EN.zip", "w") as archive:
            for name, contents in entries:
                archive.writestr(name, contents)

    def test_extract_and_repeat(self):
        self.make_zip(("Example.str", b"sample"))
        self.assertEqual(module.prepare(self.root), (1, 1))
        self.assertEqual(module.prepare(self.root), (0, 1))
        self.assertEqual((self.tables / "EN" / "Example.str").read_bytes(), b"sample")

    def test_reject_nested_path(self):
        self.make_zip(("Example.str", b"sample"), ("../bad.str", b"bad"))
        with self.assertRaisesRegex(ValueError, "unexpected"):
            module.prepare(self.root)
        self.assertFalse((self.tables / "EN").exists())

    def test_do_not_replace_existing_file(self):
        self.make_zip(("Example.str", b"sample"))
        module.prepare(self.root)
        output = self.tables / "EN" / "Example.str"
        output.write_bytes(b"existing file")
        with self.assertRaisesRegex(ValueError, "refusing to replace"):
            module.prepare(self.root)
        self.assertEqual(output.read_bytes(), b"existing file")
