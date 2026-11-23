# FM2 player guide

For first-time setup and supported disc details, see the [README](../README.md).

## Controls

Use a controller with the normal launcher, or start FM2 with
`sh tools/run-fm2.sh --hid.mnk_mode=true` for keyboard controls.

| Key | Xbox control |
|---|---|
| Return | Start |
| Space | A / Select |
| Backspace | B / Back |
| W, A, S, D | Left stick |
| E | Accelerate |
| Q | Brake |
| F10 | Open the port's PC Settings panel |

## Display & Performance

From the main menu, open **Options → Display & Performance**. F10 opens
the same preferences in a separate PC Settings panel.

| Setting | Behavior |
|---|---|
| Window Mode | Switches between windowed and fullscreen immediately. Reopen the popup to see the current choice. |
| Aspect Ratio | **Original** fits the image without distortion. **Stretch** fills the window. Neither changes the game's internal render resolution. |
| Performance HUD | Shows guest FPS and average frame time. It does not count distinct frames on the display. |
| Refresh Rate | Switches the saved choice between **Original (60 Hz)** and **Experimental (120 Hz)**. Restart to apply it. The popup shows both the active guest rate and the saved choice. |
| Restore Display Defaults | Requires confirmation. Resets the port's display preferences, not your career or stock FM2 options. Refresh rate resets on restart. |

## Experimental 120 Hz

The experimental mode requests 120 Hz guest timing and allows Vulkan to
present without waiting for the monitor where supported. This can cause
tearing. It does not guarantee 120 distinct frames per second or make a
60 Hz display run at 120 Hz.

Local startup measurements showed about 120 guest swaps per second, but
the 3D main menu produced about 28 swaps per second with draw work at
both settings on the tested AMD Renoir GPU. A 640×480 guest-mode request
did not reduce the menu's 1280×720 swap source. There is no render-scale
option in the native menu.

Race timing, physics, replays, and audio have not been validated at 120 Hz.
To override the saved choice for one launch without rewriting it, use:

```sh
sh tools/run-fm2.sh --original-timing
sh tools/run-fm2.sh --experimental-120fps
```

Use only one of these commands per launch. Put the timing flag first if
you also pass keyboard or other options.

## Saves and preferences

With the standard launcher, saves are under `private/fm2-state/user/`,
and display preferences are in `private/fm2-state/fm2-pc-settings.txt`.
To back up your progress and preferences, close FM2 and copy the user
directory and preference file to a safe location. Setup preserves your
state when you rerun it. Do not delete `private/fm2-state/` to fix a
display problem.
