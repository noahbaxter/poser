#!/usr/bin/env python3
"""Build mic curves from all sources into extracted_components.json.

Reads from ATK CSVs (ground truth) and digitized JSONs (RecordingHacks),
interpolates onto the shared 512 log-spaced frequency grid, and updates
the mic section of extracted_components.json.
Cab/speaker/position components are left unchanged.

Source priority: ATK where available, otherwise digitized curve index 0.
"""

import csv
import json
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ATK_DIR = REPO / "data" / "curves" / "atk"
DIGITIZED_DIR = REPO / "data" / "curves" / "digitized"
COMPONENTS_JSON = REPO / "data" / "curves" / "extracted_components.json"

# ATK ground truth (takes priority over digitized)
ATK_MICS = {
    "SM57": "shure_sm57.csv",
    "SM58": "shure_sm58.csv",
    "SM7B": "shure_sm7b.csv",
    "U87":  "neumann_u87.csv",
    "C414": "akg_c414_xlii.csv",
}

# Digitized mic slug -> display name (for mics not in ATK)
DIGITIZED_MICS = {
    "beta-52a":   "Beta 52A",
    "c451b":      "C451 B",
    "d112":       "D112",
    "re20":       "RE20",
    "r84":        "R84",
    "md421":      "MD421",
    "d6":         "D6",
    "coles-4038": "Coles 4038",
    "m88-tg":     "M88 TG",
    "km184":      "KM184",
    "e906":       "e906",
}


def load_atk_csv(path):
    """Load ATK CSV: freq,dB pairs. Returns (freqs, dBs) arrays."""
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
    """Load digitized JSON curve. Returns (freqs, dBs) arrays."""
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
    """Interpolate source data onto target frequency grid using log-frequency."""
    log_src = np.log10(np.maximum(src_freqs, 1.0))
    log_tgt = np.log10(np.maximum(target_freqs, 1.0))
    return np.interp(log_tgt, log_src, src_dbs)


def normalize_at_1k(freqs, dbs):
    """Shift curve so 0dB at 1kHz."""
    db_at_1k = np.interp(1000, freqs, dbs)
    return dbs - db_at_1k


def main():
    with open(COMPONENTS_JSON) as f:
        data = json.load(f)

    target_freqs = np.array(data["frequencies_hz"])
    print(f"Target grid: {len(target_freqs)} points, "
          f"{target_freqs[0]:.1f}-{target_freqs[-1]:.1f} Hz")

    new_mics = {}

    # ATK mics (ground truth)
    for display_name, csv_name in sorted(ATK_MICS.items()):
        csv_path = ATK_DIR / csv_name
        if not csv_path.exists():
            print(f"  SKIP {display_name}: {csv_path} not found")
            continue

        freqs, dbs = load_atk_csv(csv_path)
        source_label = "audio_test_kitchen"
        print(f"  {display_name}: {len(freqs)} pts from ATK, "
              f"{freqs[0]:.1f}-{freqs[-1]:.1f} Hz")

        dbs = normalize_at_1k(freqs, dbs)
        interp_dbs = interpolate_to_grid(freqs, dbs, target_freqs)
        interp_dbs -= np.mean(interp_dbs)

        new_mics[display_name] = {
            "magnitude_db": interp_dbs.tolist(),
            "source": source_label,
            "peak_to_peak_db": float(np.ptp(interp_dbs)),
            "rms_db": float(np.sqrt(np.mean(interp_dbs ** 2))),
        }

    # Digitized mics
    for slug, display_name in sorted(DIGITIZED_MICS.items()):
        freqs, dbs = load_digitized(slug)
        if freqs is None:
            print(f"  SKIP {display_name}: {slug}.json not found")
            continue

        source_label = "recordinghacks"
        print(f"  {display_name}: {len(freqs)} pts from RH ({slug}), "
              f"{freqs[0]:.1f}-{freqs[-1]:.1f} Hz")

        dbs = normalize_at_1k(freqs, dbs)
        interp_dbs = interpolate_to_grid(freqs, dbs, target_freqs)
        interp_dbs -= np.mean(interp_dbs)

        print(f"         → range {interp_dbs.min():.1f} to {interp_dbs.max():.1f} dB")

        new_mics[display_name] = {
            "magnitude_db": interp_dbs.tolist(),
            "source": source_label,
            "peak_to_peak_db": float(np.ptp(interp_dbs)),
            "rms_db": float(np.sqrt(np.mean(interp_dbs ** 2))),
        }

    # Replace mic section
    old_mic_count = len(data["components"].get("mic", {}))
    data["components"]["mic"] = new_mics

    with open(COMPONENTS_JSON, "w") as f:
        json.dump(data, f, indent=2)

    n_atk = sum(1 for name in new_mics if new_mics[name]["source"] == "audio_test_kitchen")
    n_rh = sum(1 for name in new_mics if new_mics[name]["source"] == "recordinghacks")
    print(f"\nReplaced {old_mic_count} mics with {len(new_mics)} ({n_atk} ATK, {n_rh} RH)")
    print(f"Wrote {COMPONENTS_JSON}")
    print(f"\nNow run: python3 tools/curves/generate_header.py")


if __name__ == "__main__":
    main()
