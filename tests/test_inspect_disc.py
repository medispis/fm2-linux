import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import inspect_disc


def xex():
    info = struct.pack(">4I", 0x3E3180AE, 3, 3, 0x4D5307EA) + bytes(8)
    names = b"xam.xex\0"
    library = struct.pack(">I32xHHI", 44, 0, 1, 0x82001000)
    imports = struct.pack(">III", 12 + len(names) + len(library), len(names), 1) + names + library
    fields = struct.pack(">6I", 0x00040006, 48, 0x000103FF, 72, 0x00010100, 0x8240D650)
    return struct.pack(">4s5I", b"XEX2", 0, 72 + len(imports), 0, 0, 3) + fields + info + imports


def image(executable, left=0):
    block = inspect_disc.SECTOR_SIZE
    entry = struct.pack("<HHIIBB", left, 0, 34, len(executable), 0, 11) + b"default.xex"
    data = bytearray(34 * block + len(executable))
    start = 32 * block
    data[start : start + 20] = inspect_disc.MAGIC
    struct.pack_into("<II", data, start + 20, 33, len(entry))
    data[start + block - 20 : start + block] = inspect_disc.MAGIC
    data[33 * block : 33 * block + len(entry)] = entry
    data[34 * block :] = executable
    return data


class InspectDiscTests(unittest.TestCase):
    def test_partition_and_xex_metadata(self):
        executable = xex()
        with tempfile.TemporaryFile() as stream:
            stream.write(image(executable))
            stream.flush()
            base, files = inspect_disc.disc_files(stream)
            self.assertEqual(base, 0)
            self.assertEqual(set(files), {"default.xex"})
            data = inspect_disc.read_at(stream, *files["default.xex"])
        info = inspect_disc.xex_info(data)
        self.assertEqual(info["title_id"], "4D5307EA")
        self.assertEqual(info["media_id"], "3E3180AE")
        self.assertEqual(info["entry_point"], "8240D650")
        self.assertEqual(info["import_table_records"], {"xam.xex": 1})
        self.assertEqual(info["sha256"], hashlib.sha256(executable).hexdigest())

    def test_reject_out_of_bounds_directory_node(self):
        with tempfile.TemporaryFile() as stream:
            stream.write(image(xex(), left=0xFFFF))
            stream.flush()
            with self.assertRaisesRegex(ValueError, "invalid directory node"):
                inspect_disc.disc_files(stream)
