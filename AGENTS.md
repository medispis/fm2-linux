# FM2 project instructions

- Keep `sh tools/setup-fm2.sh "/path/to/disc.iso"` as the only supported setup
  command. Do not replace automation with manual build or patch instructions.
- For every change to setup, dependencies, runtime patches, asset preparation,
  or launch behavior, update the setup workflow and its checks in the same
  change. Keep the README quick start to the setup and launch commands.
- Pin dependencies and verify downloaded SDK archives. Setup must be safe to
  rerun, must preserve user saves and inputs, and must not launch the game
  automatically.
- Keep game files, generated game code, saves, build products, and test
  captures out of commits and source packages.
- Run setup tests and the non-gameplay launch check before committing. Do not
  run gameplay tests unless the user asks. Ask before pushing.
