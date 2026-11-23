# Native menu internals

**Options → Display & Performance** uses the game's own Options scene
and confirmation popups. F10 is a separate ImGui panel. Both front ends
change the same host preferences.

## From disc to native Options

1. [prepare_display_menu.py](../tools/prepare_display_menu.py) extracts
   `Flows/Options.xml` from `Media/UI.zip` during setup and checks its
   SHA-256. It adds a category to the stock Options queries and builds
   a child scene with rows for the port's display settings.
2. The script validates the resulting XML and makes sure it fits in the
   original parser buffer. It stores the stock and transformed copies
   under `private/display-menu/`. It does **not** rewrite `UI.zip` or
   `zipmanifest.xml`.
3. At runtime, the title first reads its own unmodified archive. The
   hook in [`src/main.cpp`](../src/main.cpp) matches the supported
   flow-loader call site and the exact original XML bytes, including
   the terminator, before substituting the generated flow. It then calls the
   original parser. Other flows are not changed. Neither the archive
   reader nor the title's integrity checks are patched for this menu.

The new page uses the existing `P_OPT.xgf` scene to show the rows and
`PopUp_Message.xgf` to handle confirmation and Back. The flow supplies
the new data and events; the disc still supplies the scene assets.

## Guest-to-host bridge

| European hook | Role |
|---|---|
| `sub_824CF490`, caller `0x825E1158` | Substitute the matched Options buffer and call the original XML parser. |
| `sub_824B6DB8`, caller `0x825F24D8` | Observe the converted Lua event string. Recognize only the port's display-action names and post the action to the host UI thread. |
| `sub_825F4EE8` | Answer the port's read-only Window Mode and Refresh Rate queries with a Lua string. Other calls go to the original `UI:fireEvent` implementation. |

The action event and the menu navigation are separate. The guest flow
owns the scene transitions; the host action changes ReXGlue settings
and saves the preferences. The HUD uses an ImGui overlay to read guest
frame statistics without taking menu input. Only the **setting** is in
the native page.

## Preferences and launch order

- `fm2-pc-settings.txt` lives next to the ReXGlue configuration file.
  With the standard launcher, this is `private/fm2-state/`. It stores
  `fullscreen`, `refresh_hz`, `aspect`, and `performance_hud`.
  Neither the native page nor F10 writes these settings into career saves.
- The writer replaces the preference file by renaming a temporary file.
  The older fullscreen/refresh file format still loads; missing
  aspect-ratio and HUD values use the defaults.
- Fullscreen, letterboxing, and HUD visibility are live. The window
  popup reads the live fullscreen setting rather than the file.
  Changing refresh rate only writes the preference. At the next
  launch, the port applies the saved 120 Hz profile before the title
  starts unless an explicit override takes precedence. The active
  guest rate is captured at title launch and displayed separately.
- The two timing flags supply a complete timing override for one
  launch. They do not rewrite `fm2-pc-settings.txt`.

## Changing this code

The XEX hash, XML hash, hook addresses, call sites, buffer size, and
Lua ABI are all assumptions of the supported build. Recheck them
together if you change the target executable or SDK. Do not copy game
XML, Lua, textures, generated code, or captures into the repository.

If the launch check passes but the native category is missing, look for
`Installed native FM2 Display & Performance flow` in the runtime log.
The launch check verifies that both XML files exist and are nonempty;
the log entry confirms that the guest parser received the replacement.
After confirming a setting, look for `Native Display & Performance: saved`
to distinguish a dispatched host action from a menu transition alone.

For a menu change, verify that stock Options still work, Select and Back
route correctly, and cancellation does not save. Check live settings
on screen and confirm saved settings after restart. For timing changes,
test a normal launch and a launch override with the same saved file.
See [Contributing](../CONTRIBUTING.md#checks-before-submitting) for the
setup and launch checks.
