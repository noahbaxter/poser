#!/usr/bin/env python3
"""Compare SM57 frequency response from different sources.

Plots the Audio Test Kitchen (ATK) curve vs the RecordingHacks digitized curve
side by side to evaluate how well the digitizer is working.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent


def load_atk_csv():
    """Load the Audio Test Kitchen SM57 CSV."""
    path = REPO / "data" / "curves" / "atk" / "shure_sm57.csv"
    freqs, dbs = [], []
    for line in path.read_text().strip().splitlines():
        f, d = line.split(",")
        freqs.append(float(f))
        dbs.append(float(d))
    return np.array(freqs), np.array(dbs)


def load_digitized():
    """Load the RecordingHacks digitized SM57 (first curve in 0006-0253)."""
    path = REPO / "data" / "curves" / "digitized" / "0006-0253.json"
    with open(path) as f:
        data = json.load(f)
    pts = data["curves"]["first"]["data"]
    freqs = np.array([p["hz"] for p in pts])
    dbs = np.array([p["db"] for p in pts])
    # Clip to 20kHz — anything past that is blend noise
    mask = freqs <= 20000
    return freqs[mask], dbs[mask]


def normalize_at_1k(freqs, dbs):
    """Normalize curve so it's 0dB at 1kHz (standard mic reference)."""
    db_at_1k = np.interp(1000, freqs, dbs)
    return dbs - db_at_1k


def main():
    atk_f, atk_db = load_atk_csv()
    rh_f, rh_db = load_digitized()

    # Normalize both to 0dB at 1kHz
    atk_norm = normalize_at_1k(atk_f, atk_db)
    rh_norm = normalize_at_1k(rh_f, rh_db)

    # Common overlap range for differencing
    common_lo = max(atk_f[0], rh_f[0])
    common_hi = min(atk_f[-1], rh_f[-1])
    common_grid = np.logspace(np.log10(common_lo), np.log10(common_hi), 512)
    atk_interp = np.interp(common_grid, atk_f, atk_norm)
    rh_interp = np.interp(common_grid, rh_f, rh_norm)
    diff = rh_interp - atk_interp
    rms = np.sqrt(np.mean(diff**2))

    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    xticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    xlabels = ["20", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"]

    # --- Plot 1: Raw as extracted ---
    ax = axes[0]
    ax.semilogx(atk_f, atk_db, color="#2196F3", linewidth=1.5, label=f"ATK ({len(atk_f)} pts)")
    ax.semilogx(rh_f, rh_db, color="#f69410", linewidth=1.5, alpha=0.8, label=f"RecordingHacks ({len(rh_f)} pts)")
    ax.set_xlim(20, 20000)
    ax.set_ylim(-25, 15)
    ax.set_ylabel("dB")
    ax.set_title("SM57 — Raw (different reference levels)")
    ax.legend(loc="upper left")
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels)

    # --- Plot 2: Normalized at 1kHz ---
    ax = axes[1]
    ax.semilogx(atk_f, atk_norm, color="#2196F3", linewidth=1.5, label="ATK (0dB @ 1kHz)")
    ax.semilogx(rh_f, rh_norm, color="#f69410", linewidth=1.5, alpha=0.8, label="RecordingHacks (0dB @ 1kHz)")
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.set_xlim(20, 20000)
    ax.set_ylim(-20, 15)
    ax.set_ylabel("dB (rel. 1kHz)")
    ax.set_title("SM57 — Normalized at 1kHz")
    ax.legend(loc="upper left")
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels)

    # --- Plot 3: Difference ---
    ax = axes[2]
    ax.semilogx(common_grid, diff, color="#4CAF50", linewidth=1.5)
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.fill_between(common_grid, diff, 0, alpha=0.15, color="#4CAF50")
    ax.set_xlim(20, 20000)
    ax.set_ylim(-8, 8)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("dB difference")
    ax.set_title(f"Difference (RH − ATK) | {common_lo:.0f}–{common_hi:.0f}Hz | RMS: {rms:.2f}dB")
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels)

    plt.tight_layout()
    tmp_dir = Path("/tmp/poser")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / "sm57_source_comparison.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")
    print(f"ATK:  {len(atk_f)} pts, {atk_f[0]:.0f}–{atk_f[-1]:.0f}Hz")
    print(f"RH:   {len(rh_f)} pts, {rh_f[0]:.0f}–{rh_f[-1]:.0f}Hz")
    print(f"Diff: RMS={rms:.2f}dB over {common_lo:.0f}–{common_hi:.0f}Hz")

    # Per-band breakdown
    bands = [(40, 200, "Low"), (200, 2000, "Mid"), (2000, 8000, "Upper-mid"), (8000, 20000, "High")]
    for lo, hi, name in bands:
        mask = (common_grid >= lo) & (common_grid <= hi)
        if mask.any():
            band_rms = np.sqrt(np.mean(diff[mask]**2))
            print(f"  {name:10s} ({lo:5d}–{hi:5d}Hz): RMS={band_rms:.2f}dB")


if __name__ == "__main__":
    main()
