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

Open **Options → Display & Performance** to toggle fullscreen in FM2's
native menu. Fullscreen applies immediately and is saved separately from
career progress. **F10** still opens the separate PC Settings panel.

The local build runs with Vulkan. Career mode and audio playback were
confirmed by the user. Game files, generated code, and saves are not
included in this repository.

## Experimental refresh rate

In **F10 → PC Settings**, set **Frame Rate (next launch)** to
**Experimental (120 Hz)** and restart. The default is **Original (60 Hz)**.
The experimental mode requests 120 Hz guest timing and lets Vulkan present
without waiting for the monitor where supported.
This can cause tearing. Local startup measurements showed about 120 guest
swaps per second, up from about 60. Swaps can repeat images and do not
measure distinct frames shown on the display. In the 3D main menu on the
test machine, both modes produced about 28 swaps per second with draw
work. The higher refresh setting alone did not speed up that scene.
On the test machine's AMD Renoir GPU, GPU utilization stayed at 99% in
both modes. Requesting 640×480 did not lower the 1280×720 swap-source
resolution in this menu.

This is not a verified 120 FPS mode. A 120 Hz or faster display is needed
to verify visible motion at that rate. Race timing, physics, replays,
and audio are not validated in this mode. To override the saved setting for
one launch, use `sh tools/run-fm2.sh --original-timing` or
`sh tools/run-fm2.sh --experimental-120fps`.

## How this project was made

A human planned and managed this project. AI did most of the implementation,
debugging, and documentation under human direction.
