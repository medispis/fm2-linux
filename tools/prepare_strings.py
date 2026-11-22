#!/usr/bin/env python3
"""Expose the disc's English string tables as loose files for FM2."""

import argparse
from pathlib import Path
import zipfile


def prepare(game_root):
    tables = game_root / "Media" / "StringTables"
    destination = tables / "EN"
    with zipfile.ZipFile(tables / "EN.zip") as archive:
        names = set()
        strings = {}
        for entry in archive.infolist():
            name = entry.filename
            if (
                entry.is_dir()
                or any(char in name for char in "/\\:\0")
                or not name.lower().endswith(".str")
                or name.casefold() in names
            ):
                raise ValueError(f"unexpected string table entry: {name!r}")
            names.add(name.casefold())
            strings[name] = archive.read(entry)
    if not strings:
        raise ValueError("EN.zip contains no string tables")

    if destination.is_symlink():
        raise ValueError(f"refusing to use a symlink: {destination}")
    destination.mkdir(exist_ok=True)
    created = 0
    for name, contents in strings.items():
        path = destination / name
        try:
            with path.open("xb") as output:
                output.write(contents)
                created += 1
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != contents:
                raise ValueError(f"refusing to replace existing file: {path}") from None
    return created, len(strings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_root", type=Path)
    args = parser.parse_args()
    try:
        created, total = prepare(args.game_root)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(f"English string tables: {total} verified, {created} newly written.")


if __name__ == "__main__":
    main()
