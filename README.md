# Forza Motorsport 2 Linux recompilation

The supported target is the unpatched European disc on Linux x86-64.
Native driving, Vulkan rendering and profile reload were verified locally.
The user tested and confirmed career mode and audio playback.

## Identify the disc

Use an ISO dumped from your own disc. The inspection tool uses Python 3's
standard library. It reads the Xbox game partition without unpacking the
assets and optionally extracts just the main executable.

```sh
python3 tools/inspect_disc.py "/path/to/disc.iso"
mkdir -p private
python3 tools/inspect_disc.py "/path/to/disc.iso" --extract-xex private/default.xex
sha256sum private/default.xex
```

Extraction will not overwrite an existing file. Keep the ISO, executable,
and any generated game code local.

| Field | Observed value |
| --- | --- |
| Title ID | `4D5307EA` |
| Media ID | `3E3180AE` |
| Version / base version | `0.0.0.3` / `0.0.0.3` (raw `00000003`) |
| Entry point | `8240D650` |
| `default.xex` SHA-256 | `9726066f0c546c4e51340ed02a32ae44a89d4175de82a2d55aaaf5451d9b120a` |

The disc has 2,345 file entries and one directly visible XEX, `default.xex`.
Its XEX header has 344 import table records for `xboxkrnl.exe` and 196 for
`xam.xex`. These counts include thunk records and are not counts of distinct
imported functions.

## Run the ReXGlue smoke test

Use [ReXGlue v0.11.0](https://github.com/rexglue/rexglue-sdk/releases/tag/v0.11.0).
The published Linux x86-64 SDK archive has SHA-256
`e7d543ab8dde2c7839836a0417bfe84691c10f93357ec2c023fa98d3d315803b`.
Set `REXGLUE_SDK` to the absolute path to the unpacked `linux-amd64` directory.
From the workspace root:

```sh
mkdir -p build/smoke/assets
cp -n private/default.xex build/smoke/assets/default.xex
(
    cd build/smoke || exit
    "$REXGLUE_SDK/bin/rexglue" init --project-name fm2 --xex-path assets/default.xex &&
    "$REXGLUE_SDK/bin/rexglue" --log-file codegen.log codegen
)
```

On an existing smoke project, skip `init` and run `codegen` directly.

### First run results

- ReXGlue v0.11.0 wrote 252 files. It reported four distinct unresolved
  branch targets during emission: `0x82756590`, `0x8276C388`, `0x8279FF14`,
  and `0x827A7034`. The CLI returned success despite these diagnostics.
  The full log is `build/smoke/codegen.log`.
  `0x82756590` is already emitted inside the function at `0x82756584`,
  immediately after a call to `KeBugCheck`. The incoming branch from
  `0x82754EF0` needs to enter at that instruction, not at the function
  start. Do not add all four addresses as function starts without checking
  their context.
- The generated `fm2_init.cpp` has 265 distinct named callable import
  mappings. This is separate from the raw record counts above and does not
  establish that the runtime implements every import.
- The prebuilt SDK uses libstdc++ 13. CMake rejects it on the test host,
  which uses libstdc++ 16. Do not bypass the ABI check.
- Source configuration passed with Clang 23 and a local checkout of Vulkan
  Memory Allocator. The full disc extraction in `private/disc` has 2,345
  files, and its `default.xex` matches the hash above.

### Configure the SDK from source

Use ReXGlue v0.11.0 (`a3e1d82678ca20d68d4837a8e9ee4652ff073745`, with
submodules) and Vulkan Memory Allocator v3.3.0
(`1d8f600fd424278486eade7ed3e877c99f0846b1`) in local checkouts.
Use Python 3.11 or newer, Clang 20 or newer, CMake 3.25 or newer, Ninja,
and Vulkan 1.4.313 or newer development files on Linux x86-64.
See the [ReXGlue Linux prerequisites](https://docs.rexglue.com/getting-started/#install-the-tools)
for the system windowing and audio development libraries.
Check out the build dependencies locally:

```sh
git clone --branch v0.11.0 --recurse-submodules \
    https://github.com/rexglue/rexglue-sdk.git build/rexglue-src
git clone --branch v3.3.0 \
    https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator.git build/vma
sh tools/build-fm2.sh
```

The build script can initialize the smoke project if it does not exist.
For that first run, export `REXGLUE_SDK` as described above and extract
`private/default.xex`. The script applies the runtime patches and can
be rerun without reapplying them. Set `FM2_BUILD_JOBS` to change the
default of eight parallel build jobs. On a clean build it runs code
generation, then reconfigures CMake so ReXGlue v0.11.0 links the
generated objects.
Use `sh tools/build-fm2.sh --prepare-only` to check the pinned inputs
and apply the patches without compiling.

Run the current Vulkan build with `sh tools/run-fm2.sh`. Add
`--hid.mnk_mode=true` to map the keyboard to a controller. Return is
Start, Space is A, Backspace is B, W/A/S/D are the left stick, E is the
right trigger (accelerate), and Q is the left trigger (brake). The
launcher keeps the shader cache and user data under `private/fm2-state`.
The launcher uses synchronous shader compilation, matching the verified
Vulkan runs. It sets GPU logging to `error` to avoid flooding the log with
repeated fetch warnings. Command-line settings can override these defaults.
Run `sh tools/run-fm2.sh --check` to verify the disc build, English
string tables and shared libraries without starting the game.

### Choppy audio

The user reported choppy playback, then confirmed sound was working with
the updated launcher. The launcher requests a 1,024-sample SDL device
buffer and lets each ReXGlue stream queue 24 frames. This gives the game
more time to recover from short scheduling stalls, at the cost of more
audio latency.

`SDL_AUDIO_DEVICE_SAMPLE_FRAMES=2048 sh tools/run-fm2.sh` requests a
larger device buffer. Append `--apu.max_queued_frames=32` to increase
the ReXGlue queue. To compare with the original launcher defaults, use
`SDL_AUDIO_DEVICE_SAMPLE_FRAMES=0` and `--apu.max_queued_frames=8`.

Extract the disc to a fresh `private/disc` directory before launching:

```sh
mkdir -p private/disc
"$REXGLUE_SDK/bin/rexglue" vfs dump "/path/to/disc.iso" private/disc
python3 tools/prepare_strings.py private/disc
```

FM2 tries to open `Media/StringTables/EN` as a directory, but the English
tables on the starting disc are in `EN.zip`.

For a startup-only test, use the desktop display, SDL dummy audio, and the
null GPU. The SDL dummy **video** driver does not work here: the SDK title
app requires a window.

```sh
mkdir -p private/smoke-state
SDL_AUDIODRIVER=dummy \
    timeout -k 5s 30s build/smoke-native/fm2 \
    --title.game_root="$PWD/private/disc" \
    --app.root="$PWD/private/smoke-state" \
    --gpu.driver=null --kernel.headless=true --log.level=debug \
    >build/smoke-native-runtime.log 2>&1
```

A runtime log that announces the main thread does not prove game code ran.
To verify entry, use GDB with the same environment and program arguments:

```sh
SDL_AUDIODRIVER=dummy \
    gdb -q -nx -batch -ex 'tbreak __imp__xstart' -ex run -ex bt \
    --args build/smoke-native/fm2 \
    --title.game_root="$PWD/private/disc" \
    --app.root="$PWD/private/smoke-state" \
    --gpu.driver=null --kernel.headless=true
```

The `__imp__xstart` symbol is the generated body for guest address
`0x8240D650`. A hit confirms that the native executable entered FM2 code;
it does not confirm that initialization completed.

The unmodified build hit this breakpoint (`build/smoke-native-entry.log`).
Its first runtime abort was the branch from `0x82754EF0` to `0x82756590`
on a game thread. The destination saves and restores a fiber context and
sets guest stack pointers. Resolving the branch alone would not switch
native stacks. The experimental fiber shims in
`config/fm2-europe-fibers.toml` replace the related fiber routines as a
group. To include them, use
`includes = ["../../config/fm2-europe-fibers.toml"]` under `[entrypoint]`
in the smoke manifest and rebuild. The shimmed build created and deleted
fibers without hitting the old abort. A Vulkan run created a swapchain on
RADV Renoir before the next fault.

The project launcher in `src/main.cpp` adds read-only filesystem aliases
for audio banks with unambiguous basenames. The file trace confirms that
the three early banks opened and returned data. Banks with matching
basenames, such as engine banks for different detail levels, still
require their full paths. The launcher also mounts a writable per-user
cache separately from the read-only disc.
The startup audio probe captured nonzero PCM samples on SDL's PipeWire
playback thread (`build/fm2-audio-verify.log`). This verifies output to
the host audio backend, not the accuracy of every sound effect.

The next startup fault is a null read in `sub_824CDF18`. GDB shows that
the XML parser receives invalid bytes when it loads `FontMap.xml` from
`Fonts.zip`. Python verifies the archive CRC and reads the correct XML,
so the on-disc file is not the source of the invalid bytes. See
`build/fm2-font-parse-gdb.log` and `build/fm2-file-trace.log`.
With the asynchronous read patch, the game passed that fault, loaded
vehicle assets and UI videos, and ran until the 18-second test timeout
(`build/smoke-native-async-vulkan.log`). Vulkan window captures in
`build/fm2-frame-4s.png` and `build/fm2-frame-16s.png` verify that the
intro renders. The cache mount also let FM2 create all five
`replication_stream_*` files without writing to the disc folder.

The native Vulkan build also reached the title screen, car selection,
and the assists menu after keyboard input. Evidence: `build/fm2-menu-80s.png`,
`build/fm2-menu-92s.png`, and `build/fm2-menu-120s.png`. The car preview
area was blank during the capture, and the GPU log contains repeated
empty resolve errors. FM2 wrote `ForzaProfile` and `PlayerDatabase` files
under `private/fm2-state/user`. A later boot mounted the existing profile
and opened both files (`build/fm2-career.log`).

The Vulkan build loaded Laguna Seca with a Mitsubishi Eclipse GT and
rendered the track, car, and HUD. `build/fm2-race-74s.png` captures the
countdown and `build/fm2-race-82s.png` shows lap 1 at 57 mph. The test later
returned to a dimmed car selection screen without a fatal process crash.
This did not establish a finished lap or results screen.

A separate driving probe reached 89 mph after pressing the throttle,
slowed to 5 mph after braking, opened Pause, and resumed. The evidence
is in `build/fm2-drive-79s.png`, `build/fm2-drive-91s.png`,
`build/fm2-drive-96s.png`, and `build/fm2-drive-122s.png`.

After the empty-resolve patch, the previously blank car preview rendered
in `build/fm2-finish-135s.png`. The retest log contains no empty-resolve
errors, but it still reports invalid texture fetch constants.

On Nissan Speedway, an exhibition race loaded with seven AI opponents.
Quitting the running race brought up the Race Results screen, which
correctly displayed DNF (`build/fm2-oval-focused-187s.png`). This checks
the results UI, not a completed race. A subsequent drive crossed the
start line and reached lap 1 of 2 (`build/fm2-oval-drive-185s.png`).
The captured frame stopped changing at race time `02:34.668` in that
run while the process stayed alive. This is a historical automated
test result; no further gameplay tests are planned.

Career mode reached region and difficulty selection in the native build
(`build/fm2-career-select-214s.png` and `build/fm2-career-select-255s.png`).
The next run set up a European career, bought a VW Golf GTI Mk2, and
reached the Career Main Menu with 2,000 CR
(`build/fm2-career-garage-282s.png`). The file trace shows the game
replaced `PlayerDatabase` and reopened `ForzaProfile` during setup
(`build/fm2-career-garage.log`). The user subsequently confirmed
career mode in their own gameplay test.

## Package the project source

`sh tools/package-source.sh` creates `build/fm2-linux-source.tar.gz`
locally. It includes the launcher, patch files, build tools and tests.
It does not include disc images, extracted assets, generated game code,
runtime dependencies or saves.
