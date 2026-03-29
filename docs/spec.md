# Poser — Concept & Spec

**"Make your sound pretend to be something better"**

## The Idea

A simple EQ plugin that ships with curated frequency response curves of well-known microphones and guitar cabinet speakers. You pick a mic or cab, dial in a blend percentage, and your signal takes on that tonal character. It's not mic modeling — it's not trying to "convert" anything. It applies the known EQ shape of recognizable gear as a creative tonal direction, at whatever intensity you want.

The design philosophy is similar to ultra-focused plugins like the Goodhertz Tone Control or Fractal's sag emulation — a tiny, opinionated tool that does one thing and leans into simplicity as a feature. Those plugins succeed because they remove decisions, not add them.

## The Motivating Use Case

"I recorded drums and I just wish the kick could sound more like a D112 or a Beta 52 and it just doesn't." That's the plugin. The D112's whole identity is a massive low-end hump around 80-100Hz and a clicky presence peak at 4kHz. Apply that shape to your kick track at 60-80% and you'd get meaningfully closer to that sound. Would it be identical to having tracked with that mic? No. Would it get you 70% of the way there in a way that actually matters in a mix? Probably yes. And 70% of the way there with one knob is a genuinely useful tool.

This extends to any source: pushing a vocal toward SM7B warmth, giving a room mic some Royer 121 rolloff character, making a snare more SM57-forward. It also works on completely digital sources — synths, samples, DI tracks, anything. The plugin doesn't know or care what the source is.

## What It Is / What It Isn't

**It IS:**
- A curated library of frequency response curves from famous mics and cabs
- A blend knob that scales how much of that curve gets applied
- A mixing tool that works on any source — mic'd audio, DI, synths, samples, whatever
- Source-agnostic: you do NOT need to specify what mic you recorded with
- Genre-agnostic: works on kicks, vocals, guitars, full buses, anything
- "Opinionated EQ presets with lineage" — the value is curation and naming, not novel DSP

**It ISN'T:**
- A mic modeler (not trying to "turn mic A into mic B")
- A cab sim / IR loader (not trying to replace a guitar cabinet)
- A match EQ (user doesn't supply a reference — the references are built in)
- Doing anything beyond frequency response — no transient shaping, no noise, no polar pattern modeling
- A Sonarworks-style correction tool — those flatten a known input to flat. This goes the other direction: it takes whatever you have and pushes it toward a known tonal destination.

## Why EQ-Only Is the Correct (and Complete) Scope

### For dynamic mics: frequency response IS the sound
The SM57 presence peak around 5-6kHz — that's the sound. The MD421's mid-scoop — that's the sound. When someone says "this sounds like a 57" on a snare, they're mostly identifying that presence peak and the tight low-end rolloff. Apply that shape to something else and you'd get recognizably 57-flavored results.

### For guitar cabs/speakers: frequency response is the entire story
That's literally what impulse responses capture, and people buy and trade thousands of those. A V30 and a Greenback differ primarily in frequency response and everyone can hear it immediately.

### For condensers and ribbons: EQ is the biggest factor but not the only one
Transient behavior and capsule resonance contribute more to the identity of condensers and ribbons than they do for dynamics. A ribbon's transient softness comes from the mass and compliance of the ribbon element. You could approximate it with a transient shaper, but now you're building a different plugin. The frequency response is still the single biggest factor even for these categories, and it's the only factor you can meaningfully model without knowing the source context.

### Why transient/noise/polar modeling was rejected
- Transient shaping without knowing the source material is meaningless — you don't know what mic was used, the distance, or whether there's even a mic in the chain at all. The plugin could be used on a synth bus.
- Proximity effect modeling requires knowing source distance, which you don't have.
- Polar pattern emulation post-recording is meaningless.
- Capsule resonance modeling is physical modeling territory — a whole different discipline.
- Noise/character generation adds nothing useful and should 100% not be in this plugin.
- A "mic category" selector (dynamic/condenser/ribbon) that applies transient differences would just be a transient shaper with mic pictures on it. That's not modeling anything, it's pretending to.
- Every additional modeling dimension dilutes the simplicity that makes the plugin valuable.

## Controls

### Core (the whole plugin)
- **Mode toggle**: Mics / Cabs
- **Preset selector**: Visual browser with pictures/icons of each mic or cab. Should feel like scrolling through a mic locker or a wall of cabs.
- **Blend knob (bipolar)**:
  - 0% = bypass
  - Positive = apply the curve
  - Negative = apply the inverse curve (e.g., MD421 mid-scoop becomes mid-hump at -50%)
  - Range: roughly -200% to +500% (or even 1000% — let people go extreme and discover the character at those settings)
  - Bipolar is free — just flip the sign on all magnitude values. Doubles the usefulness of every preset.
- **Output trim**: Mandatory — aggressive curves at high blend will shift gain. Auto-gain (loudness-matched bypass) ideal for A/B'ing but manual trim knob fine for v1.

### Maybe v1, Maybe v2
- **Tilt/focus control**: Shifts the curve's center of gravity up or down in frequency. Not a full frequency shift — just a broad tilt so you can say "421 character but weighted toward the low end." Cut this if it muddies the simplicity.
- **Multi-curve blending**: Load two curves and blend between them — "40% SM7B + 60% RE20." Powerful but adds UI complexity. Probably v2.

### Explicitly NOT included (settled decisions, don't revisit)
- Source mic selector as a REQUIRED input (you don't need to tell it what you recorded with — this is the key UX difference from Antares Mic Mod). Exception: optional "swap" selector for advanced users who want to subtract a known source mic when re-mic'ing cab IRs.
- Transient shaping of any kind
- Noise/character generator
- Proximity effect modeling
- Polar pattern anything
- Linear phase mode (minimum phase is fine at reasonable blend values — see Technical Notes)
- Mic position visual/control — if you add a "position" knob for cabs, frame it as a tonal shaping control (bright to dark tilt), NOT as a physical mic position model. Do NOT put a visual position indicator showing a mic moving on a speaker, because people will A/B it against actually moving a mic and it'll fail that comparison.

## Preset Library

See [preset-list.md](preset-list.md) for the full list with tonal descriptions.

### Mics — ~18-20 Essential Flavors
Organized by typical use case (how people think, not by mic type):
- **Kick/Bass**: D112, Beta 52A, RE20, e602
- **Snare/Guitar cabs**: SM57, MD421, e906, M88
- **Vocals/General**: SM7B, RE20, SM58
- **Condensers**: U87, C414, KM184, C451
- **Ribbons**: R-121, Coles 4038, AEA R84

### Cabs — ~10-12 Essential Flavors
- **Speakers**: V30, Greenback, Blue, Jensen P12R/C12N, Eminence Texas Heat, Creamback
- **Cab configs**: 4x12 closed (V30s), 4x12 closed (Greenbacks), 2x12 open, 1x12 open, 1x12 closed

Whether speakers and cabs ship as separate selectable components (modular) or as whole-chain presets depends on the decomposition validation.

## Data Sourcing

### Mic Curves
Primary source is manufacturer spec sheets. Shure, Sennheiser, AKG/Harman, Neumann all publish detailed frequency response data. For PDF-only plots, use WebPlotDigitizer. Supplementary sources: recordinghacks.com, Dayton Audio EARS community.

### Cab/Speaker Curves
Derive magnitude response from impulse responses via FFT. Average across positions to get canonical curves. 
## Critical Validation: The Python Prototype

**This is the go/no-go gate before writing any JUCE code. Do this FIRST.**

The decomposition test determines whether the cab section is modular (speaker + cab separately) or whole-chain presets. The core plugin (mic curves + blend knob) doesn't depend on this test at all.

## Technical Notes

### Filter Implementation
Two approaches: (1) Convert magnitude curve to minimum-phase FIR filter via cepstral method, or (2) fit the curve to a high-order parametric EQ (series of bell/shelf bands). The parametric approach is more CPU-efficient and lets you interpolate coefficients smoothly for the blend knob.

### Blend Knob Math
The blend knob scales the magnitude curve before converting to filter coefficients. At 50%, every boost and cut is halved. At 200%, they're doubled. For parametric approach, interpolate filter coefficients directly.

### Minimum Phase Is Fine
It's what every analog EQ does. Nobody will hear phase issues at reasonable blend values (0-150%). At extreme settings (500%+), cumulative phase shift could get smearey — this is expected and acceptable.

### Dry/Wet vs. Blend Knob — DO NOT USE IR CONVOLUTION
When you mix a dry signal with a convolved signal, you're summing the original with a time-smeared, phase-shifted version of itself. At 50% wet you don't get "half the cab character" — you get comb filtering and phase cancellation. The blend knob scales EQ curve magnitude BEFORE applying as a filter. This is correct.

### Preset Data Format
- Each preset: ~100-200 frequency/magnitude pairs, logarithmically spaced from 20Hz to 20kHz
- Stored as JSON, binary, or custom format
- Metadata alongside: name, category, image/icon path, short description
- For bipolar operation: negate dB values

## Competitive Landscape

### Direct competitor
**Antares Mic Mod** (~$99): 100+ mic models. Source→target workflow (MUST specify source mic). Has proximity controls, low cut, polar pattern, tube saturation. Poorly regarded — consensus is "glorified EQ that can't make an SM57 sound like a U87." Legacy UI, neglected. **No blend/intensity control. No guitar cabs.**

### Adjacent (hardware-locked systems)
- **Slate Digital VMS** ($600+ with mic): Requires their ML-1/ML-1A mic. Won't work without it. Recording-time tool.
- **Townsend Labs / UA Sphere** ($1000+): Dual-capsule mic, captures 3D soundfield. Most accurate mic modeling, but requires expensive hardware.

### Guitar cab space (NOT our competition)
Modular cab sim plugins (speaker/cab/mic selectors with IR-based processing). These are full cab replacement tools — different market from what Poser does.

### Our differentiation
1. **No source mic required** — works on anything
2. **Blend knob as core interaction** — exploration and degree, not A-to-B conversion
3. **Both mics AND cabs in one tool**
4. **Modern UX, focused scope** — one knob + selector
5. **Creative mixing tool, not corrective/tracking tool**
6. **Works on non-mic sources** — synths, samples, DI, buses

### Honest assessment
Not inventing a new category. The concept is 20+ years old. But the existing product (Antares Mic Mod) is neglected, poorly regarded, and differently conceived. The hardware systems are a different market. The opportunity is executing this well with modern UX and the right creative framing.

## Ideas Explored and Deliberately Rejected

### "Construct a microphone" — pick dynamic/condenser/ribbon, then specific model
The category modeling (transient shaping, noise character) doesn't work without knowing the source material. Would just be a channel strip with mic pictures on it.

### Modular cab builder with separate speaker + cab + mic + position
Directly competes with established cab sim plugins that have better data, brand partnerships, and years of head start. The positioning difference between "I am your cabinet" (cab sim) and "I flavor your sound toward something" (Poser) is what keeps us out of that competitive space.

### IR loader with dry/wet blend
Dry/wet on convolution causes comb filtering and phase cancellation. 50% wet sounds phasey and broken. Frequency domain interpolation between flat and target IR is theoretically possible but is just EQ with extra steps and more CPU.

## Open Questions

- **Pricing model**: One-time? Subscription for preset packs? Free base + paid expansions?
- **Expandability**: User-importable curves? Community presets? Import format?
- **Advanced mode**: Expose EQ curve visualization? Educational but might make it feel like "just an EQ."
- **Multi-curve blending**: v2 feature — dual slot with crossfade
- **Branding**: Standalone brand (not part of -chotic family)

## Key Technical Decisions (SETTLED)

- No IR convolution with dry/wet
- No source mic selector
- No transient/noise/polar modeling
- Minimum phase only for v1
- Bipolar blend is free value
- Cab curves from FFT magnitude of IRs, not IRs themselves
- Phase information from IRs not worth preserving
- This is a mixing/creative tool, not a cab sim or mic modeler
