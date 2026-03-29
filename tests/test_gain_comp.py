#!/usr/bin/env python3
"""Test gain compensation by simulating the exact DSP chain.

Generates white noise, processes it through the same FFT overlap-add
pipeline as the plugin (matching EqProcessor.h), and measures the
output RMS relative to input RMS.

Perfect compensation = 0dB difference at all scale values.
"""

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent

# Match EqProcessor.h exactly
FFT_SIZE = 1024
HOP_SIZE = FFT_SIZE // 2
COMPLEX_SIZE = FFT_SIZE // 2 + 1
SAMPLE_RATE = 48000.0

# Deterministic white noise — long enough for stable RMS
np.random.seed(42)
NOISE = np.random.randn(FFT_SIZE * 20).astype(np.float64)
NOISE_RMS = np.sqrt(np.mean(NOISE ** 2))

# Sqrt-Hann window
WINDOW = np.sqrt(np.hanning(FFT_SIZE))


def build_bin_mapping(curve_freqs):
    """Match the plugin's nearest-neighbor bin mapping."""
    curve_freqs = np.array(curve_freqs)
    mapping = []
    for i in range(COMPLEX_SIZE):
        fft_freq = i * SAMPLE_RATE / FFT_SIZE
        best_idx = int(np.argmin(np.abs(curve_freqs - fft_freq)))
        mapping.append(best_idx)
    return mapping


def build_magnitude_response(curve_db, bin_mapping, blend, scale):
    """Build magnitude response matching updateResponse() in EqProcessor.h."""
    mag = np.ones(COMPLEX_SIZE)
    for i in range(COMPLEX_SIZE):
        cb = bin_mapping[i]
        total_db = curve_db[cb] * blend * scale
        mag[i] = 10.0 ** (total_db / 20.0)

    # RMS compensation — same as EqProcessor.h
    sum_sq = np.sum(mag ** 2)
    rms = np.sqrt(sum_sq / COMPLEX_SIZE)
    if rms > 0.001:
        mag *= 1.0 / rms

    return mag


def process_through_eq(noise, mag_response):
    """Process noise through FFT overlap-add, matching EqProcessor exactly."""
    n = len(noise)
    output = np.zeros(n + FFT_SIZE)

    fifo_pos = 0
    out_read = 0
    input_fifo = np.zeros(FFT_SIZE)
    output_accum = np.zeros(FFT_SIZE * 2)
    result = np.zeros(n)

    for s in range(n):
        input_fifo[fifo_pos] = noise[s]

        # Read from output accumulator
        out = output_accum[out_read]
        output_accum[out_read] = 0.0
        result[s] = out

        out_read = (out_read + 1) % (FFT_SIZE * 2)
        fifo_pos += 1

        if fifo_pos >= FFT_SIZE:
            # Process frame
            windowed = input_fifo * WINDOW
            spectrum = np.fft.rfft(windowed)
            spectrum *= mag_response
            out_frame = np.fft.irfft(spectrum, n=FFT_SIZE) * WINDOW

            for i in range(FFT_SIZE):
                idx = (out_read + i) % (FFT_SIZE * 2)
                output_accum[idx] += out_frame[i]

            # Shift FIFO
            input_fifo[:HOP_SIZE] = input_fifo[HOP_SIZE:]
            input_fifo[HOP_SIZE:] = 0.0
            fifo_pos = HOP_SIZE

    return result


def measure_gain(curve_db, bin_mapping, blend, scale):
    """Measure the gain change through the full DSP chain."""
    mag = build_magnitude_response(curve_db, bin_mapping, blend, scale)
    output = process_through_eq(NOISE, mag)

    # Skip the first FFT_SIZE samples (latency/startup)
    valid = output[FFT_SIZE * 2:]
    if len(valid) == 0:
        return 0.0

    out_rms = np.sqrt(np.mean(valid ** 2))
    if out_rms < 1e-10:
        return -100.0

    return 20.0 * np.log10(out_rms / NOISE_RMS)


def test_individual_curves(data, bin_mapping):
    """Test every curve at every scale individually."""
    freqs = data["frequencies_hz"]
    scales = [0.5, 1.0, 2.0, 3.0, 5.0, -1.0, -2.0, -5.0]
    problems = []

    print("=== Individual curve gain compensation ===")
    print("(ideal: 0.0dB everywhere)\n")

    for comp_type in ("mic", "cab", "speaker", "position"):
        if comp_type not in data["components"]:
            continue

        items = data["components"][comp_type]
        print(f"--- {comp_type.upper()} (blend=1.0) ---")
        header = f"{'Name':<14}"
        for s in scales:
            header += f"  {s:+.0f}x"
        print(header)
        print("-" * len(header))

        for name in sorted(items.keys()):
            curve = np.array(items[name]["magnitude_db"])
            row = f"{name:<14}"
            for s in scales:
                gain_db = measure_gain(curve, bin_mapping, 1.0, s)
                row += f"  {gain_db:+5.1f}"
                if abs(gain_db) > 1.5:
                    problems.append(("individual", f"{comp_type}/{name}", s, gain_db))
            print(row)

    return problems


def test_flat_passthrough(bin_mapping, num_bins):
    """All blends at 0 or scale at 0 should be unity gain."""
    print("\n=== Flat passthrough ===")
    flat = np.zeros(num_bins)
    problems = []

    for s in [0.0, 1.0, 5.0, -5.0]:
        gain_db = measure_gain(flat, bin_mapping, 1.0, s)
        status = "OK" if abs(gain_db) < 0.01 else "FAIL"
        print(f"  Flat curve at {s:+.0f}x: {gain_db:+.3f}dB  [{status}]")
        if abs(gain_db) > 0.01:
            problems.append(("passthrough", "flat", s, gain_db))

    return problems


def test_symmetry(data, bin_mapping):
    """Positive and negative scale should produce the same RMS."""
    print("\n=== Symmetry (+N vs -N should match) ===")
    problems = []

    for comp_type in ("mic", "cab"):
        if comp_type not in data["components"]:
            continue
        items = data["components"][comp_type]
        for name in sorted(items.keys()):
            curve = np.array(items[name]["magnitude_db"])
            for s in [1.0, 2.0, 5.0]:
                pos = measure_gain(curve, bin_mapping, 1.0, s)
                neg = measure_gain(curve, bin_mapping, 1.0, -s)
                diff = abs(pos - neg)
                if diff > 1.0:
                    print(f"  {comp_type}/{name} at ±{s:.0f}x: +{pos:+.1f} / -{neg:+.1f} (Δ{diff:.1f}dB)")
                    problems.append(("symmetry", f"{comp_type}/{name}", s, diff))

    if not problems:
        print("  All within ±1dB — symmetric")

    return problems


def test_combinations(data, bin_mapping):
    """Test a few realistic multi-curve combos."""
    print("\n=== Combinations ===")
    problems = []

    combos = [
        ("SM57 + DZL + V30 + 05", {"mic": "SM57", "cab": "412 DZL", "speaker": "V30", "position": "05"}),
        ("U87 + ORN + G80 + 00", {"mic": "U87", "cab": "412 ORN", "speaker": "G80", "position": "00"}),
        ("SM58 + MAR + EDVH + EDGE", {"mic": "SM58", "cab": "412 MAR", "speaker": "EDVH", "position": "EDGE"}),
    ]

    type_keys = {"mic": "mic", "cab": "cab", "speaker": "speaker", "position": "position"}

    for label, selection in combos:
        for scale in [1.0, 3.0, 5.0, -1.0, -5.0]:
            # Build combined magnitude response
            mag = np.ones(COMPLEX_SIZE)
            for comp_type, name in selection.items():
                curve = np.array(data["components"][comp_type][name]["magnitude_db"])
                for i in range(COMPLEX_SIZE):
                    cb = bin_mapping[i]
                    total_db = curve[cb] * 1.0 * scale  # blend=1.0
                    mag[i] *= 10.0 ** (total_db / 20.0)

            # No wait — the plugin sums dB, not multiplies linear. Let me match exactly.
            mag = np.ones(COMPLEX_SIZE)
            for i in range(COMPLEX_SIZE):
                cb = bin_mapping[i]
                total_db = 0.0
                for comp_type, name in selection.items():
                    curve = np.array(data["components"][comp_type][name]["magnitude_db"])
                    total_db += curve[cb] * 1.0  # blend=1.0
                total_db *= scale
                mag[i] = 10.0 ** (total_db / 20.0)

            # RMS compensation
            sum_sq = np.sum(mag ** 2)
            rms = np.sqrt(sum_sq / COMPLEX_SIZE)
            if rms > 0.001:
                mag *= 1.0 / rms

            output = process_through_eq(NOISE, mag)
            valid = output[FFT_SIZE * 2:]
            out_rms = np.sqrt(np.mean(valid ** 2))
            gain_db = 20.0 * np.log10(out_rms / NOISE_RMS) if out_rms > 1e-10 else -100.0

            status = "OK" if abs(gain_db) < 1.5 else "WARN" if abs(gain_db) < 3.0 else "FAIL"
            print(f"  {label} @ {scale:+.0f}x: {gain_db:+5.1f}dB  [{status}]")
            if abs(gain_db) > 3.0:
                problems.append(("combo", label, scale, gain_db))

    return problems


def main():
    with open(REPO / "data" / "curves" / "compiled" / "extracted_components.json") as f:
        data = json.load(f)

    freqs = data["frequencies_hz"]
    bin_mapping = build_bin_mapping(freqs)

    all_problems = []
    all_problems += test_individual_curves(data, bin_mapping)
    all_problems += test_flat_passthrough(bin_mapping, len(freqs))
    all_problems += test_symmetry(data, bin_mapping)
    all_problems += test_combinations(data, bin_mapping)

    print(f"\n{'=' * 90}")
    if all_problems:
        print(f"TOTAL: {len(all_problems)} issue(s)")
        for category, name, scale, val in all_problems:
            print(f"  [{category}] {name} at {scale:+.0f}x: {val:+.1f}dB")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
