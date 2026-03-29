# Poser

EQ plugin shipping curated frequency response curves of famous mics and guitar cab speakers.
Pick a mic/cab, dial a blend knob, signal takes on that tonal character.
NOT a mic modeler, NOT a cab sim — it's a creative mixing/flavor tool. See `docs/spec.md`.

JUCE audio plugin. VST3/AU on macOS, VST3 on Windows, VST3/LV2/CLAP on Linux.

## Build

```bash
./scripts/build.sh              # Release build + install
./scripts/build.sh debug        # Debug build
./scripts/build.sh standalone   # Build and launch standalone app
./scripts/build.sh curves       # Regenerate curve data only
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
  curves/
    manage.py                # Entry point: prepare / build
    registry.py              # Mic definitions — edit this to add/remove mics
    digitize.py              # Extraction engine (mask export, curve digitization)
    compile.py               # ATK + digitized → extracted_components.json → CurveData.h
    validate.py              # ATK vs digitized agreement check
  ir/
    inventory.py             # Index IR collection from external drive
    extract_components.py    # Decompose IRs into cab/speaker/mic/position
    decomposition.py         # Shared DSP/analysis library
    preview.py               # Quick IR visualization
    preview_cabs.py          # Multi-cab speaker comparison

data/
  datasheets/              # Manufacturer datasheet PNGs (committed, primary source)
  curves/
    sources/                 # Cached source PNGs from RecordingHacks (legacy fallback)
    masks/                   # Red pixel masks for digitization (committed, hand-editable)
    atk/                     # Audio Test Kitchen measured responses (CSV)
    digitized/               # Curves extracted from masks (JSON, generated)
    extracted_components.json # Compiled curve data (generated)
  ir/
    ir_inventory.json        # IR collection index (generated)
    v30_cab_comparison.json  # Cab analysis results (generated)
```

## Adding a Mic

### Quick version (datasheet — preferred)

```bash
# 1. Add mic to MICS in tools/curves/registry.py with datasheet config
# 2. Place manufacturer datasheet PNG in data/datasheets/
# 3. Measure plot_bounds, freq_range, db_range, color from the image
#    (use tools/curves/detect_bounds.py for initial estimates)
# 4. Build everything (digitize → compile → generate header)
python3 tools/curves/manage.py build
# 5. Check comparison plots in /tmp/poser/, adjust config if needed
# 6. Rebuild plugin and listen
```

### Quick version (RH fallback — legacy)

```bash
# 1. Add mic to MICS in tools/curves/registry.py with rh_id
# 2. Download source image and export mask
python3 tools/curves/manage.py prepare
# 3. If mask has multiple curves (proximity variants, switch positions):
#    - Open data/curves/masks/{slug}.png in an image editor
#    - Duplicate it — erase unwanted lines in each copy
#    - Save as {slug}_1.png, {slug}_2.png, etc.
# 4. Build everything
python3 tools/curves/manage.py build
# 5. Rebuild plugin and listen
```

### Details

**Registry** (`tools/curves/registry.py`) is the single source of truth for all
mic definitions. Each entry maps a slug to a display name and curve source config.

**Priority**: ATK CSV > datasheet > hand-edited masks > RH source image.

**Datasheets** are manufacturer frequency response PNGs in `data/datasheets/`.
Each mic's `datasheet` config specifies the image file, plot area pixel bounds,
axis ranges, and curve color. The digitizer extracts curves using these explicit
coordinates — no auto-detection needed. For multi-curve images (proximity variants,
switch positions), add a `curves` list with `line_style: "solid"/"dashed"` to
discriminate lines. For hard cases (overlapping black curves on black grid),
the mask editing workflow still works as a fallback.

**RH source images** (legacy) are 476x159 RGBA PNGs from RecordingHacks with red
curves. `prepare` downloads them to `data/curves/sources/` and exports red pixel
masks to `data/curves/masks/`. Only used when no datasheet config exists.

**Masks** are white PNGs with red curve pixels only. For mics with multiple curves,
make copies named `{slug}_1.png`, `{slug}_2.png` etc, erasing unwanted lines in each.

**ATK mics** (SM57, SM58, SM7B, C414, D4, U87) use lab-measured CSVs as ground truth
and take priority over all other sources. To validate: `python3 tools/curves/validate.py`

## Adding Web Assets

1. Add file path to `juce_add_binary_data(PoserData ...)` in `CMakeLists.txt`
2. Register in `PluginEditor.cpp` `getResource()` table
3. BinaryData naming: hyphens removed, dots become underscores (`my-file.js` -> `myfile_js`)

## Rules

- Don't run build/test commands -- tell me to run them
- Don't increment or commit changes to `VERSION`
