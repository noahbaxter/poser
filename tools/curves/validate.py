#!/usr/bin/env python3
"""Validate digitized mic curves against ATK ground truth.

For the 5 mics where ATK lab measurements exist, overlays ATK vs digitized
(normalized at 1kHz) and reports RMS agreement.

Outputs:
  /tmp/poser/validation_report.png  — overlay plots
  stdout                            — summary table
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
TMP = Path("/tmp/poser")

BANDS = [
    (40, 200, "Low"),
    (200, 2000, "Mid"),
    (2000, 8000, "Upper-mid"),
    (8000, 20000, "High"),
]

# Mics with both ATK and digitized data
MICS = {
    "SM57": {"slug": "sm57", "atk_csv": "shure_sm57.csv"},
    "SM58": {"slug": "sm58", "atk_csv": "shure_sm58.csv"},
    "SM7B": {"slug": "sm7b", "atk_csv": "shure_sm7b.csv"},
    "C414": {"slug": "c414", "atk_csv": "akg_c414_xlii.csv"},
    "U87":  {"slug": "u87",  "atk_csv": "neumann_u87.csv"},
}


def normalize_at_1k(freqs, dbs):
    db_at_1k = np.interp(1000, freqs, dbs)
    return dbs - db_at_1k


def load_atk(csv_name):
    path = REPO / "data" / "curves" / "atk" / csv_name
    if not path.exists():
        return None
    freqs, dbs = [], []
    for line in path.read_text().strip().splitlines():
        f, d = line.split(",")
        freqs.append(float(f))
        dbs.append(float(d))
    return np.array(freqs), np.array(dbs)


def load_digitized(slug):
    path = REPO / "data" / "curves" / "digitized" / f"{slug}.json"
    if not path.exists():
        return None
    with open(path) as f:
        d = json.load(f)
    try:
        pts = d["curves"]["single"]["curves"][0]["data"]
    except (KeyError, IndexError):
        return None
    freqs = np.array([p["hz"] for p in pts])
    dbs = np.array([p["db"] for p in pts])
    mask = freqs <= 20000
    return freqs[mask], dbs[mask]


def rms_between(f1, db1, f2, db2, lo=20, hi=20000):
    common_lo = max(f1[0], f2[0], lo)
    common_hi = min(f1[-1], f2[-1], hi)
    if common_lo >= common_hi:
        return float("nan")
    grid = np.logspace(np.log10(common_lo), np.log10(common_hi), 256)
    d1 = np.interp(grid, f1, db1)
    d2 = np.interp(grid, f2, db2)
    return float(np.sqrt(np.mean((d1 - d2) ** 2)))


def main():
    TMP.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, len(MICS), figsize=(4 * len(MICS), 4))

    print(f"{'Mic':<8} {'RMS':>6} {'Low':>6} {'Mid':>6} {'UMid':>6} {'High':>6}")
    print("-" * 45)

    for i, (name, info) in enumerate(MICS.items()):
        ax = axes[i]

        atk = load_atk(info["atk_csv"])
        dig = load_digitized(info["slug"])

        if atk is None or dig is None:
            ax.set_title(f"{name} (missing data)")
            continue

        atk_f, atk_db = atk
        dig_f, dig_db = dig
        atk_n = normalize_at_1k(atk_f, atk_db)
        dig_n = normalize_at_1k(dig_f, dig_db)

        ax.semilogx(atk_f, atk_n, color="#2196F3", linewidth=1.5, label="ATK")
        ax.semilogx(dig_f, dig_n, color="#ff0000", linewidth=1.5, alpha=0.7, label="Digitized")
        ax.set_xlim(20, 20000)
        ax.set_ylim(-20, 15)
        ax.grid(True, which="both", alpha=0.2)
        ax.set_xticks([100, 1000, 10000])
        ax.set_xticklabels(["100", "1k", "10k"], fontsize=7)

        rms = rms_between(atk_f, atk_n, dig_f, dig_n)
        ax.set_title(f"{name} ({rms:.2f}dB)", fontsize=10)
        if i == 0:
            ax.legend(fontsize=7)

        band_vals = []
        for lo, hi, bname in BANDS:
            band_vals.append(rms_between(atk_f, atk_n, dig_f, dig_n, lo, hi))

        print(f"{name:<8} {rms:>5.2f}d "
              + "  ".join(f"{v:>4.2f}d" for v in band_vals))

    plt.tight_layout()
    out = TMP / "validation_report.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
