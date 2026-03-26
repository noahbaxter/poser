# Poser — Component Extraction Process

## Goal

Extract four EQ coloration layers from audio signal chain data:
1. **Cab** — the cabinet's contribution (box resonance, internal reflections)
2. **Speaker** — the speaker's contribution (cone breakup, presence peak, rolloff)
3. **Mic** — the microphone's coloration (frequency response curve)
4. **Position** — mic placement effect (bright center vs dark edge)

Each layer becomes a selectable EQ curve in the plugin with its own blend knob. The user picks one of each and dials in how much flavor they want.

**These are NOT trying to reconstruct an IR.** They're independent tonal colorations that happen to come from the same signal chain.

## Data Sources

### Mic curves (primary source: manufacturer data)
- Digitize from manufacturer spec sheets (Shure, Sennheiser, AKG, Neumann, etc.)
- These are ground truth — controlled on-axis measurements in anechoic conditions
- No extraction needed, just digitization

### Cab, speaker, position curves (primary source: IR analysis)
- Derived from multi-variable impulse response collections
- The IR-extracted mic component serves as cross-validation against manufacturer curves

## Extraction Method

### The math

Every IR captures the full chain: cab × speaker × mic × position. In dB, these are additive. To isolate one variable, average across all others — the other variables cancel out, leaving just the target.

**Grand mean** = average of ALL IRs. This is the "baseline" — what an average cab+speaker+mic+position sounds like.

**Cab component** = (average of all IRs in that cab) - grand_mean
- Averages out speaker, mic, position → what's left is the cab

**Speaker component** = (average of all IRs with that speaker) - grand_mean - cab_component
- Averages out mic, position → subtracts cab → what's left is the speaker

**Mic component** = (average of all IRs with that mic) - grand_mean
- Averages out cab, speaker, position → what's left is the mic's coloration

**Position component** = (average of all IRs at that position) - grand_mean
- Averages out cab, speaker, mic → what's left is the position's effect

### What makes a good component

1. **Coherent shape** — smooth, identifiable features (peaks, dips, slopes), not random noise
2. **Distinct from siblings** — V30 looks different from G80, SM57 looks different from R121
3. **Stable across data** — doesn't change dramatically if you exclude a few IRs
4. **Scales well** — at 5x or 10x blend, it's still a musically useful EQ shape, not spiky garbage

### What we DON'T need

- Perfect recombination (cab + speaker + mic + position ≈ original IR) — nice but not required
- Large magnitude at 1x — small differences become large at high blend
- Phase accuracy — we only extract magnitude, which is correct for this use case

## Decision Points

After running the extraction:

1. **If mic components from IRs roughly match manufacturer curves** → validates the entire methodology. The extraction is working correctly.

2. **If cab components are coherent and distinct** → ship cab selector in the plugin.

3. **If speaker components are coherent and distinct** → ship speaker selector.
   If they're mostly noise → ship whole-chain cab+speaker presets instead.

4. **If position components show a clear bright-to-dark gradient** → ship a position knob (or map it to a tilt control).
   If they're noisy → skip position, it's already captured in the mic averaging.
