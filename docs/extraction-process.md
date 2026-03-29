# Poser — Data Extraction & Curve Generation

## Overview

Poser's EQ curves come from published frequency response data — manufacturer spec sheets,
lab measurements (Audio Test Kitchen), and digitized charts (RecordingHacks). Cab/speaker
filter parameters are derived from impulse response analysis.

All curve data lives in `data/`. The build step compiles everything into `src/CurveData.h`.

## Frequency Response Curves

### Adding a mic from Audio Test Kitchen (CSV)

1. Place the CSV in `data/curves/atk/` with format `frequency,dB` (one pair per line)
2. Add the entry in `tools/curves/registry.py` (`MICS` dict)
3. Run the build:
```bash
python3 tools/curves/manage.py build
```

### Adding a mic by digitizing a frequency response chart

This works with any frequency response chart image — RecordingHacks, manufacturer spec sheets, user manuals, etc. The tool extracts colored curves from the image using palette analysis and outputs JSON data points.

1. Get a frequency response chart image (PNG). For RecordingHacks, the tool downloads automatically:
```bash
# RecordingHacks comparison graph (two mics, 1200x401 PNG)
python3 tools/curves/digitize.py 0006 0253              # SM57 vs SM58
python3 tools/curves/digitize.py 0006 0253 --first      # SM57 only
python3 tools/curves/digitize.py 0860 0255              # U87 vs SM7B

# Local image file
python3 tools/curves/digitize.py --image /path/to/chart.png
```

2. Check the comparison plot in `/tmp/poser/` — original image on top, digitized curves on bottom. Verify the curves match visually.

3. Validate against another source if available:
```bash
python3 tools/curves/compare.py
```

4. The digitized JSON is saved to `data/curves/digitized/`. To include it in the plugin, add the mic to `tools/curves/registry.py` and rebuild:
```bash
python3 tools/curves/manage.py build
```

### RecordingHacks mic catalog

The full catalog of 937 mics is at `/tmp/rh_all_mics.txt` (if previously scraped). The autocomplete API can be queried for mic IDs:
- Endpoint: `https://recordinghacks.com/kws.php?m=2&q={query}` (2+ chars, case-sensitive)
- Returns: `Mic Name (Pattern)\tID`
- Graph: `https://recordinghacks.com/graphs2.php/{id}` (single) or `/{id1}-{id2}` (comparison, larger)

### Digitizer calibration notes

The digitizer handles:
- **Paletted PNGs** — works at the palette level, classifying entries as pure curve, watermark-blended curve, or background
- **Watermark occlusion** — uses a two-pass approach: pure colors first, then blend colors to fill gaps in occluded regions
- **Axis calibration** — auto-detects gridlines and computes log-frequency mapping (doesn't assume axis boundaries equal labeled range)
- **Legend masking** — skips the legend region in top-left corner

For non-RecordingHacks images, you may need to adjust the calibration. The tool currently assumes:
- Log-frequency X axis with standard decade gridlines
- Linear dB Y axis (±20dB)
- Colored curves on a light gray background

## Build Step

Curve data lives in `data/`. The build step compiles it into the plugin:

```bash
python3 tools/curves/manage.py build    # → extracted_components.json → CurveData.h
```

`CurveData.h` contains constexpr arrays that the plugin reads at runtime. The build step:
- Interpolates all curves onto a 512-point log-frequency grid (20Hz–20kHz)
- Normalizes each curve at 1kHz = 0dB, then mean-centers
- Generates two curve sets per mic: "full" (raw normalized) and "character" (average subtracted)
- Applies safety taper at frequency extremes (cosine fade below 30Hz, above 16kHz)

## File Reference

| Location | Description |
|----------|-------------|
| `data/curves/atk/*.csv` | Audio Test Kitchen measured responses |
| `data/curves/digitized/*.json` | Curves digitized from chart images |
| `data/curves/extracted_components.json` | Compiled curve data (all sources) |
| `src/CurveData.h` | Auto-generated C++ header (don't edit manually) |
| `/tmp/poser/` | Ephemeral images/plots (not committed) |
