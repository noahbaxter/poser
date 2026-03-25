# AudioPlugin

JUCE audio plugin. VST3/AU on macOS, VST3 on Windows, VST3/LV2/CLAP on Linux.

## Build

```bash
./scripts/build.sh              # Release build + install
./scripts/build.sh debug        # Debug build
./scripts/standalone.sh         # Build and launch standalone app
./scripts/watch.sh              # Auto-rebuild on src/web changes
./scripts/clean.sh              # Remove build artifacts
```

## Test

```bash
./scripts/test.sh               # Run unit + integration + compliance
./scripts/test.sh unit          # C++ unit tests only
./scripts/test.sh integration   # Python integration tests only
./scripts/test.sh compliance    # pluginval compliance tests only
./scripts/test.sh validate      # pluginval at strictness 10 (or: validate 5)
```

## Adding Web Assets

1. Add file path to `juce_add_binary_data(AudioPluginData ...)` in `CMakeLists.txt`
2. Register in `PluginEditor.cpp` `getResource()` table
3. BinaryData naming: hyphens removed, dots become underscores (`my-file.js` -> `myfile_js`)

## Rules

- Don't run build/test commands -- tell me to run them
- Don't increment or commit changes to `VERSION`
