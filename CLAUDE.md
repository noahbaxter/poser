# Poser

EQ plugin shipping curated frequency response curves of famous mics and guitar cab speakers.
Pick a mic/cab, dial a blend knob, signal takes on that tonal character.
NOT a mic modeler, NOT a cab sim — it's a creative mixing/flavor tool. See `docs/spec.md`.

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

## Data Tools

Offline Python tools for generating curve data. All images go to `/tmp/poser/`.

```
tools/
  curves/                    # Frequency response curve extraction
    digitize.py              # Extract curves from freq response chart images
    compare.py               # Validate curves across sources
    build.py                 # All curve sources → data/curves/extracted_components.json
    generate_header.py       # extracted_components.json → src/CurveData.h
  ir/                        # Impulse response decomposition
    inventory.py             # Index IR collection from external drive
    extract_components.py    # Decompose IRs into cab/speaker/mic/position
    decomposition.py         # Shared DSP/analysis library
    preview.py               # Quick IR visualization
    preview_cabs.py          # Multi-cab speaker comparison

data/
  curves/
    atk/                     # Audio Test Kitchen measured responses (CSV)
    digitized/               # Curves extracted from chart images (JSON)
    extracted_components.json # Compiled curve data (generated)
  ir/
    ir_inventory.json        # IR collection index (generated)
    v30_cab_comparison.json  # Cab analysis results (generated)
```

## Adding Web Assets

1. Add file path to `juce_add_binary_data(PoserData ...)` in `CMakeLists.txt`
2. Register in `PluginEditor.cpp` `getResource()` table
3. BinaryData naming: hyphens removed, dots become underscores (`my-file.js` -> `myfile_js`)

## Rules

- Don't run build/test commands -- tell me to run them
- Don't increment or commit changes to `VERSION`
