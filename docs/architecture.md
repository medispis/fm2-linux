# FM2 architecture

This port recompiles one Xbox 360 executable into native Linux x86-64
code. ReXGlue supplies the Xbox-compatible runtime. The port supplies the
disc-specific integration, compatibility fixes, and PC settings. Game
assets still come from the user's disc.

## Build pipeline

```text
European disc ISO
  ├─ inspect_disc.py → verified default.xex
  │                      └─ ReXGlue codegen → generated C++ → Clang / Ninja
  └─ ReXGlue VFS dump → extracted disc
                           ├─ loose English string tables
                           └─ local native-menu inputs

FM2 launcher code + compiled game code + ReXGlue runtime → Linux executable
```

The [setup script](../tools/setup-fm2.sh) checks the disc's embedded XEX
against the supported SHA-256 before extraction. It downloads and verifies
the pinned ReXGlue bootstrap archive and checks out the pinned SDK and
Vulkan Memory Allocator sources. The [build helper](../tools/build-fm2.sh)
checks both source revisions and builds the runtime with the host compiler.
The downloaded SDK extracts the disc and initializes the project. The
port links against the runtime built from source.

[configure_smoke.py](../tools/configure_smoke.py) points the generated
project at the port's [`src/main.cpp`](../src/main.cpp) and includes the
[European fiber shim manifest](../config/fm2-europe-fibers.toml).
On a clean build, the helper runs code generation before configuring
CMake a second time: ReXGlue v0.11.0 reads the generated source list at
configure time. Without the second configure, the generated game objects
would be missing from the link.

| Local path | Contents |
|---|---|
| `private/default.xex` | Verified executable extracted from the ISO. |
| `private/disc/` | Disc tree mounted by the runtime; setup adds loose English `.str` files from the disc archive. |
| `private/display-menu/` | Original and transformed Options XML generated locally. |
| `build/smoke/` | ReXGlue project and generated C++. |
| `build/smoke-native/` | Linux executable and adjacent runtime libraries. |
| `private/fm2-state/` | Saves, logs, preferences, and caches for the standard launcher. |

Setup finishes with `sh tools/run-fm2.sh --check`. This checks the mounted
XEX hash, a required English string table, the generated menu files, and
the executable's shared-library dependencies. It does not start FM2 or
verify that Vulkan can render on a specific driver. The
[README](../README.md#quick-start) remains the only supported setup procedure.

## Runtime compatibility

The [launcher](../tools/run-fm2.sh) selects Vulkan and supplies separate
disc, state, and shader-cache paths. The application derives from
ReXGlue's `TitleApp`. The generated code calls into ReXGlue for services
such as guest file I/O, graphics, input, and audio.

- **Fibers:** The build replaces five guest fiber entry points as a set.
  Thread conversion, creation, switching, and destruction must agree on
  fiber handles and continuations. The manifest addresses apply to the
  supported European XEX only.
- **Files and audio banks:** The title hook makes aliases for unambiguous
  `.fsb` basenames under `Media/Audio`. Duplicate names are left alone so
  the title can still open the correct bank by its full path. The hook
  also mounts a writable guest cache under the user directory, separate
  from the disc mount.
- **Audio buffering:** The launcher requests 1,024 SDL device sample
  frames by default and sets ReXGlue's audio queue limit to 24 frames.
  These settings provide headroom for short stalls; the SDL value is a
  request, not a guarantee about the device buffer.

### ReXGlue patches

| Patch | Behavior |
|---|---|
| [Asynchronous reads](../patches/rexglue-async-read.patch) | On the patched successful read path, return `X_STATUS_PENDING` for asynchronous guest handles. The completed I/O status block still carries the result. |
| [Empty resolves](../patches/rexglue-empty-resolve.patch) | Skip Xenos resolves whose regions are empty after clipping instead of asserting or failing. |
| [Unsynced presentation](../patches/rexglue-unsynced-present.patch) | Let Vulkan choose a non-VSync presentation mode independently of guest vblank pacing, where the host supports it. |
| [Presentation setting lifetime](../patches/rexglue-present-until-launch.patch) | Let the port apply the saved host presentation preference before title launch. |
| [Refresh setting lifetime](../patches/rexglue-refresh-until-launch.patch) | Publish the selected guest refresh rate before title launch, even after startup-only settings are frozen. Otherwise a saved 120 Hz choice could change host presentation while leaving guest timing at 60 Hz. |

## Timing and evidence

Guest refresh rate, guest swaps, Vulkan presentation, and physical
display refresh are separate. Experimental mode requests 120 Hz guest
timing, keeps ReXGlue's guest vblank pacing enabled, and requests
unsynced host presentation. It does not interpolate frames or guarantee
120 new images per second. The performance HUD reports ReXGlue's guest
frame statistics, not display scanout or distinct images.

Local tests observed around 120 guest swaps per second at startup, but
the same 3D menu produced about 28 swaps with draw work per second in
both timing modes on the tested AMD Renoir system. Neither measurement
establishes race timing or distinct frame delivery on a 120 Hz display.
Use the [player guide](player-guide.md#experimental-120-hz) for the
current support status and launch overrides.

See [Native menu internals](native-menu.md) for the flow patch, guest to
host event bridge, and preference lifecycle.
