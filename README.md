# Forza Motorsport 2 for Linux

A native Linux x86-64 recompilation of Forza Motorsport 2. It supports
the unpatched European disc (`4D5307EA`, media ID `3E3180AE`, version `0.0.0.3`).

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

For keyboard controls, run `sh tools/run-fm2.sh --hid.mnk_mode=true`.
Return is Start, Space is A, Backspace is B, WASD is the left stick,
E accelerates, and Q brakes.

The local build runs with Vulkan. Career mode and audio playback were
confirmed by the user. Game files, generated code, and saves are not
included in this repository.

## How this project was made

A human planned and managed this project. AI did most of the implementation,
debugging, and documentation under human direction.
