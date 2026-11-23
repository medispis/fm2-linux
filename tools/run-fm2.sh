#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
executable="$root/build/smoke-native/fm2"
disc="$root/private/disc"
state="$root/private/fm2-state"

timing=
native_rendering=false
while :; do
    case "${1-}" in
        --experimental-120fps|--original-timing)
            if [ -n "$timing" ]; then
                printf '%s\n' 'Choose only one timing preset.' >&2
                exit 2
            fi
            case "$1" in
                --experimental-120fps) timing=120 ;;
                --original-timing) timing=60 ;;
            esac
            ;;
        --native-rendering) native_rendering=true ;;
        *) break ;;
    esac
    shift
done

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
    if [ ! -f "$root/build/smoke-native/librexgpu-xenos-vulkan.so" ]; then
        printf '%s\n' 'Missing the Vulkan runtime. Rerun setup.' >&2
        exit 1
    fi
    if [ ! -s "$root/private/display-menu/stock.xml" ] ||
       [ ! -s "$root/private/display-menu/options.xml" ]; then
        printf '%s\n' 'Missing native display menu data. Rerun setup.' >&2
        exit 1
    fi
    for category in FM2Display FM2WindowMode FM2AspectMode FM2PerformanceHud \
                    FM2RefreshRate FM2RenderResolution FM2DisplayDefaults; do
        if [ ! -s "$disc/Media/UI/Textures/P_Map/P_OPT/P_OPT_ICON_$category.xds" ]; then
            printf '%s\n' 'Missing native display menu artwork. Rerun setup.' >&2
            exit 1
        fi
    done
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

if [ -n "$timing" ]; then
    for arg do
        option=${arg%%=*}
        option=${option#--}
        case "${option#no-}" in
            ui.video_mode_refresh_rate|video_mode_refresh_rate|gpu.vsync|vsync|\
            gpu.vulkan.unsynced_present)
                printf '%s\n' 'Do not combine a timing preset with refresh-rate or VSync overrides.' >&2
                exit 2
                ;;
        esac
    done
    if [ "$timing" = 120 ]; then
        printf '%s\n' 'Experimental: 120 Hz guest timing, host VSync off. Gameplay timing is not validated.' >&2
        set -- --ui.video_mode_refresh_rate=120 --gpu.vsync=true --gpu.vulkan.unsynced_present=true "$@"
    else
        set -- --ui.video_mode_refresh_rate=60 --gpu.vsync=true --gpu.vulkan.unsynced_present=false "$@"
    fi
fi

if [ "$native_rendering" = true ]; then
    for arg do
        option=${arg%%=*}
        case "$option" in
            --gpu.resolution_scale_x|--gpu.resolution_scale_y|--resolution_scale_x|--resolution_scale_y)
                printf '%s\n' 'Do not combine --native-rendering with render scale overrides.' >&2
                exit 2
                ;;
        esac
    done
    set -- --gpu.resolution_scale_x=1 --gpu.resolution_scale_y=1 "$@"
fi

mkdir -p "$state"
# The native PipeWire backend can produce broken audio on some systems.
# Prefer the local PulseAudio server (including pipewire-pulse) if available.
if [ "${SDL_AUDIO_DRIVER+x}" != x ] && [ -n "${XDG_RUNTIME_DIR-}" ] &&
   [ -S "$XDG_RUNTIME_DIR/pulse/native" ]; then
    SDL_AUDIO_DRIVER=pulseaudio,pipewire,alsa
    export SDL_AUDIO_DRIVER
fi
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
    "$@"
