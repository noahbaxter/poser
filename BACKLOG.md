# Backlog

## Phase 0 — Validation (COMPLETE)

- [x] Build IR inventory and decomposition pipeline
- [x] Build 4-layer component extraction
- [x] Validate methodology: IR-extracted mic components match known mic characteristics
- [x] **Decision gate: MODULAR** — all four layers (cab, speaker, mic, position) extract as coherent, distinct EQ shapes

### Key findings
- All four variables extract as coherent shapes from IR data
- Mic curves from manufacturer measurements are dramatically better than IR-extracted residuals (15-22dB vs 1-2dB of character)
- Cab/speaker/position extraction from IRs works well for the "flavor" use case
- Position has the cleanest gradient (bright center ↔ dark edge)

## Phase 1 — Core DSP & Prototype (IN PROGRESS)

### Done
- [x] FFT-based magnitude EQ using AudioFFT (cross-platform, handles scaling correctly)
- [x] Sqrt-Hann WOLA with 50% overlap — verified perfect reconstruction via impulse test
- [x] 4 component selectors (mic, cab, speaker, position) with per-component blend 0-100%
- [x] Master push knob (-500% to +500%) scales entire composite curve
- [x] Output trim with smoothing
- [x] Auto-gain compensation (average magnitude → unity)
- [x] Curve low/high cut (fade EQ curve to 0dB outside freq range, prevents bass buildup)
- [x] Boost-only / cut-only / both mode (parameter exists, not yet in UI)
- [x] All parameters bridged to WebView UI via JUCE relay system
- [x] Knob component (`web/components/knob.js`) — reads initial state from C++ backend synchronously, listens for changes, no feedback loops
- [x] Shift+click to disable individual components
- [x] State save/recall via APVTS
- [x] 15 DSP integration tests passing (passthrough, spectral, kick drum, preset switching)
- [x] pluginval compliance passing
- [x] Real mic curves from Audio Test Kitchen (Harman Labs): SM57, SM58, SM7B, U87, C414

### In progress / needs work
- [ ] Integrate real mic curves properly — currently normalized but need to verify they sound right at natural magnitude vs the IR-extracted cab/speaker/position curves
- [ ] Get more mic data: MD421, R-121, RE20, D112, M88, e906 not in ATK database
- [ ] RecordingHacks has 800 mic graphs as PNGs — could automate curve extraction via image processing
- [ ] Curve mode UI (boost-only/cut-only toggle) — parameter exists but no UI control yet

## Phase 2 — More Mic Curves

### Available sources
- **Audio Test Kitchen** — 6 mics downloaded (SM57, SM58, SM7B, U87, C414). CSV data from Harman Labs measurements. Best quality but limited to condensers mostly.
- **RecordingHacks** — 800 graphs for 600 mics, all retraced to common scale. PNG images at `/graphs2.php/{ID}`. Could automate extraction.
- **Manufacturer PDFs** — Shure, Sennheiser, AKG, Neumann, Royer publish spec sheets. Manual WebPlotDigitizer process (~5 min each).

### Target mics still needed
- [ ] Sennheiser MD421 (mid scoop, the "broadcast dynamic")
- [ ] Royer R-121 (ribbon rolloff, guitar cab favorite)
- [ ] Electro-Voice RE20 (flat broadcast sound)
- [ ] AKG D112 (kick drum mic, massive low-end hump)
- [ ] Beyerdynamic M88 (tight, controlled)
- [ ] Sennheiser e906 (guitar cab flat-profile)
- [ ] Shure Beta 52A (kick drum, tighter than D112)
- [ ] Neumann KM184 (small diaphragm overhead)
- [ ] AKG C451 (classic overhead)
- [ ] Coles 4038 (BBC ribbon)
- [ ] AEA R84 (classic ribbon warmth)

## Phase 3 — Expand Cab/Speaker/Position Data

- [ ] Expand extraction to additional IR collections
- [ ] More cab types: open-back 1x12, 2x12, different 4x12 brands
- [ ] More speaker types: Greenback, Blue, Jensen, Eminence
- [ ] Determine if cab/speaker curves need normalization adjustment (currently ±6dB peak)

## Phase 4 — UI Polish

- [ ] Curve mode toggle (boost-only / cut-only / both) in UI
- [ ] Visual EQ curve display showing the composite response
- [ ] Better selector UX for mics (icons/images?)
- [ ] Preset system (save/recall combinations of all 4 selections + blend values)
- [ ] Fix: window size for different display scales

## Phase 5 — Production

- [ ] Proper overlap-add (current simple FIFO has ~21ms latency, acceptable but could improve)
- [ ] Windows build verification
- [ ] Remove debug white noise generator from standalone
- [ ] Update old integration tests (gain_db tests removed, need new regression baselines)
- [ ] C++ unit tests for the FFT processing
- [ ] Performance profiling
- [ ] Installer builds (macOS pkg, Windows Inno Setup)

## Ideas / Future

- Tilt/focus control (shifts curve center of gravity up/down in frequency)
- Multi-curve blending — dual slot with crossfade ("40% SM7B + 60% RE20")
- User-importable curves / community presets
- Advanced mode: expose underlying EQ curve visualization (educational)
- Expansion preset packs
- Automated RecordingHacks graph extraction for 600+ mics

## Known Issues

- Latency is ~21ms (1024 samples at 48kHz) — acceptable for mixing, not for tracking
- Some curves (EDGE, certain speakers) cause bass buildup at high push — use low cut knob
- Curve mode (boost/cut only) parameter exists but no UI yet
- Old test_integration.py tests were removed (referenced nonexistent gain_db param)
