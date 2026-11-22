#!/usr/bin/env python3
"""Identify the base FM2 build without unpacking the entire disc."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import struct


SECTOR_SIZE = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
XGD2_OFFSET = 0x0FD90000


def read_at(image, offset, size):
    image.seek(offset)
    data = image.read(size)
    if len(data) != size:
        raise ValueError(f"short read at disc offset {offset:#x}")
    return data


def disc_files(image):
    image_size = os.fstat(image.fileno()).st_size
    for base in (XGD2_OFFSET, 0):
        if base + 33 * SECTOR_SIZE > image_size:
            continue
        descriptor = read_at(image, base + 32 * SECTOR_SIZE, SECTOR_SIZE)
        if descriptor[:20] == descriptor[-20:] == MAGIC:
            break
    else:
        raise ValueError("expected an XGD2 or game-partition-only image")

    root_sector, root_size = struct.unpack_from("<II", descriptor, 20)
    directories = [("", root_sector, root_size)]
    seen = set()
    files = {}
    while directories:
        parent, sector, size = directories.pop()
        if not size:
            continue
        if sector in seen or size > 32 * 1024 * 1024:
            raise ValueError(f"invalid directory: {parent or '/'}")
        seen.add(sector)
        table = read_at(image, base + sector * SECTOR_SIZE, size)
        nodes = [0]
        visited = set()
        while nodes:
            node = nodes.pop()
            if node in visited or node + 14 > len(table):
                raise ValueError(f"invalid directory node: {parent or '/'}")
            visited.add(node)
            left, right, sector, length, attributes, name_size = struct.unpack_from(
                "<HHIIBB", table, node
            )
            start, end = node + 14, node + 14 + name_size
            if not name_size or end > len(table):
                raise ValueError(f"invalid directory name: {parent or '/'}")
            name = table[start:end].decode("latin-1")
            if name in (".", "..") or any(c in name for c in "/\\\0"):
                raise ValueError(f"invalid path component: {name!r}")
            path = f"{parent}/{name}" if parent else name
            if attributes & 0x10:
                directories.append((path, sector, length))
            else:
                offset = base + sector * SECTOR_SIZE
                if offset + length > image_size or path in files:
                    raise ValueError(f"invalid file extent or duplicate path: {path}")
                files[path] = (offset, length)
            nodes.extend(child * 4 for child in (left, right) if child)
    return base, files


def xex_info(data):
    if data[:4] != b"XEX2":
        raise ValueError("default.xex does not have an XEX2 header")
    header_size = struct.unpack_from(">I", data, 8)[0]
    count = struct.unpack_from(">I", data, 20)[0]
    if not 24 + count * 8 <= header_size <= len(data):
        raise ValueError("invalid XEX2 header size")
    header = data[:header_size]
    fields = dict(struct.iter_unpack(">II", header[24:24 + count * 8]))
    media, version, base_version, title = struct.unpack_from(
        ">4I", header, fields[0x00040006]
    )
    offset = fields[0x000103FF]
    size, strings_size, strings_count = struct.unpack_from(">III", header, offset)
    strings_start = offset + 12
    pos, strings_end, end = strings_start, strings_start + strings_size, offset + size
    if not pos <= strings_end <= end <= len(header):
        raise ValueError("invalid XEX2 import table size")
    names = []
    for _ in range(strings_count):
        terminator = header.index(b"\0", pos, strings_end)
        names.append(header[pos:terminator].decode("ascii"))
        pos = strings_start + ((terminator - strings_start + 4) & ~3)

    libraries = {}
    pos = strings_end
    while pos < end:
        if end - pos < 0x28:
            raise ValueError("truncated XEX2 import library")
        length = struct.unpack_from(">I", header, pos)[0]
        index, records = struct.unpack_from(">HH", header, pos + 0x24)
        if length < 0x28 + records * 4 or pos + length > end:
            raise ValueError("invalid XEX2 import library size")
        name = names[index & 0xFF]
        libraries[name] = libraries.get(name, 0) + records
        pos += length

    return {
        "title_id": f"{title:08X}",
        "media_id": f"{media:08X}",
        "version_raw": f"{version:08X}",
        "base_version_raw": f"{base_version:08X}",
        "entry_point": f"{fields[0x00010100]:08X}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "import_table_records": libraries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--extract-xex", type=Path, help="write to a new file")
    parser.add_argument("--expect-xex-sha256", help="reject discs whose default.xex does not match")
    args = parser.parse_args()
    try:
        with args.iso.open("rb") as image:
            base, files = disc_files(image)
            modules = sorted(path for path in files if path.lower().endswith(".xex"))
            path, = (path for path in modules if path.lower() == "default.xex")
            data = read_at(image, *files[path])
        report = {
            "partition_offset": f"{base:#x}",
            "file_count": len(files),
            "files_by_top_level": dict(sorted(Counter(
                path.split("/", 1)[0] for path in files
            ).items())),
            "xex_modules": modules,
            "default_xex": xex_info(data),
        }
        if args.expect_xex_sha256 and report["default_xex"]["sha256"] != args.expect_xex_sha256:
            raise ValueError("unsupported default.xex; the European disc hash must match")
        if args.extract_xex:
            with args.extract_xex.open("xb") as output:
                output.write(data)
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, KeyError, IndexError, struct.error) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
