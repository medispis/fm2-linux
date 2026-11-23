#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

case "${1-}" in
    ''|--prepare-only) ;;
    *) printf '%s\n' 'Usage: sh tools/build-fm2.sh [--prepare-only]' >&2; exit 2 ;;
esac

sdk_source="$root/build/rexglue-src"
vma="$root/build/vma/include"
project="$root/build/smoke"
manifest="$project/fm2_manifest.toml"
if [ ! -f "$sdk_source/CMakeLists.txt" ] || [ ! -f "$vma/vk_mem_alloc.h" ]; then
    printf '%s\n' 'Check out the pinned ReXGlue and VMA sources first. See README.md.' >&2
    exit 1
fi
if [ "$(git -C "$sdk_source" rev-parse HEAD)" != a3e1d82678ca20d68d4837a8e9ee4652ff073745 ]; then
    printf '%s\n' 'The SDK patches require ReXGlue v0.11.0. See README.md.' >&2
    exit 1
fi
if [ "$(git -C "$vma/.." rev-parse HEAD)" != 1d8f600fd424278486eade7ed3e877c99f0846b1 ]; then
    printf '%s\n' 'The build requires Vulkan Memory Allocator v3.3.0. See README.md.' >&2
    exit 1
fi

if [ ! -f "$manifest" ]; then
    : "${REXGLUE_SDK:?Set REXGLUE_SDK to the unpacked v0.11.0 Linux SDK directory}"
    python3 tools/configure_smoke.py --check-xex private/default.xex
    mkdir -p "$project/assets"
    cp -n private/default.xex "$project/assets/default.xex"
    (
        cd "$project"
        "$REXGLUE_SDK/bin/rexglue" init --project-name fm2 --xex-path assets/default.xex
    )
fi
python3 tools/configure_smoke.py

for patch in rexglue-async-read.patch rexglue-empty-resolve.patch rexglue-unsynced-present.patch \
             rexglue-present-until-launch.patch rexglue-refresh-until-launch.patch; do
    patch="$root/patches/$patch"
    # The follow-up patch changes a line added by unsynced-present.
    if [ "$patch" = "$root/patches/rexglue-unsynced-present.patch" ] &&
        git -C "$sdk_source" apply --reverse --check \
            "$root/patches/rexglue-present-until-launch.patch" 2>/dev/null; then
        continue
    fi
    if ! git -C "$sdk_source" apply --reverse --check "$patch" 2>/dev/null; then
        git -C "$sdk_source" apply "$patch"
    fi
done
if [ "${1-}" = --prepare-only ]; then
    printf '%s\n' 'FM2 build inputs are ready.'
    exit 0
fi

jobs=${FM2_BUILD_JOBS:-8}
configure() {
    cmake -S "$project" -B build/smoke-native -G Ninja \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
        -DREXSDK_DIR="$sdk_source" -DREXGLUE_VMA_INCLUDE_DIR="$vma" \
        -DCMAKE_BUILD_TYPE=Release
}

configure
if [ ! -f "$project/generated/default/sources.cmake" ]; then
    cmake --build build/smoke-native --target fm2_codegen --parallel "$jobs"
    # ReXGlue v0.11.0 only adds the generated objects if this list exists
    # at configure time.
    configure
fi
cmake --build build/smoke-native --target fm2 --parallel "$jobs"
