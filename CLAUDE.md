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
    paths.py                 # Centralized path constants — all tools import from here
    manage.py                # Entry point: prepare / build
    registry.py              # Mic definitions — edit this to add/remove mics
    digitize.py              # Extraction engine (mask export, curve digitization)
    compile.py               # ATK + digitized → extracted_components.json → CurveData.h
    validate.py              # ATK vs digitized agreement check
data/
  curves/
    datasheet/               # Manufacturer datasheets (primary source)
      originals/             #   Source PNGs ({slug}.png)
      masks/                 #   Hand-edited masks for datasheets
      guides/                #   Hand-traced guide JSONs
      curves/                #   Digitized output JSONs
    recordinghacks/          # RecordingHacks images (legacy fallback)
      originals/             #   Downloaded source PNGs
      masks/                 #   Red pixel masks + numbered variants
      curves/                #   Digitized output JSONs
    atk/                     # Audio Test Kitchen lab measurements
      originals/             #   Lab CSV files ({slug}.csv)
      curves/                #   Normalized output JSONs
    compiled/                # Final output
      extracted_components.json  # Compiled curve data (generated)
```

## Adding a Mic

### Quick version (datasheet — preferred)

```bash
# 1. Add mic to MICS in tools/curves/registry.py with datasheet config
# 2. Place manufacturer datasheet PNG in data/curves/datasheet/originals/{slug}.png
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
#    - Open data/curves/recordinghacks/masks/{slug}.png in an image editor
#    - Duplicate it — erase unwanted lines in each copy
#    - Save as {slug}_1.png, {slug}_2.png, etc.
# 4. Build everything
python3 tools/curves/manage.py build
# 5. Rebuild plugin and listen
```

### Details

**Registry** (`tools/curves/registry.py`) is the single source of truth for all
mic definitions. Each entry maps a slug to a display name and curve source config.

**Paths** (`tools/curves/paths.py`) centralizes all directory constants. Every tool
imports from here instead of defining its own paths. Slug-based naming everywhere:
datasheet PNG is `{slug}.png`, ATK CSV is `{slug}.csv`.

**Priority**: ATK CSV > datasheet > hand-edited masks > RH source image.

**Data is organized by source** — each source type has its own self-contained pipeline:
`originals/` (input images/CSVs) → `masks/` (hand-edited) → `curves/` (digitized output).

**Datasheets** are manufacturer frequency response PNGs in `data/curves/datasheet/originals/`.
Each mic's `datasheet` config specifies plot area pixel bounds, axis ranges, and curve color.
For multi-curve images, add a `curves` list with `line_style: "solid"/"dashed"`.

**RH source images** (legacy) are 476x159 RGBA PNGs from RecordingHacks with red
curves. `prepare` downloads them to `recordinghacks/originals/` and exports red pixel
masks to `recordinghacks/masks/`. Only used when no datasheet config exists.

**Masks** are white PNGs with red curve pixels only. For mics with multiple curves,
make copies named `{slug}_1.png`, `{slug}_2.png` etc, erasing unwanted lines in each.
Masks live in the source directory they were derived from (datasheet or recordinghacks).

**ATK mics** (SM57, SM58, SM7B, C414, D4, U87) use lab-measured CSVs as ground truth
in `atk/originals/` and take priority over all other sources. To validate:
`python3 tools/curves/validate.py`

## Adding Web Assets

1. Add file path to `juce_add_binary_data(PoserData ...)` in `CMakeLists.txt`
2. Register in `PluginEditor.cpp` `getResource()` table
3. BinaryData naming: hyphens removed, dots become underscores (`my-file.js` -> `myfile_js`)

## Rules

- Don't run build/test commands -- tell me to run them
- Don't increment or commit changes to `VERSION`
