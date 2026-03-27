"""Compile mic curves into plugin data.

Reads ATK CSVs + digitized JSONs → extracted_components.json → CurveData.h

Internal module used by manage.py. Not meant to be run directly.
"""

import csv
import json
import re
from pathlib import Path

import numpy as np

from registry import MICS

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
    freqs, dbs = [], []
    with open(path) as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                try:
                    freqs.append(float(row[0]))
                    dbs.append(float(row[1]))
                except ValueError:
                    continue
    return np.array(freqs), np.array(dbs)


def load_digitized(slug, curve_index=0):
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


# --- Build extracted_components.json ---

def build_components():
    """Merge ATK + digitized curves into extracted_components.json."""
    with open(COMPONENTS_JSON) as f:
        data = json.load(f)

    target_freqs = np.array(data["frequencies_hz"])
    print(f"Target grid: {len(target_freqs)} points, "
          f"{target_freqs[0]:.1f}-{target_freqs[-1]:.1f} Hz")

    new_mics = {}

    for slug in sorted(MICS):
        info = MICS[slug]
        display_name = info["name"]
        atk_csv = info.get("atk_csv")

        # ATK ground truth takes priority
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

        new_mics[display_name] = {
            "magnitude_db": interp_dbs.tolist(),
            "source": source,
            "peak_to_peak_db": float(np.ptp(interp_dbs)),
            "rms_db": float(np.sqrt(np.mean(interp_dbs ** 2))),
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
            if comp_type != "mic":
                mag = normalize_curve(mag)
                norm_peak = max(abs(v) for v in mag)
                print(f"  {name:12s} raw peak {raw_peak:5.2f}dB → normalized {norm_peak:5.2f}dB")
            else:
                print(f"  {name:12s} raw peak {raw_peak:5.2f}dB (natural)")
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

    out.append("} // namespace CurveData")
    out.append("")

    HEADER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    HEADER_OUTPUT.write_text("\n".join(out))
    print(f"Wrote {HEADER_OUTPUT}")
