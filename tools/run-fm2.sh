#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
executable="$root/build/smoke-native/fm2"
disc="$root/private/disc"
state="$root/private/fm2-state"

if [ ! -x "$executable" ] || [ ! -f "$disc/default.xex" ] || [ ! -d "$disc/Media" ]; then
    printf '%s\n' 'Build FM2 and extract the disc first. See README.md.' >&2
    exit 1
fi

if [ "${1-}" = --check ]; then
    python3 "$root/tools/configure_smoke.py" --check-xex "$disc/default.xex"
    if [ ! -f "$disc/Media/StringTables/EN/AIDiff.str" ]; then
        printf '%s\n' 'Missing English string tables. See README.md.' >&2
        exit 1
    fi
    for file in "$executable" "$root/build/smoke-native"/librex*.so; do
        dependencies=$(ldd "$file") || exit 1
        if printf '%s\n' "$dependencies" | grep -F 'not found'; then
            printf 'Missing shared dependencies for %s\n' "$file" >&2
            exit 1
        fi
    done
    printf '%s\n' 'FM2 launch files and shared libraries verified; the game was not started.'
    exit 0
fi

mkdir -p "$state"
# Give the audio producer more room to absorb shader and scheduling stalls.
: "${SDL_AUDIO_DEVICE_SAMPLE_FRAMES:=1024}"
export SDL_AUDIO_DEVICE_SAMPLE_FRAMES
exec "$executable" \
    --title.game_root="$disc" \
    --app.root="$state" \
    --app.cache_root="$state/shaders" \
    --apu.max_queued_frames=24 \
    --gpu.driver=vulkan \
    --gpu.xenos.async_shader_compilation=false \
    --log.categories.gpu=error \
    --ui.fullscreen=false \
    "$@"
