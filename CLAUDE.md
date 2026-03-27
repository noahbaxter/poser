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
  curves/
    sources/                 # Cached source PNGs from RecordingHacks (committed)
    masks/                   # Red pixel masks for digitization (committed, hand-editable)
    atk/                     # Audio Test Kitchen measured responses (CSV)
    digitized/               # Curves extracted from masks (JSON, generated)
    extracted_components.json # Compiled curve data (generated)
  ir/
    ir_inventory.json        # IR collection index (generated)
    v30_cab_comparison.json  # Cab analysis results (generated)
```

## Adding a Mic

### Quick version

```bash
# 1. Add mic to MICS in tools/curves/registry.py
# 2. Download source image and export mask
python3 tools/curves/manage.py prepare
# 3. If mask has multiple curves (proximity variants, switch positions):
#    - Open data/curves/masks/{slug}.png in an image editor
#    - Duplicate it — erase unwanted lines in each copy
#    - Save as {slug}_1.png, {slug}_2.png, etc.
# 4. Build everything (digitize → compile → generate header)
python3 tools/curves/manage.py build
# 5. Rebuild plugin and listen
```

### Details

**Registry** (`tools/curves/registry.py`) is the single source of truth for all
mic definitions. Each entry maps a slug to a display name, RecordingHacks ID,
and optional ATK CSV. Edit this one file to add or remove mics.

**Source images** come from RecordingHacks single-mic graphs (476x159 RGBA PNGs
with red curves). `prepare` downloads them to `data/curves/sources/{slug}.png`
and exports the red pixels as masks to `data/curves/masks/{slug}.png`. Source
images are cached — they won't re-download if they already exist.

**Masks** are white PNGs with red curve pixels only (no grid, no labels). For
mics with a single response curve, the base mask works as-is. For mics with
multiple curves (e.g. proximity effect variants at different distances), make
copies named `{slug}_1.png`, `{slug}_2.png` etc, and erase the unwanted lines
in each. When `build` sees `_N` variants, it digitizes each as a separate curve.

**ATK mics** (SM57, SM58, SM7B, C414, U87) use lab-measured CSVs as ground truth
and take priority over digitized data. To validate digitized curves against ATK:
`python3 tools/curves/validate.py`

## Adding Web Assets

1. Add file path to `juce_add_binary_data(PoserData ...)` in `CMakeLists.txt`
2. Register in `PluginEditor.cpp` `getResource()` table
3. BinaryData naming: hyphens removed, dots become underscores (`my-file.js` -> `myfile_js`)

## Rules

- Don't run build/test commands -- tell me to run them
- Don't increment or commit changes to `VERSION`
