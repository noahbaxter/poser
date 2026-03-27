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
  curves/
    digitize.py              # Download source images, export/digitize masks
    build.py                 # ATK + digitized → extracted_components.json
    generate_header.py       # extracted_components.json → src/CurveData.h
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
# 1. Add mic to MIC_SLUGS + RH_MIC_NAMES in digitize.py
# 2. Download source image and export mask
python3 tools/curves/digitize.py prepare
# 3. If mask has multiple curves (proximity variants, switch positions):
#    - Open data/curves/masks/{slug}.png in an image editor
#    - Duplicate it — erase unwanted lines in each copy
#    - Save as {slug}_1.png, {slug}_2.png, etc.
# 4. Digitize all masks → JSON
python3 tools/curves/digitize.py build
# 5. Add mic to DIGITIZED_MICS in build.py
# 6. Compile into plugin data
python3 tools/curves/build.py
python3 tools/curves/generate_header.py
# 7. Rebuild plugin and listen
```

### Details

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

**Naming**: everything uses mic slugs (e.g. `sm57`, `beta-52a`, `m88-tg`), not
RecordingHacks numeric IDs. Slugs are defined in `MIC_SLUGS` in `digitize.py`.

## Adding Web Assets

1. Add file path to `juce_add_binary_data(PoserData ...)` in `CMakeLists.txt`
2. Register in `PluginEditor.cpp` `getResource()` table
3. BinaryData naming: hyphens removed, dots become underscores (`my-file.js` -> `myfile_js`)

## Rules

- Don't run build/test commands -- tell me to run them
- Don't increment or commit changes to `VERSION`
