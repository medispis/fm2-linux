#!/usr/bin/env python3
"""Attach the FM2 launcher and build-specific settings to a ReXGlue project."""

import argparse
import hashlib
from pathlib import Path

EUROPE_XEX_SHA256 = "9726066f0c546c4e51340ed02a32ae44a89d4175de82a2d55aaaf5451d9b120a"


def replace_once(path, original, updated, count=1):
    text = path.read_text()
    if text.count(updated) == count and original not in text:
        return
    if text.count(original) != count or updated in text:
        raise ValueError(f"unexpected ReXGlue template in {path}")
    path.write_text(text.replace(original, updated))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-xex", type=Path, help="only check the supplied executable")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    project = workspace / "build" / "smoke"
    try:
        with (args.check_xex or project / "assets" / "default.xex").open("rb") as xex:
            if hashlib.file_digest(xex, "sha256").hexdigest() != EUROPE_XEX_SHA256:
                raise ValueError("unsupported default.xex; the European disc hash must match")
        if args.check_xex:
            print("European FM2 executable hash verified.")
            return
        replace_once(
            project / "fm2_manifest.toml",
            "includes = []",
            'includes = ["../../config/fm2-europe-fibers.toml"]',
        )
        replace_once(
            project / "CMakeLists.txt",
            " src/main.cpp)",
            " ../../src/main.cpp)",
            count=2,
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print("Configured FM2 launcher and European fiber shims.")


if __name__ == "__main__":
    main()
