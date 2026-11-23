#!/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
    printf '%s\n' 'Usage: sh tools/setup-fm2.sh "/path/to/your-disc.iso"' >&2
    exit 2
fi
iso=$(CDPATH='' cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

for tool in python3 clang clang++ cmake ninja git curl bsdtar sha256sum ldd; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Required tool not found: %s\n' "$tool" >&2
        exit 1
    fi
done

mkdir -p private build
expected=9726066f0c546c4e51340ed02a32ae44a89d4175de82a2d55aaaf5451d9b120a
set -- "$iso" --expect-xex-sha256 "$expected"
if [ ! -f private/default.xex ]; then
    set -- "$@" --extract-xex private/default.xex
fi
python3 tools/inspect_disc.py "$@"
python3 tools/configure_smoke.py --check-xex private/default.xex

sdk="$root/build/rexglue-sdk-0.11.0/linux-amd64"
if [ ! -x "$sdk/bin/rexglue" ]; then
    download=$(mktemp -d "$root/build/sdk-download.XXXXXX")
    archive="$download/sdk.zip"
    curl --fail --location --silent --show-error \
        https://github.com/rexglue/rexglue-sdk/releases/download/v0.11.0/rexglue-sdk-0.11.0-linux-amd64.zip \
        -o "$archive"
    printf '%s  %s\n' e7d543ab8dde2c7839836a0417bfe84691c10f93357ec2c023fa98d3d315803b \
        "$archive" | sha256sum -c -
    bsdtar -xf "$archive" -C "$download"
    [ -x "$download/linux-amd64/bin/rexglue" ]
    mkdir -p "$(dirname -- "$sdk")"
    mv -T -- "$download/linux-amd64" "$sdk"
    rm -- "$archive"
    rmdir -- "$download"
fi

if [ ! -e build/rexglue-src ]; then
    git clone --depth 1 --branch v0.11.0 --recurse-submodules \
        https://github.com/rexglue/rexglue-sdk.git build/rexglue-src
fi
if [ ! -e build/vma ]; then
    git clone --depth 1 --branch v3.3.0 \
        https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator.git build/vma
fi

if [ ! -e private/disc ]; then
    disc=$(mktemp -d "$root/private/disc-extract.XXXXXX")
    "$sdk/bin/rexglue" vfs dump "$iso" "$disc"
    python3 tools/configure_smoke.py --check-xex "$disc/default.xex"
    mv -T -- "$disc" private/disc
fi
python3 tools/configure_smoke.py --check-xex private/disc/default.xex
python3 tools/prepare_strings.py private/disc
python3 tools/prepare_display_menu.py private/disc private/display-menu
REXGLUE_SDK="$sdk" sh tools/build-fm2.sh
sh tools/run-fm2.sh --check
printf '%s\n' 'Setup complete. Launch with: sh tools/run-fm2.sh'
