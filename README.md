# Forza Motorsport 2 for Linux

A native Linux x86-64 recompilation of Forza Motorsport 2 using Vulkan.
It supports the unpatched European disc (`4D5307EA`, media ID `3E3180AE`,
version `0.0.0.3`). Bring your own disc image; this repository does not
include game files or a prebuilt game.

## Quick start

Use an ISO dumped from your own disc. Run these commands from this project:

```sh
sh tools/setup-fm2.sh "/path/to/your-disc.iso"
sh tools/run-fm2.sh
```

Setup verifies and extracts the disc, downloads pinned build tools, applies
the patches, compiles the game, and checks the result. It does not start
the game. You can rerun setup after an update; it preserves your saves.

You need Python 3.11+, Clang 20+, CMake 3.25+, Ninja, Git, curl, bsdtar,
and the [ReXGlue Linux system prerequisites](https://docs.rexglue.com/getting-started/#install-the-tools).
Setup does not install system packages.

## Project status

Career mode and audio playback were confirmed on the local build. **Options
→ Display & Performance** integrates the port's display controls into FM2's
native menu. Original 60 Hz timing is the default; **120 Hz is experimental**,
not a verified 120 FPS mode.

- [Player guide](docs/player-guide.md): controls, display settings, refresh
  overrides, and save locations.
- [Troubleshooting](docs/troubleshooting.md): setup failures, launch recovery,
  and what to include in a bug report.
- [Technical architecture](docs/architecture.md): recompilation, runtime
  patches, timing, and how the native menu works.
- [Contributing](CONTRIBUTING.md): project layout, verification, and what
  must stay out of commits.

## How this project was made

A human planned and managed this project. AI did most of the implementation,
debugging, and documentation under human direction.
