# Backlog

## Up Next

- [ ] `feature` **More cabs** — expand beyond 4 cab configurations. Source additional IR data for cab/speaker filter parameters.
- [ ] `feature` **Pedal/gear tone curves** — HM-2, Neve preamp, API console. Famous tonal signatures from non-mic gear. Need to figure out source data (manufacturer specs? community measurements?).
- [ ] `design` **Variant labels + switch UI** — multi-curve mics (C414 patterns, SM7B bass rolloff, RE20 proximity, e906 switch positions) currently just cycle numbered variants with no context. Need: descriptive labels per variant explaining what it is (e.g. "Cardioid", "Fig-8", "Bass Rolloff On"), a toggle/dip-switch UI element per mic, and thoughtful default ordering (most common variant first). Related: review which mics have variants and whether the variant groupings make sense.

## Inbox

- [ ] `feature` **Zero/low-latency mode** — fit the magnitude curve to a minimum-phase FIR or IIR biquad filter bank instead of FFT overlap-add. True zero-latency for tracking use. FFT mode stays as the "quality" option.
- [ ] `idea` **Per-component-type curve scaling** — cab/speaker/position curves feel weaker than mic curves. May need normalization or scaling pass in compile.py to balance perceived intensity across component types.
- [ ] `chore` **Manufacturer datasheet digitizer** — proper tool to extract frequency response curves from manufacturer PDFs/PNGs with varying formats, axis scales, and colors. Replace hand-traced approximations with accurate pixel-level extraction.
- [ ] `chore` **High/low rolloff detection in curve pipeline** — algorithmically detect where each curve's natural rolloff begins during compile, rather than relying on fixed taper points. Would improve character extraction accuracy.
- [ ] `feature` **Curve mode toggle in UI** — boost-only / cut-only / both. Parameter exists in backend (curve_mode), zeroes negative or positive dB values. Niche but could be useful for surgical work. Needs a button/toggle in the UI.
- [ ] `idea` **Speaker size parameter** — shift the LPF point based on theoretical speaker diameter (10"/12"/15"). Physical model: bigger cone = lower rolloff.

## Icebox

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

- [ ] Tilt/focus control (shifts curve center of gravity up/down in frequency)
- [ ] Multi-curve blending — dual slot with crossfade ("40% SM7B + 60% RE20")
- [ ] User-importable curves / community presets
- [ ] Expansion preset packs
- [ ] Preset system (save/recall combinations)
- [ ] Performance profiling

## Done

- [x] UI: 560×560 window, MIC/CAB tabs, blend panel (4 rows with toggles + knobs), scale knob, bottom controls (LO, TRIM, HI, FLT, CMP)
- [x] EQ curve viewer: pop-out with live spectrum + curve overlay, auto-norm, scale toggle
- [x] Variant stacks: 27 mic entries with variant cycling (scroll on label), badge indicator
- [x] Mic variant/switch UI: multi-curve mics cycle variants (C414 4-way, e906 3-way, etc.)
- [x] Position selector: 13 positions (0-10 + EDGE + FRED), drag slider, scroll wheel
- [x] 5 mic groups (Kick/Drum/Vox/Guit/Inst), multi-group membership, group bar with scroll
- [x] 27 mics / 46 curves from ATK + RecordingHacks digitization pipeline
- [x] CI/CD: 3-platform build (macOS/Windows/Linux), tests, signed+notarized macOS .pkg, Windows Inno Setup .exe, Linux .zip, GitHub Releases
- [x] Per-cab HPF + per-speaker LPF filters (measured from IR data)
- [x] Gain comp toggle (on/off)
- [x] Flat cab/speaker use average filter values (filter always filters when ON)
- [x] DSP reference doc (docs/dsp.md)
- [x] Backend-driven UI, mic groups
- [x] Cab+Speaker grouping in DSP (per-cab HPF × per-speaker LPF)
- [x] Mask-based digitization with hand-editing for multi-curve mics
- [x] Character extraction (subtract average mic rolloff, safety taper)
- [x] Runtime RMS gain compensation
- [x] Cab LPF parameter (average of 18 real cab IRs)
- [x] Unified manage.py entry point with registry.py
- [x] FFT overlap-add DSP (sqrt-Hann WOLA, 50% overlap)
- [x] 4 component selectors with per-component blend
- [x] Scale knob (-500% to +500%)
- [x] Curve low/high cut, output trim
- [x] WebView UI with knob components
- [x] State save/recall, pluginval compliance
- [x] IR decomposition pipeline (cab/speaker/mic/position)

## Known Issues

- Latency is ~21ms (1024 samples at 48kHz) — acceptable for mixing, not tracking
- Cab curves are relative differences only (absolute rolloff extracted separately as LPF)
- Curve mode (boost/cut only) parameter exists but no UI yet
