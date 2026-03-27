"""Compile mic curves into plugin data.

Reads ATK CSVs + digitized JSONs → extracted_components.json → CurveData.h

Internal module used by manage.py. Not meant to be run directly.
"""

import csv
import json
import re
from pathlib import Path

import numpy as np

from registry import MICS, MIC_GROUPS

REPO = Path(__file__).resolve().parent.parent.parent
ATK_DIR = REPO / "data" / "curves" / "atk"
DIGITIZED_DIR = REPO / "data" / "curves" / "digitized"
COMPONENTS_JSON = REPO / "data" / "curves" / "extracted_components.json"
HEADER_OUTPUT = REPO / "src" / "CurveData.h"

FLOATS_PER_LINE = 12
TARGET_PEAK_DB = 6.0

TYPE_CONFIG = {
    "cab":      ("Cab",      "Cabs"),
    "speaker":  ("Speaker",  "Speakers"),
    "mic":      ("Mic",      "Mics"),
    "position": ("Position", "Positions"),
}


# --- Curve loading ---

def load_atk_csv(path):
    """Returns (freqs, dbs, data_lo_hz, data_hi_hz)."""
    freqs, dbs = [], []
    with open(path) as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                try:
                    freqs.append(float(row[0]))
                    dbs.append(float(row[1]))
                except ValueError:
                    continue
    freqs = np.array(freqs)
    dbs = np.array(dbs)
    return freqs, dbs


def load_digitized(slug, curve_index=0):
    """Returns (freqs, dbs) or (None, None)."""
    path = DIGITIZED_DIR / f"{slug}.json"
    if not path.exists():
        return None, None
    with open(path) as f:
        d = json.load(f)
    try:
        pts = d["curves"]["single"]["curves"][curve_index]["data"]
    except (KeyError, IndexError):
        return None, None
    freqs = np.array([p["hz"] for p in pts])
    dbs = np.array([p["db"] for p in pts])
    mask = freqs <= 20000
    return freqs[mask], dbs[mask]


def interpolate_to_grid(src_freqs, src_dbs, target_freqs):
    log_src = np.log10(np.maximum(src_freqs, 1.0))
    log_tgt = np.log10(np.maximum(target_freqs, 1.0))
    return np.interp(log_tgt, log_src, src_dbs)


def normalize_at_1k(freqs, dbs):
    db_at_1k = np.interp(1000, freqs, dbs)
    return dbs - db_at_1k


def extract_character(curves_dict, target_freqs):
    """Subtract the average mic shape from each curve to isolate character.

    The average captures the shared rolloff that all mics have. What's left
    is pure character: presence peaks, mid scoops, warmth — the stuff that
    makes each mic sound different from "generic mic."
    """
    all_curves = [np.array(info["magnitude_db"]) for info in curves_dict.values()]
    avg_curve = np.mean(all_curves, axis=0)

    result = {}
    for name, info in curves_dict.items():
        curve = np.array(info["magnitude_db"])
        character = curve - avg_curve
        result[name] = character

    return result, avg_curve


# Fixed safety taper at the extremes — cosine fade to 0dB
TAPER_LO_HZ = 30.0    # full taper below this
TAPER_LO_START = 15.0  # 0dB below this (1 octave below TAPER_LO_HZ)
TAPER_HI_HZ = 16000.0  # full taper above this
TAPER_HI_END = 20000.0  # 0dB above this (~0.3 octaves above)


def apply_safety_taper(curve, target_freqs):
    """Gentle fixed taper at the very extremes as a safety net."""
    result = curve.copy()
    for i, f in enumerate(target_freqs):
        if f <= 0:
            result[i] = 0.0
            continue
        if f < TAPER_LO_HZ:
            if f <= TAPER_LO_START:
                result[i] = 0.0
            else:
                t = (np.log2(f) - np.log2(TAPER_LO_START)) / (np.log2(TAPER_LO_HZ) - np.log2(TAPER_LO_START))
                result[i] *= 0.5 * (1.0 - np.cos(np.pi * t))
        if f > TAPER_HI_HZ:
            if f >= TAPER_HI_END:
                result[i] = 0.0
            else:
                t = (np.log2(f) - np.log2(TAPER_HI_HZ)) / (np.log2(TAPER_HI_END) - np.log2(TAPER_HI_HZ))
                result[i] *= 0.5 * (1.0 + np.cos(np.pi * t))
    return result


# --- Build extracted_components.json ---

def build_components():
    """Merge ATK + digitized curves into extracted_components.json."""
    with open(COMPONENTS_JSON) as f:
        data = json.load(f)

    target_freqs = np.array(data["frequencies_hz"])
    print(f"Target grid: {len(target_freqs)} points, "
          f"{target_freqs[0]:.1f}-{target_freqs[-1]:.1f} Hz")

    # First pass: load and interpolate all mics onto the grid
    raw_mics = {}

    for slug in sorted(MICS):
        info = MICS[slug]
        display_name = info["name"]
        atk_csv = info.get("atk_csv")

        if atk_csv:
            csv_path = ATK_DIR / atk_csv
            if not csv_path.exists():
                print(f"  SKIP {display_name}: {csv_path} not found")
                continue
            freqs, dbs = load_atk_csv(csv_path)
            source = "audio_test_kitchen"
            print(f"  {display_name}: {len(freqs)} pts from ATK")
        else:
            freqs, dbs = load_digitized(slug)
            if freqs is None:
                print(f"  SKIP {display_name}: {slug}.json not found")
                continue
            source = "recordinghacks"
            print(f"  {display_name}: {len(freqs)} pts from RH ({slug})")

        dbs = normalize_at_1k(freqs, dbs)
        interp_dbs = interpolate_to_grid(freqs, dbs, target_freqs)
        interp_dbs -= np.mean(interp_dbs)

        raw_mics[display_name] = {
            "magnitude_db": interp_dbs.tolist(),
            "source": source,
        }

    # Second pass: extract character by subtracting average mic shape,
    # then apply safety taper at the extremes
    character_curves, avg_curve = extract_character(raw_mics, target_freqs)
    print(f"\nAverage mic rolloff: {avg_curve[0]:+.1f}dB at {target_freqs[0]:.0f}Hz, "
          f"{avg_curve[-1]:+.1f}dB at {target_freqs[-1]:.0f}Hz")

    new_mics = {}
    for display_name, character in character_curves.items():
        tapered = apply_safety_taper(character, target_freqs)

        new_mics[display_name] = {
            "magnitude_db": tapered.tolist(),
            "source": raw_mics[display_name]["source"],
            "peak_to_peak_db": float(np.ptp(tapered)),
            "rms_db": float(np.sqrt(np.mean(tapered ** 2))),
        }

    old_mic_count = len(data["components"].get("mic", {}))
    data["components"]["mic"] = new_mics

    with open(COMPONENTS_JSON, "w") as f:
        json.dump(data, f, indent=2)

    n_atk = sum(1 for m in new_mics.values() if m["source"] == "audio_test_kitchen")
    n_rh = len(new_mics) - n_atk
    print(f"Replaced {old_mic_count} mics with {len(new_mics)} ({n_atk} ATK, {n_rh} RH)")
    print(f"Wrote {COMPONENTS_JSON}")


# --- Generate CurveData.h ---

def sanitize_ident(name):
    s = name.replace(" ", "").replace("-", "_")
    if s and s[0].isdigit():
        s = "_" + s
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def header_display_name(comp_type, name):
    if comp_type == "cab":
        return re.sub(r"^\d+\s+", "", name)
    return name


def normalize_curve(mag):
    peak = max(abs(v) for v in mag)
    if peak < 0.001:
        return mag
    scale = TARGET_PEAK_DB / peak
    return [v * scale for v in mag]


def format_float_array(values):
    lines = []
    for i in range(0, len(values), FLOATS_PER_LINE):
        chunk = values[i : i + FLOATS_PER_LINE]
        formatted = ", ".join(f"{v:.4f}f" for v in chunk)
        lines.append("    " + formatted)
    return ",\n".join(lines)



# Gain compensation is now done at runtime in PluginProcessor.cpp — it measures
# the RMS of the actual combined magnitude response and normalizes to unity.
# No precomputed LUTs needed.


def generate_header():
    """Generate src/CurveData.h from extracted_components.json."""
    with open(COMPONENTS_JSON) as f:
        data = json.load(f)

    freqs = data["frequencies_hz"]
    components = data["components"]
    num_bins = len(freqs)


    out = []
    out.append("#pragma once")
    out.append("// Auto-generated by tools/curves/compile.py — do not edit")
    out.append("#include <array>")
    out.append("")
    out.append("namespace CurveData {")
    out.append("")
    out.append(f"static constexpr int kNumBins = {num_bins};")
    out.append(f"static constexpr std::array<float, kNumBins> kFrequencies = {{")
    out.append(format_float_array(freqs))
    out.append("};")
    out.append("")
    out.append("struct Curve {")
    out.append("    const char* name;")
    out.append("    const float* data;")
    out.append("};")
    out.append("")

    # Cab LPF: modeled from real cab IR data as a simple bandpass shape.
    # Real cabs are essentially a bandpass: HPF below ~80Hz, LPF above ~6kHz.
    # We model this as two smooth rolloffs meeting at unity in the passband,
    # rather than using the raw (noisy) IR average directly.
    cab_lpf_path = REPO / "data" / "ir" / "v30_cab_comparison.json"
    if cab_lpf_path.exists():
        with open(cab_lpf_path) as f:
            ir_data = json.load(f)
        ir_freqs = np.array(ir_data["frequencies_hz"])
        all_cab_mags = [np.array(ir_data["cabs"][n]["magnitude_db"])
                        for n in ir_data["cabs"]]
        avg_cab = np.mean(all_cab_mags, axis=0)

        # Interpolate onto our frequency grid
        target_freqs = np.array(freqs)
        log_ir = np.log10(np.maximum(ir_freqs, 1.0))
        log_tgt = np.log10(np.maximum(target_freqs, 1.0))
        cab_curve = np.interp(log_tgt, log_ir, avg_cab)

        # Find the average level in the passband (100Hz-4kHz) as our 0dB reference
        passband = (target_freqs >= 100) & (target_freqs <= 4000)
        ref_db = np.mean(cab_curve[passband])
        cab_curve -= ref_db  # passband averages to 0dB

        # Build a clean bandpass: unity in passband, rolloff at edges
        # HPF: 12dB/oct below 80Hz (2nd order)
        # LPF: 12dB/oct above 6kHz (2nd order)
        cab_lpf_db = np.zeros(len(target_freqs))
        for i, f in enumerate(target_freqs):
            if f < 80:
                # HPF rolloff: 12dB/octave
                cab_lpf_db[i] = 12.0 * np.log2(max(f, 1.0) / 80.0)
            elif f > 6000:
                # LPF rolloff: 12dB/octave
                cab_lpf_db[i] = -12.0 * np.log2(f / 6000.0)

        cab_lpf_linear = (10.0 ** (cab_lpf_db / 20.0)).tolist()

        out.append("// Cab bandpass filter — modeled from real cab IRs.")
        out.append("// Unity (1.0) from 80Hz-6kHz, 12dB/oct HPF below, 12dB/oct LPF above.")
        out.append(f"static constexpr float kCabLPF[] = {{")
        out.append(format_float_array(cab_lpf_linear))
        out.append("};")
        out.append("")

        for label, freq in [("20", 20), ("40", 40), ("80", 80), ("1k", 1000),
                             ("6k", 6000), ("10k", 10000), ("16k", 16000)]:
            idx = int(np.argmin(np.abs(target_freqs - freq)))
            print(f"  Cab LPF @ {label}: {cab_lpf_db[idx]:+.1f}dB ({cab_lpf_linear[idx]:.3f})")
        print(f"Cab LPF: 12dB/oct HPF<80Hz + LPF>6kHz (from {len(all_cab_mags)} cab IRs)")

    for comp_type in ("cab", "speaker", "mic", "position"):
        if comp_type not in components:
            continue

        singular, plural = TYPE_CONFIG[comp_type]
        items = components[comp_type]
        sorted_names = sorted(items.keys())

        for name in sorted_names:
            ident = sanitize_ident(name)
            var_name = f"k{singular}_{ident}"
            mag = items[name]["magnitude_db"]
            raw_peak = max(abs(v) for v in mag)
            print(f"  {name:12s} peak {raw_peak:5.2f}dB")
            out.append(f"static constexpr float {var_name}[] = {{")
            out.append(format_float_array(mag))
            out.append("};")
            out.append("")

        entries = []
        for name in sorted_names:
            ident = sanitize_ident(name)
            var_name = f"k{singular}_{ident}"
            dname = header_display_name(comp_type, name)
            entries.append(f'    {{"{dname}", {var_name}}}')

        out.append(f"static constexpr Curve k{plural}[] = {{")
        out.append(",\n".join(entries))
        out.append("};")
        out.append(f"static constexpr int kNum{plural} = {len(sorted_names)};")
        out.append("")
        print(f"{plural}: {len(sorted_names)}")

    # Mic groups — map group names to indices into kMics[] (alphabetically sorted)
    if "mic" in components:
        mic_sorted = sorted(components["mic"].keys())
        out.append("struct MicGroup {")
        out.append("    const char* name;")
        out.append("    const int* indices;")
        out.append("    int count;")
        out.append("};")
        out.append("")

        group_entries = []
        for group_name in MIC_GROUPS:
            # Find which mic indices belong to this group
            indices = []
            for slug, info in MICS.items():
                if info.get("group") == group_name:
                    display = info["name"]
                    if display in mic_sorted:
                        indices.append(mic_sorted.index(display))
            indices.sort()
            ident = sanitize_ident(group_name)
            arr_name = f"kMicGroup_{ident}_indices"
            out.append(f"static constexpr int {arr_name}[] = {{ {', '.join(str(i) for i in indices)} }};")
            group_entries.append(f'    {{"{group_name}", {arr_name}, {len(indices)}}}')

        out.append("")
        out.append(f"static constexpr MicGroup kMicGroups[] = {{")
        out.append(",\n".join(group_entries))
        out.append("};")
        out.append(f"static constexpr int kNumMicGroups = {len(MIC_GROUPS)};")
        out.append("")
        print(f"MicGroups: {len(MIC_GROUPS)}")

    out.append("} // namespace CurveData")
    out.append("")

    HEADER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    HEADER_OUTPUT.write_text("\n".join(out))
    print(f"Wrote {HEADER_OUTPUT}")
