#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
mkdir -p build
archive=build/fm2-linux-source.tar.gz

# Only project source and build inputs. Do not archive game data or
# binaries, even if they are present in the workspace.
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
    --transform='s,^,fm2-linux/,' -czf "$archive" -- \
    .gitignore AGENTS.md README.md config/fm2-europe-fibers.toml \
    patches/rexglue-async-read.patch patches/rexglue-empty-resolve.patch src/main.cpp \
    patches/rexglue-unsynced-present.patch patches/rexglue-present-until-launch.patch \
    patches/rexglue-refresh-until-launch.patch \
    tests/test_configure_smoke.py tests/test_inspect_disc.py tests/test_prepare_strings.py \
    tests/test_prepare_display_menu.py tests/test_run_fm2.py \
    tools/build-fm2.sh tools/configure_smoke.py tools/inspect_disc.py tools/package-source.sh \
    tools/prepare_display_menu.py tools/prepare_strings.py tools/probe_x11.py \
    tools/run-fm2.sh tools/setup-fm2.sh
sha256sum "$archive"
