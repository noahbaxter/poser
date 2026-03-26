#!/usr/bin/env python3
"""Convert ATK mic response CSVs to our extracted_components.json format.

Reads CSVs from data/mic_responses/, interpolates onto our 512 log-spaced
frequency grid, and updates the mic section of extracted_components.json.
Cab/speaker/position components are left unchanged.
"""

import csv
import json
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data" / "curves" / "atk"
COMPONENTS_JSON = REPO / "data" / "curves" / "extracted_components.json"

# Map CSV filenames to display names
MIC_MAP = {
    "shure_sm57.csv": "SM57",
    "shure_sm58.csv": "SM58",
    "shure_sm7b.csv": "SM7B",
    "neumann_u87.csv": "U87",
    "akg_c414_xlii.csv": "C414",
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


def interpolate_to_grid(src_freqs, src_dbs, target_freqs):
    """Interpolate source data onto target frequency grid."""
    # ATK data goes down to 1Hz, our grid starts at 20Hz
    # Use log-frequency interpolation for smoother results
    log_src = np.log10(np.maximum(src_freqs, 1.0))
    log_tgt = np.log10(np.maximum(target_freqs, 1.0))
    return np.interp(log_tgt, log_src, src_dbs)


def main():
    # Load existing components
    with open(COMPONENTS_JSON) as f:
        data = json.load(f)

    target_freqs = np.array(data["frequencies_hz"])
    print(f"Target grid: {len(target_freqs)} points, {target_freqs[0]:.1f}-{target_freqs[-1]:.1f} Hz")

    # Build new mic section from ATK data
    new_mics = {}

    for csv_name, display_name in sorted(MIC_MAP.items()):
        csv_path = DATA_DIR / csv_name
        if not csv_path.exists():
            print(f"  SKIP {display_name}: {csv_path} not found")
            continue

        freqs, dbs = load_atk_csv(csv_path)
        print(f"  {display_name}: {len(freqs)} points, {freqs[0]:.1f}-{freqs[-1]:.1f} Hz, "
              f"range {dbs.min():.1f} to {dbs.max():.1f} dB")

        # Interpolate onto our grid
        interp_dbs = interpolate_to_grid(freqs, dbs, target_freqs)

        # ATK data is relative to 1kHz (0dB at 1kHz). Our extracted components
        # are relative to grand mean. For consistency, subtract the mean so the
        # curve averages to ~0dB (the "character" relative to flat).
        mean_db = np.mean(interp_dbs)
        interp_dbs -= mean_db
        print(f"         → interpolated, mean-subtracted, range {interp_dbs.min():.1f} to {interp_dbs.max():.1f} dB")

        new_mics[display_name] = {
            "magnitude_db": interp_dbs.tolist(),
            "source": "audio_test_kitchen",
            "peak_to_peak_db": float(np.ptp(interp_dbs)),
            "rms_db": float(np.sqrt(np.mean(interp_dbs**2))),
        }

    # Replace mic section
    old_mic_count = len(data["components"].get("mic", {}))
    data["components"]["mic"] = new_mics

    # Save
    with open(COMPONENTS_JSON, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nReplaced {old_mic_count} IR-extracted mics with {len(new_mics)} ATK measured mics")
    print(f"Wrote {COMPONENTS_JSON}")
    print(f"\nNow run: python3 tools/curves/generate_header.py")


if __name__ == "__main__":
    main()
