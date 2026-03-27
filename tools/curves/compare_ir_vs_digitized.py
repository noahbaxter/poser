#!/usr/bin/env python3
"""Compare mic curves from IR extraction vs RecordingHacks digitization.

Cross-validates two independent data sources:
- IR-extracted: derived from impulse response decomposition
- Digitized: extracted from RecordingHacks frequency response chart images
- ATK: Audio Test Kitchen lab measurements (where available)

If the shapes roughly match, both pipelines are working correctly.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
TMP = Path("/tmp/poser")

# Map between naming conventions
# IR name -> (RH file_id, display name) — only mics with digitized RH data
MIC_MAP = {
    "SM58": ("0006-0253", "SM58"),
    "SM7B": ("0006-0255", "SM7B"),
    "C414": ("0006-0307", "C414"),
    "U87":  ("0006-0860", "U87"),
    "SM57": (None, "SM57"),  # no RH digitization, ATK only
}

# Which curve key and index to use for each
RH_CURVE_INFO = {
    "SM58": ("second", 0),
    "SM7B": ("second", 0),
    "C414": ("second", 0),
    "U87":  ("second", 0),
}

# ATK CSV files (where available)
ATK_MAP = {
    "SM57": "shure_sm57.csv",
    "SM58": "shure_sm58.csv",
    "SM7B": "shure_sm7b.csv",
    "C414": "akg_c414_xlii.csv",
    "U87":  "neumann_u87.csv",
}


def load_ir_curves():
    """Load mic components from IR extraction."""
    path = REPO / "data" / "curves" / "extracted_components.json"
    with open(path) as f:
        d = json.load(f)
    freqs = np.array(d["frequencies_hz"])
    mics = {}
    for name, info in d["components"]["mic"].items():
        mics[name] = (freqs, np.array(info["magnitude_db"]))
    return mics


def load_rh_curve(file_id, key, index):
    """Load a digitized curve from RecordingHacks data."""
    path = REPO / "data" / "curves" / "digitized" / f"{file_id}.json"
    with open(path) as f:
        d = json.load(f)
    pts = d["curves"][key]["curves"][index]["data"]
    freqs = np.array([p["hz"] for p in pts])
    dbs = np.array([p["db"] for p in pts])
    return freqs, dbs


def load_atk_csv(filename):
    """Load an ATK measurement CSV."""
    path = REPO / "data" / "curves" / "atk" / filename
    if not path.exists():
        return None, None
    freqs, dbs = [], []
    for line in path.read_text().strip().splitlines():
        f, d = line.split(",")
        freqs.append(float(f))
        dbs.append(float(d))
    return np.array(freqs), np.array(dbs)


def normalize_at_1k(freqs, dbs):
    """Normalize to 0dB at 1kHz."""
    db_at_1k = np.interp(1000, freqs, dbs)
    return dbs - db_at_1k


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    ir_mics = load_ir_curves()

    fig, axes = plt.subplots(len(MIC_MAP), 1, figsize=(14, 4 * len(MIC_MAP)))

    for i, (ir_name, (rh_file, display)) in enumerate(MIC_MAP.items()):
        ax = axes[i]

        # Load IR source (always available)
        ir_f, ir_db = ir_mics[ir_name]
        ir_norm = normalize_at_1k(ir_f, ir_db)
        ax.semilogx(ir_f, ir_norm, color="#4CAF50", linewidth=1.5, label="IR extraction")

        # Load RH digitized (if available)
        rh_f, rh_norm, rms_label = None, None, ""
        if rh_file and ir_name in RH_CURVE_INFO:
            rh_key, rh_idx = RH_CURVE_INFO[ir_name]
            rh_f, rh_db = load_rh_curve(rh_file, rh_key, rh_idx)
            rh_norm = normalize_at_1k(rh_f, rh_db)
            ax.semilogx(rh_f, rh_norm, color="#9410a0", linewidth=1.5, alpha=0.8, label="RecordingHacks")

            # RMS difference
            common_lo = max(ir_f[0], rh_f[0])
            common_hi = min(ir_f[-1], rh_f[-1])
            grid = np.logspace(np.log10(common_lo), np.log10(common_hi), 256)
            rms = np.sqrt(np.mean((np.interp(grid, ir_f, ir_norm) - np.interp(grid, rh_f, rh_norm)) ** 2))
            rms_label = f" | IR-RH RMS: {rms:.1f}dB"

        # Load ATK measured (if available)
        atk_f, atk_db = load_atk_csv(ATK_MAP.get(ir_name, ""))
        if atk_f is not None:
            atk_norm = normalize_at_1k(atk_f, atk_db)
            ax.semilogx(atk_f, atk_norm, color="#2196F3", linewidth=1.5, alpha=0.7, label="ATK measured")

        ax.set_xlim(20, 20000)
        ax.set_ylim(-20, 15)
        ax.set_ylabel("dB (rel. 1kHz)")
        ax.set_title(f"{display} — IR vs RH vs ATK{rms_label}", fontsize=11)
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, which="both", alpha=0.3)
        ax.set_xticks([20, 100, 1000, 10000, 20000])
        ax.set_xticklabels(["20", "100", "1k", "10k", "20k"])

    axes[-1].set_xlabel("Frequency (Hz)")
    plt.tight_layout()
    out = TMP / "ir_vs_rh_vs_atk_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")

    # Summary
    print("\nCross-validation summary:")
    for ir_name, (rh_file, display) in MIC_MAP.items():
        ir_f, ir_db = ir_mics[ir_name]
        ir_norm = normalize_at_1k(ir_f, ir_db)

        if rh_file and ir_name in RH_CURVE_INFO:
            rh_key, rh_idx = RH_CURVE_INFO[ir_name]
            rh_f, rh_db = load_rh_curve(rh_file, rh_key, rh_idx)
            rh_norm = normalize_at_1k(rh_f, rh_db)
            common_lo = max(ir_f[0], rh_f[0])
            common_hi = min(ir_f[-1], rh_f[-1])
            grid = np.logspace(np.log10(common_lo), np.log10(common_hi), 256)
            rms = np.sqrt(np.mean((np.interp(grid, ir_f, ir_norm) - np.interp(grid, rh_f, rh_norm)) ** 2))
            print(f"  {display:6s}: IR vs RH RMS = {rms:.2f}dB")
        else:
            print(f"  {display:6s}: (no RH data, ATK only)")


if __name__ == "__main__":
    main()
