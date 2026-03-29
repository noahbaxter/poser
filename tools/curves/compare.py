#!/usr/bin/env python3
"""Compare datasheet extraction vs existing digitized curves.

Usage:
    python3 tools/curves/compare.py              # all mics with datasheets
    python3 tools/curves/compare.py d112 u87     # specific mics

Generates /tmp/poser/compare_{slug}.png with three panels:
  Top: datasheet image (cropped to plot area)
  Mid: old curve (RH or hand-digitized)
  Bot: new curve (datasheet extraction) overlaid with old
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from digitize import digitize_datasheet
from registry import MICS

OUT_DIR = Path("/tmp/poser")


def compare_mic(slug):
    info = MICS.get(slug)
    if not info or "datasheet" not in info:
        return
    ds = info["datasheet"]
    ds_path = paths.datasheet_original(slug)
    if not ds_path.exists():
        return

    # Load existing
    existing_path = paths.find_curve(slug)
    if existing_path is None or not existing_path.exists():
        print(f"  {slug}: no existing data, skipping")
        return
    with open(existing_path) as f:
        existing = json.load(f)
    try:
        old_pts = existing["curves"]["single"]["curves"][0]["data"]
    except (KeyError, IndexError):
        return

    # Extract new
    results = digitize_datasheet(slug, ds, paths.DATASHEET_ORIGINALS)
    if not results or "single" not in results or not results["single"]["curves"]:
        return

    new_data = results["single"]["curves"][0]

    old_freqs = np.array([p["hz"] for p in old_pts])
    old_dbs = np.array([p["db"] for p in old_pts])
    new_freqs = np.array([d[0] for d in new_data])
    new_dbs = np.array([d[1] for d in new_data])

    # Normalize both at 1kHz
    old_at_1k = np.interp(1000, old_freqs, old_dbs)
    new_at_1k = np.interp(1000, new_freqs, new_dbs)
    old_norm = old_dbs - old_at_1k
    new_norm = new_dbs - new_at_1k

    # Figure
    left, top, right, bottom = ds["plot_bounds"]
    fig, (ax_img, ax_cmp) = plt.subplots(2, 1, figsize=(14, 7),
                                          gridspec_kw={"height_ratios": [1, 1.2]})

    # Top: datasheet cropped
    src = np.array(Image.open(ds_path).convert("RGB"))
    cropped = src[top:bottom, left:right]
    ax_img.imshow(cropped, aspect="auto")
    ax_img.set_title(f"{info['name']} — {ds_path.name}", fontsize=11)
    ax_img.set_xticks([])
    ax_img.set_yticks([])

    # Bottom: overlay
    n_old = len(old_pts)
    old_label = f"Old ({'hand' if n_old < 50 else 'RH'}, {n_old} pts)"
    ax_cmp.semilogx(old_freqs, old_norm, color="#888888", linewidth=2,
                     label=old_label, alpha=0.7)
    ax_cmp.semilogx(new_freqs, new_norm, color="#e74c3c", linewidth=1.5,
                     label=f"New (datasheet, {len(new_data)} pts)")

    # Compute RMS diff
    lo = max(old_freqs[0], new_freqs[0], 40)
    hi = min(old_freqs[-1], new_freqs[-1], 18000)
    grid = np.logspace(np.log10(lo), np.log10(hi), 200)
    old_interp = np.interp(grid, old_freqs, old_norm)
    new_interp = np.interp(grid, new_freqs, new_norm)
    rms = np.sqrt(np.mean((new_interp - old_interp) ** 2))

    ax_cmp.set_xlim(10, 25000)
    ax_cmp.set_ylim(-20, 20)
    ax_cmp.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax_cmp.set_xlabel("Frequency (Hz)")
    ax_cmp.set_ylabel("dB (normalized at 1kHz)")
    ax_cmp.set_title(f"Old vs New — RMS diff: {rms:.1f} dB", fontsize=11)
    ax_cmp.legend(loc="upper left", fontsize=9)
    ax_cmp.grid(True, which="both", alpha=0.3)
    ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    ax_cmp.set_xticks(ticks)
    ax_cmp.set_xticklabels([f"{t//1000}k" if t >= 1000 else str(t) for t in ticks])

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"compare_{slug}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {out_path}")


def main():
    if len(sys.argv) > 1:
        slugs = sys.argv[1:]
    else:
        slugs = [s for s in sorted(MICS) if "datasheet" in MICS[s]]

    for slug in slugs:
        compare_mic(slug)

    print(f"\nComparison plots in {OUT_DIR}/")
    if len(sys.argv) > 1:
        import subprocess
        last = OUT_DIR / f"compare_{slugs[-1]}.png"
        subprocess.run(["open", str(last)], check=False)


if __name__ == "__main__":
    main()
