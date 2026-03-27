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

| Component | Source | Count | Typical Range |
|-----------|--------|-------|---------------|
| Mic | Published frequency response measurements | 16 | +/-5-10 dB |
| Cab | IR decomposition | 4 | +/-0.5-2 dB |
| Speaker | IR decomposition | 8 | +/-1-3 dB |
| Position | IR decomposition | 13 | +/-2-5 dB |

Mic curves come from published frequency response data (lab measurements and
manufacturer charts). Cab, speaker, and position curves come from decomposing
a large multi-variable IR collection across many cab/speaker/mic/position combos.

## Character Extraction

Each component's raw frequency response includes shared physics (e.g., all mics
roll off at the extremes). We subtract the average to isolate pure character:

    character(f) = raw(f) - mean_of_all(f)

This removes the shared rolloff and leaves only the tonal signature: presence peaks,
mid scoops, warmth differences. The average is discarded — it's the "generic" shape
common to all items in that dimension.

A safety taper is applied at the extremes (cosine fade below 30 Hz and above 16 kHz)
to prevent artifacts from unreliable data at the frequency edges.

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
[Combine character curves in dB domain]
  totalDb = mic * micBlend + cab * cabBlend + speaker * speakerBlend + position * positionBlend
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
