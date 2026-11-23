# Contributing

Read [AGENTS.md](AGENTS.md) for project rules. The only supported setup
entry point is the command in the [README](README.md#quick-start).

## Project layout

| Path | Purpose |
|---|---|
| `tools/setup-fm2.sh` | Validates the disc, prepares assets, builds the port, and runs the non-gameplay launch check. |
| `tools/build-fm2.sh`, `patches/` | Build the pinned ReXGlue revision with the required runtime patches. |
| `config/fm2-europe-fibers.toml` | Guest fiber shims for the supported European executable. |
| `tools/prepare_display_menu.py`, `src/main.cpp` | Generate the native display menu locally, hook it into FM2's Options flow, and apply host preferences. The stock UI archive and manifest are left intact. |
| `tests/` | Tests for disc inspection, setup helpers, menu preparation, and launcher behavior. |

## Checks before submitting

Run the unit tests and non-gameplay launch check:

```sh
python3 -B -m unittest discover -s tests -q
sh tools/run-fm2.sh --check
```

For setup or runtime changes, run the supported setup command with the
original ISO. Run it again to verify that setup is safe to rerun. Test
menu changes in the menu; do not run races unless requested. Update the
setup workflow, tests, and documentation with any behavior change.

Keep game data, generated code, saves, build outputs, and test captures
local. Source packages use an explicit allowlist in
`tools/package-source.sh`; update it when adding files that belong in the
package.
