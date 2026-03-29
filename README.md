# Poser

EQ plugin shipping curated frequency response curves of famous microphones and guitar cabinet speakers. Pick a mic or cab, dial a blend knob, and your signal takes on that tonal character.

Not a mic modeler. Not a cab sim. It's a creative mixing tool that applies the known EQ shape of recognizable gear as a tonal direction, at whatever intensity you want.

## How It Works

Poser applies the published frequency response of real microphones and speakers as an EQ curve to your audio. The curves are sourced from manufacturer datasheets and lab measurements (Audio Test Kitchen), digitized, and compiled into the plugin.

- **27 microphones** across 5 groups (Kick, Drum, Vocal, Guitar, Instrument)
- **4 guitar cabinet boxes** with per-cab low-end rolloff (HPF)
- **8 speakers** with per-speaker high-end rolloff (LPF)
- **13 mic positions** (center to edge, plus specialty positions)

The DSP is a 1024-point FFT magnitude EQ with overlap-add synthesis. Magnitude-only processing — no phase modification, no convolution, no IR loading.

## Controls

- **Mic/Cab selector** — ring-style browser with group filtering
- **Blend knob** — -100% to +100%, bipolar (negative inverts the curve)
- **Scale** — 0-500%, multiplies the curve intensity
- **Lo/Hi Cut** — soft frequency limits on the curve (not the audio)
- **FLT** — cab filter toggle (applies per-cab HPF + per-speaker LPF)
- **CMP** — gain compensation (RMS normalization to keep loudness constant)
- **FULL** — full mic response vs character-only mode
- **Swap** — subtract a source mic's curve (for re-mic'ing signals that already went through a known mic, e.g. cab IRs)
- **Trim** — output level adjustment

## Curve Modes

**Full mode** (default): applies the mic's actual frequency response relative to flat. Includes all natural rolloff and presence characteristics. A SM57 at 100% gives you the full SM57 shape: bass rolloff below 200Hz, presence peak at 5-6kHz, the works.

**Character mode**: subtracts the average mic response from each curve, leaving only what makes each mic different from the group. More subtle — highlights the tonal signature without the shared rolloff that all mics have. Useful for gentle flavoring rather than dramatic reshaping.

## Swap Mode

When your source signal already went through a specific microphone (e.g. a guitar cab IR captured with an SM57), you can set the swap selector to that mic. The plugin subtracts the source mic's curve at full strength before applying the target mic, effectively re-mic'ing the signal.

Note: this is magnitude-only — it can't undo the phase and time-domain characteristics baked into an IR. It gets you the frequency difference, which is the biggest component but not the whole picture.

## Building

```bash
./scripts/build.sh              # Release build + install
./scripts/build.sh debug        # Debug build
./scripts/build.sh standalone   # Build and launch standalone app
./scripts/build.sh curves       # Regenerate curve data only
./scripts/clean.sh              # Remove build artifacts
```

Requires CMake, a C++17 compiler, and Python 3 with numpy (for curve tools).

## Testing

```bash
./scripts/test.sh               # All tests
./scripts/test.sh unit          # C++ unit tests
./scripts/test.sh integration   # Python integration tests
./scripts/test.sh compliance    # pluginval compliance
./scripts/test.sh validate      # pluginval at strictness 10
```

## Formats

- **macOS**: VST3, AU
- **Windows**: VST3
- **Linux**: VST3, LV2, CLAP

## Documentation

- [Concept & spec](docs/spec.md)
- [DSP reference](docs/dsp.md)
- [Data extraction process](docs/extraction-process.md)
- [CLAUDE.md](CLAUDE.md) — build instructions, data tools, adding mics
- [BACKLOG.md](BACKLOG.md) — planned work and known issues

## License

MIT
