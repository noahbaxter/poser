# Backlog

## Up Next

- [ ] `feature` **More cabs** — expand beyond 4 cab configurations. Source additional IR data for cab/speaker filter parameters.
- [ ] `feature` **Pedal/gear tone curves** — HM-2, Neve preamp, API console. Famous tonal signatures from non-mic gear. Need to figure out source data (manufacturer specs? community measurements?).
- [ ] `design` **Variant labels + switch UI** — multi-curve mics (C414 patterns, SM7B bass rolloff, RE20 proximity, e906 switch positions) currently just cycle numbered variants with no context. Need: descriptive labels per variant explaining what it is (e.g. "Cardioid", "Fig-8", "Bass Rolloff On"), a toggle/dip-switch UI element per mic, and thoughtful default ordering (most common variant first). Related: review which mics have variants and whether the variant groupings make sense.

## Inbox

- [ ] `feature` **Zero/low-latency mode** — fit the magnitude curve to a minimum-phase FIR or IIR biquad filter bank instead of FFT overlap-add. True zero-latency for tracking use. FFT mode stays as the "quality" option.
- [ ] `idea` **Per-component-type curve scaling** — cab/speaker/position curves feel weaker than mic curves. May need normalization or scaling pass in compile.py to balance perceived intensity across component types.
- [ ] `chore` **Manufacturer datasheet digitizer** — build proper tool to extract frequency response curves from the 24 manufacturer PDF/PNG datasheets in `data/datasheets/`. Different formats: some in dBV (absolute, need normalization to relative), some in relative dB. Different axis scales, colors, grid densities. RecordingHacks data is within ~1dB of manufacturer specs for most mics but digitization from 476x159px PNGs is inherently lossy. Having a pipeline from higher-resolution manufacturer charts would improve accuracy, especially for mics without ATK lab data (currently only SM57, SM58, SM7B, C414, U87 have ATK ground truth).
- [ ] `chore` **High/low rolloff detection in curve pipeline** — algorithmically detect where each curve's natural rolloff begins during compile, rather than relying on fixed taper points. Would improve character extraction accuracy.
- [ ] `feature` **Curve mode toggle in UI** — boost-only / cut-only / both. Parameter exists in backend (curve_mode), zeroes negative or positive dB values. Niche but could be useful for surgical work. Needs a button/toggle in the UI.
- [ ] `idea` **Speaker size parameter** — shift the LPF point based on theoretical speaker diameter (10"/12"/15"). Physical model: bigger cone = lower rolloff.
- [ ] `design` **Runtime safety taper instead of baked-in** — currently the cosine taper (<30Hz, >16kHz) is applied at compile time, which throws away real measured data at the extremes (some mics have good data down to 20Hz). Move taper to runtime, scaled with blend amount: no taper at 100%, increasing taper past 100% to prevent boosting garbage at extremes with high scale values. Compile should preserve the full measured range.
- [ ] `design` **Fixed reference curve for character mode** — character extraction currently subtracts the average of the current mic roster, which means adding/removing a mic shifts every other mic's character. Replace with a fixed reference shape (e.g. "generic cardioid rolloff" or a fixed broadband tilt) that's stable regardless of roster changes. The average-subtraction approach also makes swap mode identical in both modes since the average cancels out in subtraction.
- [ ] `idea` **Per-curve energy normalization** — currently each mic curve has different RMS energy (e602: 1.69, D12: 1.02). Switching between mics changes volume, not just shape. Could pre-normalize each curve to mag_RMS=1.0 at compile time so the blend knob only changes shape. Runtime CMP already does this on the combined output, but per-curve would make A/B comparison between mics more fair. Note: doesn't affect swap mode (differential curve is already near-unity).

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
- [x] Full mic curve mode — raw frequency response relative to flat, not just character differences
- [x] Swap mic selector — subtract a source mic's curve for re-mic'ing cab IRs
- [x] Hover tooltips on toggle buttons (FLT, CMP, FULL)
- [x] Curve data validated against manufacturer datasheets (within ~1dB for SM57, MD421)
- [x] Gain compensation audited — confirmed correct: uniform dB shift, shape-preserving, fully off when toggled

## Known Issues

- Latency is ~21ms (1024 samples at 48kHz) — acceptable for mixing, not tracking
- Cab curves are relative differences only (absolute rolloff extracted separately as LPF)
- Curve mode (boost/cut only) parameter exists but no UI yet
- Swap mode is magnitude-only — can't undo phase/time-domain characteristics of cab IRs
- Character mode can produce larger curves than full mode for some mics (when mic is opposite to average)
- RecordingHacks digitization limited by source image resolution (476x159px)

### Datasheet vs RH/ATK curve discrepancies

Investigated 2026-03-29. Some mics show significant differences between datasheet
(guide-traced) and RH/ATK curves. Summary of findings:

**M88** — Guide traced 3 proximity curves (2cm/10cm/1m) but curve 0 is the 2cm
(+13dB bass boost), while RH curve 0 is the 1m far-field. Comparing the wrong
curves against each other. Even matching the right pairs, avg error is ~1.6dB
with ~9.5dB max at extremes — unclear if this is acceptable or indicates a
deeper calibration issue. Guide freq_range [20, 30000] was tested vs [20, 20000]
— 30kHz actually matches better despite axis labels ending at 20k.

**MD421** — Guide freq_range [20, 30000] confirmed correct (0.23dB avg error vs RH
with current config, 3.23dB if changed to [20, 20000]). Multiple bass control
curves on datasheet may cause confusion about which is primary. Not a config bug.

**SM81** — Genuine source disagreement. Datasheet flat curve is ±1.5dB (correct —
SM81 is one of the flattest condensers made). RH shows ±9dB with a +7.4dB
presence peak at 5kHz — completely different measurement. No dB rescaling fix
helps. Guide plot_bounds [216, 41, 2362, 997] and db_range [20, -20] differ from
registry [1051, 41, 2036, 998] / [10, -10] but the guide values appear to be
the user-corrected versions.

**E604** — Sennheiser absolute dBV scale (-40 to -90), normalizes correctly. Two
curves (1m solid, 5cm dashed). Shape genuinely differs from RH — different
measurement conditions. Not a config bug.

**C414** — Three sources (ATK + DS + RH) all show a very flat mic but disagree on
subtle details (presence peak location, HF rolloff). Datasheet ±2dB, ATK ±2dB,
RH ±5dB. Mostly legitimate inter-source variation.

**D4** — Three sources with somewhat different presence peak structure in 1-6kHz.
Not a config bug, just source disagreement.

**SM7B** — High-frequency "teeth" in the guide trace. SM7B is color black so
digitize_guided uses the guide trace directly (no pixel refinement). Artifacts
are from the hand-tracing itself — would need careful retrace above 8kHz.
