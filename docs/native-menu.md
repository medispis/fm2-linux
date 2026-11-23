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

### Preview artwork

The Options scene looks up its right-hand preview by category name.
Setup converts the port's [original monitor artwork](../assets/display-preview.dds)
from a 512×512 BC3 DDS into the tiled, byte-swapped XDS format used by the
supported disc. It installs the preview as loose files for the category
and each of its rows under `private/disc/Media/UI/Textures/P_Map/P_OPT/`.
The artwork was AI-generated for this port. The stock `Textures.zip`,
`UI.zip`, and `Media/zipmanifest.xml` are not edited; the game still draws
the menu, selection highlights, and controller prompts.

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
  `fullscreen`, `refresh_hz`, `aspect`, `performance_hud`, and `render_resolution`.
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
- Render Resolution saves the guest render profile or matched Vulkan
  draw scale for the next launch. The popup reports the launch scale and saved
  preset separately. `--native-rendering` forces 1× on both axes for one launch.

### Below-native resolution investigation

Changing the reported guest video mode to 960×540 did not change the
1280×720 swap source. A local prototype changed FM2's guest device
parameters to 960×540 instead. It changed some Vulkan color and depth
allocations to 960 pixels wide, but the 1280×512 MSAA targets and the
1280×720 swap source remained. The intro appeared cropped. A follow-up
trace reached the same 3D Arcade menu in both variants. Both used a
1280-pixel surface pitch and 4× MSAA for the main scene, with 1280-pixel-wide
resolves to a 1280×720 destination. The menu remained correctly framed
because its rendering path kept the original dimensions. The guest
device hook alone cannot provide a 540p mode.

The implemented 540p preset updates profile 0 before FM2 allocates its
3D targets. It verifies the stock profile and then scales the three
horizontal strip boundaries from `0, 256, 512, 720` to `0, 192, 384, 540`
while retaining 4× MSAA. The Arcade menu trace confirmed a 960×540
viewport, 960×192 strips, and a 960×540 swap source. The 1080p preset
uses that profile with Vulkan draw scaling set to 2× on both axes;
the Arcade trace confirmed a 1920×1080 viewport and swap source.
The same mechanism supports the menu-tested 640-, 800-, and 1120-pixel
guest widths and 2× rendering on the 800- and 1120-pixel profiles.
The preset table selects exact sizes rather than rounding arbitrary
dimensions. The hook runs only for the matching European call site;
no files on the disc are changed.

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
