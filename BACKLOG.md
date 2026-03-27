# Backlog

## Up Next

- [x] `feature` **Backend-driven UI** — component lists come from C++ at init via evaluateJavascript. Done.
- [x] `feature` **Mic categorization** — group buttons (Vocal/Instrument/Kick/Condenser/Ribbon). Done.
- [ ] `feature` **Cab+Speaker grouping** — cab and speaker should be a single UI section. Pick a cab, pick a speaker. The cab HPF + speaker LPF combine as a toggleable bandpass filter. Offer "flat" options for both. Per-cab HPF and per-speaker LPF are already measured. Needs: UI redesign from 4 tabs to 3 (Mic, Cab+Speaker, Position), new combined filter in DSP, "flat cab" and "flat speaker" options.
- [ ] `feature` **Write DSP/decomposition doc** — explain the signal model (IR = cab × speaker × mic × position), what the decomposition extracts, how character extraction works, how gain compensation works. Put in docs/dsp.md. This is getting complex enough to warrant a reference doc.
- [ ] `feature` **Curve viewer** — collapsible panel from bottom of plugin showing composite EQ curve.
- [ ] `feature` **More cabs** — expand beyond 4 cab configurations. Source additional IR data for cab/speaker filter parameters.
- [ ] `idea` **Speaker size parameter** — shift the LPF point based on theoretical speaker diameter (10"/12"/15"). Physical model: bigger cone = lower rolloff.

## Inbox

- [ ] `feature` **Pedal/gear tone curves** — HM-2, Neve preamp, API console. Famous tonal signatures from non-mic gear. Need to figure out source data (manufacturer specs? community measurements?).
- [ ] `chore` **High/low rolloff detection in curve pipeline** — algorithmically detect where each curve's natural rolloff begins during compile, rather than relying on fixed taper points. Would improve character extraction accuracy.
- [ ] `feature` **Curve mode toggle in UI** — boost-only / cut-only / both. Parameter exists in backend, no UI control yet.

- [ ] `feature` **Zero/low-latency mode** — fit the magnitude curve to a minimum-phase FIR or IIR biquad filter bank instead of FFT overlap-add. True zero-latency for tracking use. FFT mode stays as the "quality" option.

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
- [ ] Windows build verification
- [ ] Installer builds (macOS pkg, Windows Inno Setup)
- [ ] Performance profiling
- [ ] C++ unit tests for FFT processing

## Done

- [x] 16 mic curves from ATK + RecordingHacks digitization pipeline
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
