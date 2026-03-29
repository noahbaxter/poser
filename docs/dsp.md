# DSP Reference

## Signal Model

A guitar cabinet IR captures four main physical layers of coloration:

    IR(f) = Cab(f) * Speaker(f) * Mic(f) * Position(f)

In dB, this is additive:

    IR_dB(f) = Cab_dB(f) + Speaker_dB(f) + Mic_dB(f) + Position_dB(f)

The IR decomposition pipeline (`tools/ir/extract_components.py`) isolates each by
averaging across the other dimensions. For each component value, the "character" is
what makes it different from the average of all values in that dimension.

## Data Sources

| Component | Source | Count | Full Range | Character Range |
|-----------|--------|-------|------------|-----------------|
| Mic | Published frequency response measurements | 27 (46 curves) | 4-23 dB ptp | 5-10 dB ptp |
| Cab | IR decomposition | 4 | +/-0.5-2 dB | — |
| Speaker | IR decomposition | 8 | +/-1-3 dB | — |
| Position | IR decomposition | 13 | +/-2-5 dB | — |

Mic curves come from two sources: lab-measured CSVs from Audio Test Kitchen (SM57,
SM58, SM7B, C414, U87) and digitized frequency response charts from RecordingHacks.
ATK data takes priority when both exist. Manufacturer datasheets are stored in
`data/datasheets/` for visual cross-reference (24 mics).

Cab, speaker, and position curves come from decomposing a multi-variable IR
collection across many cab/speaker/mic/position combos. These use character
extraction only (no full mode) since they're already relative measurements.

## Mic Curve Modes

Mic curves are stored in two forms, selectable at runtime via the FULL toggle:

### Full Mode (default)

The mic's actual frequency response normalized at 1kHz = 0dB, mean-centered, with
safety taper at the extremes. This is the raw shape — includes natural bass rolloff,
presence peaks, everything. A SM57 in full mode has ~23dB peak-to-peak swing.

### Character Mode

Subtracts the average of all mic curves from each individual curve:

    character(f) = raw(f) - mean_of_all(f)

This removes the shared rolloff that all mics have, leaving only the tonal signature:
what makes each mic different from "generic mic." More subtle (~9dB peak-to-peak for
SM57). Note: character extraction can amplify differences for mics that are opposite
to the average — e.g. a kick mic with less presence than average gets an exaggerated
presence cut after subtraction.

### Safety Taper

Both modes apply a cosine fade below 30 Hz and above 16 kHz to prevent artifacts
from unreliable data at the frequency edges.

## Swap Mode

When the source signal already went through a known microphone (e.g. a cab IR captured
with a SM57), the swap selector subtracts that mic's curve before applying the target:

    totalDb = target[bin] * blend - swap[bin]

The swap mic is always subtracted at full -100% strength regardless of the blend knob
position. The blend knob only controls how much of the target mic gets added. This is
intentional: you always want to fully undo the source mic, then partially or fully
apply the new one.

Note: in swap mode, Full vs Character mode produces identical results because the
average mic curve cancels out in the subtraction: `(A - avg) - (B - avg) = A - B`.

### Limitations

Swap mode operates on magnitude only. A cab IR contains the mic's full response
(magnitude + phase + proximity + time-domain behavior). Subtracting the magnitude
curve gets you the frequency difference but can't undo the phase characteristics
baked into the IR. This is the biggest component but not the whole picture.

## Cab/Speaker Filter

Separate from the character curves, the cab and speaker each contribute a physical
rolloff that shapes the overall bandwidth:

- **Cab (box)** -> HPF: low-end rolloff from box resonance, porting, back panel
- **Speaker (cone)** -> LPF: high-end rolloff from cone mass, material, diameter

These are modeled as smooth rolloff curves based on measured parameters:

    HPF: slope_dB_oct * log2(f / f_3dB)   for f < f_3dB, else 0 dB
    LPF: -12 * log2(f / f_3dB)            for f > f_3dB, else 0 dB

### Per-Cab HPF (measured)

| Cab | -3 dB | Slope |
|-----|-------|-------|
| 412 DZL | 78 Hz | 24 dB/oct |
| 412 MAR | 93 Hz | 19 dB/oct |
| 412 MES | 98 Hz | 16 dB/oct |
| 412 ORN | 94 Hz | 12 dB/oct |

### Per-Speaker LPF (measured)

| Speaker | -3 dB | Character |
|---------|-------|-----------|
| 12K | 4366 Hz | Darkest |
| G80 | 4435 Hz | |
| T75 | 4406 Hz | |
| V30 | 4920 Hz | |
| H30 | 5040 Hz | |
| GOV | 5149 Hz | |
| EDVH | 5380 Hz | |
| M25 | 5602 Hz | Brightest |

All speakers are 12 dB/oct. The combined filter is a bandpass: `HPF(cab) * LPF(speaker)`.

The filter is toggleable ("CAB FILTER" in the UI) and applied after gain compensation
so it doesn't affect the RMS normalization of the character curves. "Flat" options
(index 0) for both cab and speaker produce unity gain (no rolloff).

## Processing Chain

```
Input
  |
  v
[FFT: 1024-point, sqrt-Hann window]
  |
  v
[Select mic curve set: Full (kMicsFull) or Character (kMics)]
  |
  v
[Combine curves in dB domain]
  totalDb = mic[target] * micBlend - mic[swap]    (swap fixed at 100%, omitted if off)
          + cab * cabBlend + speaker * speakerBlend + position * positionBlend
  totalDb *= masterPush
  |
  v
[Curve mode filter]
  mode 0: pass all
  mode 1: boost only (clip negative dB to 0)
  mode 2: cut only (clip positive dB to 0)
  |
  v
[Low/high cut: soft fade at user-set frequencies]
  |
  v
[Convert to linear magnitude: 10^(dB/20)]
  |
  v
[RMS gain compensation (if enabled): normalize to unity RMS]
  comp = 1 / sqrt(mean(magnitude^2))
  |
  v
[Cab/speaker filter (if enabled): magnitude *= cabHPF * speakerLPF]
  |
  v
[IFFT + overlap-add synthesis]
  |
  v
[Output trim (smoothed, per-sample)]
  |
  v
Output
```

## Gain Compensation

Toggleable ("GAIN COMP" in the UI, default ON). When enabled, RMS power of the
combined magnitude response is measured and normalized to unity:

    compensation = 1.0 / sqrt(mean(magnitudeResponse^2))

This is mathematically equivalent to running white noise through the EQ and measuring
the output RMS. It prevents the combined curve from being louder or quieter than bypass,
regardless of which components are selected or how the blend/scale knobs are set.

When OFF, the volume change from the EQ shape is preserved — boosts make things
louder, cuts make things quieter. This is useful when the gain shift is part of the
intended character (e.g., a bright mic adding energy to the top end).

The compensation is applied BEFORE the cab/speaker filter so that the filter's
intentional rolloff is preserved (you hear the bandwidth narrowing).

## FFT Processing

- **FFT size:** 1024 samples
- **Hop size:** 512 samples (50% overlap)
- **Window:** sqrt-Hann (analysis and synthesis)
- **Reconstruction:** analysis * synthesis = Hann window, perfect reconstruction at 50% overlap
- **Latency:** 1024 samples (~21 ms at 48 kHz)
- **Frequency bins:** 513 complex values mapped to 512 log-spaced CurveData bins via nearest-neighbor
- **Processing:** magnitude-only (no phase modification)
