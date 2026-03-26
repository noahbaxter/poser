# Backlog

## Phase 0 — Validation (COMPLETE)

- [x] Build IR inventory and decomposition pipeline
- [x] Build 4-layer component extraction
- [x] Validate methodology: IR-extracted mic components match known mic characteristics
- [x] **Decision gate: MODULAR** — all four layers (cab, speaker, mic, position) extract as coherent, distinct EQ shapes

### Key findings
- All four variables contribute ~0.7-1.2 dB pairwise MAE at 1x (scales to 3.5-6 dB at 5x blend)
- Position has the most variation (EDGE vs center = 3.6 dB), maps to a bright↔dark tilt knob
- Mic extraction matches known physics (R121 rolloff, SM57 presence peak, C414 extended)
- Cab components have identifiable features centered around 500-600Hz (cabinet resonance)
- Speaker components are smallest but still coherent shapes with identifiable features
- Mic curves for the plugin will come from manufacturer spec sheets (ground truth), not IR extraction

## Phase 1 — Core DSP

- [ ] Define preset data format (freq/magnitude pairs, JSON or binary)
- [ ] Implement curve-to-filter conversion (parametric EQ fitting — series of bell/shelf bands)
- [ ] Implement blend knob scaling (scale magnitude before converting to coefficients)
- [ ] Implement bipolar operation (negate dB values for negative blend)
- [ ] Implement output trim / gain compensation
- [ ] Wire up APVTS parameters: 4 selectors (mic, speaker, cab, position) + 4 blend knobs + output trim

## Phase 2 — Mic Curves

- [ ] Digitize proof-of-concept curves: SM57, MD421, D112 (most distinctive, best documented)
- [ ] Source and digitize remaining ~15 mic curves from manufacturer spec sheets
- [ ] Build preset loading system
- [ ] Validate curves sound recognizable on real mix material

## Phase 3 — Cab/Speaker/Position Curves

- [ ] Extract final cab/speaker/position curves from IR collection
- [ ] Determine optimal smoothing level for preset curves
- [ ] Expand extraction to additional IR collections for more cab/speaker variety
- [ ] Build preset sets for each component type

## Phase 4 — UI

- [ ] Design 4-selector interface (mic, speaker, cab, position)
- [ ] Per-component blend knobs (bipolar, wide range)
- [ ] Output trim knob
- [ ] WebView implementation

## Phase 5 — Polish & Ship

- [ ] Full preset library with metadata and images
- [ ] Testing (unit, integration, pluginval compliance)
- [ ] Installer builds (macOS, Windows, Linux)

## Ideas / Future

- Tilt/focus control (shifts curve center of gravity up/down in frequency)
- Multi-curve blending — dual slot with crossfade ("40% SM7B + 60% RE20")
- User-importable curves / community presets
- Advanced mode: expose underlying EQ curve visualization
- Expansion preset packs (pricing model TBD)

## Known Issues

(none yet)
