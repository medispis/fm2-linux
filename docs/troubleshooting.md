# Troubleshooting

Start with the [supported disc and prerequisites](../README.md#quick-start).
Use the [setup script](../README.md#quick-start) after updates instead of
applying patches or rebuilding components by hand.

| Symptom | What to check |
|---|---|
| Unsupported `default.xex` or wrong disc hash | Use an ISO from the unpatched European release listed in the README. Other regions or patched executables are not supported. Keep the original ISO and any saves. |
| A required tool or shared library is missing | Install the missing system prerequisite, then rerun setup with your ISO. Setup does not install system packages. If the failure persists, keep the first relevant error from setup. |
| The native Display & Performance entry is missing after updating | Rerun setup. It generates the menu data locally from the supported disc. F10 can still open the separate PC Settings panel. |
| The screen tears, motion stalls, or audio sounds wrong in 120 Hz mode | Try the original timing first. `sh tools/run-fm2.sh --original-timing` does not overwrite the saved preference. If the issue goes away, set **Original (60 Hz)** in the menu before restarting. |
| The game starts fullscreen and you cannot reach Options | Try `sh tools/run-fm2.sh --ui.fullscreen=false` for one launch. Use the native Window Mode or F10 controls to save your preferred mode. |

To check the disc executable, generated menu files, and shared-library
dependencies without starting FM2:

```sh
sh tools/run-fm2.sh --check
```

## Reporting a problem

Include the project commit, Linux distribution, GPU and driver, the command
you ran, and steps to reproduce. For display or audio reports, include the
active and saved refresh rates and whether the issue happens at 60 Hz.
The standard launcher keeps logs under `private/fm2-state/logs/`. Share
only the relevant excerpt and remove personal paths or identifiers.

Do not attach ISO or XEX files, extracted assets, generated game code,
saves, binaries, or test captures to public issues.
