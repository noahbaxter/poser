#!/usr/bin/env python3
"""Plot V30 canonical curves across all available cabs. Opens a matplotlib window.

Usage:
    python3 scripts/preview_v30_cabs.py                  # Default: 1/6 octave smoothing
    python3 scripts/preview_v30_cabs.py --smooth 1/3     # 1/3 octave
    python3 scripts/preview_v30_cabs.py --smooth 1/12    # 1/12 octave (more detail)
    python3 scripts/preview_v30_cabs.py --smooth none     # Raw, no smoothing
    python3 scripts/preview_v30_cabs.py --smooth all      # Side-by-side: raw, 1/6, 1/3
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from decomposition import get_log_freqs, load_ir_magnitude, octave_smooth

import matplotlib
matplotlib.use('macosx')
import matplotlib.pyplot as plt
import numpy as np

INVENTORY = Path("/Users/noahbaxter/Code/personal/plugins/poser/output/ir_inventory.json")
OUTPUT_DIR = Path("/Users/noahbaxter/Code/personal/plugins/poser/output")
OUTPUT_JSON = OUTPUT_DIR / "v30_cab_comparison.json"
OUTPUT_PNG = OUTPUT_DIR / "v30_cab_comparison.png"


def parse_smooth_arg():
    """Parse --smooth argument."""
    for i, arg in enumerate(sys.argv):
        if arg == "--smooth" and i + 1 < len(sys.argv):
            val = sys.argv[i + 1]
            if val == "none":
                return [None]
            if val == "all":
                return [None, 1/12, 1/6, 1/3]
            # Parse fraction like "1/6" or decimal like "0.167"
            if "/" in val:
                num, den = val.split("/")
                return [float(num) / float(den)]
            return [float(val)]
    return [1/6]  # default


def main():
    smooth_levels = parse_smooth_arg()

    with open(INVENTORY) as f:
        inv = json.load(f)

    log_freqs = get_log_freqs()

    # Collect all V30 files grouped by cab, across all collections
    # Skip Seacow (no parsed mic data) and combo speakers (V30+G80 etc.)
    cab_files = {}  # cab_name -> [file_paths]
    for coll_name, coll in inv["collections"].items():
        for combo_name, combo in coll["combos"].items():
            speaker = combo.get("speaker") or ""
            # Match V30 exactly or V30 variants (V30-MB1, V30-EN1)
            if speaker != "V30" and not speaker.startswith("V30-"):
                continue
            cab = combo.get("cab", "")
            if not cab:
                continue

            # Use collection name to disambiguate same cab from different packs
            # But prefer to group by actual cab name for cross-collection comparison
            key = cab
            if cab not in cab_files:
                cab_files[key] = []

            for f in combo["files"]:
                path = f.get("path", "")
                if path and not f.get("special", False):
                    cab_files[key].append(path)

    print(f"Found V30 in {len(cab_files)} unique cabs")
    for cab, files in sorted(cab_files.items()):
        print(f"  {cab}: {len(files)} files")

    # Compute raw canonical curve for each cab (average across all files)
    cab_raw = {}
    for cab, files in sorted(cab_files.items()):
        if len(files) < 2:
            print(f"  Skipping {cab} (only {len(files)} files)")
            continue
        mags = []
        for fp in files:
            p = Path(fp)
            if not p.exists():
                continue
            mags.append(load_ir_magnitude(p, log_freqs))
        if mags:
            cab_raw[cab] = np.mean(mags, axis=0)
            print(f"  {cab}: averaged {len(mags)} files")

    # Apply smoothing at each requested level
    # cab_curves_by_level[level] = {cab: curve}
    cab_curves_by_level = {}
    for level in smooth_levels:
        if level is None:
            cab_curves_by_level[level] = cab_raw
        else:
            label = f"1/{int(1/level)}" if level and 1/level == int(1/level) else f"{level}"
            print(f"  Smoothing at {label} octave...")
            cab_curves_by_level[level] = {
                cab: octave_smooth(curve, log_freqs, level)
                for cab, curve in cab_raw.items()
            }

    # Use the first smoothing level as the "primary" for JSON output
    primary_level = smooth_levels[0]
    cab_curves = cab_curves_by_level[primary_level]

    # --- Analysis ---

    stride = 4
    freqs_sparse = log_freqs[::stride].tolist()
    cab_names = sorted(cab_curves.keys())

    # Frequency bands for perceptual analysis
    BANDS = {
        "sub_bass":   (20, 80),
        "bass":       (80, 250),
        "low_mids":   (250, 500),
        "mids":       (500, 2000),
        "presence":   (2000, 5000),
        "brilliance": (5000, 10000),
        "air":        (10000, 20000),
    }

    def band_mask(lo, hi):
        return (log_freqs >= lo) & (log_freqs <= hi)

    def band_mae(curve_a, curve_b, lo, hi):
        m = band_mask(lo, hi)
        if not np.any(m):
            return 0.0
        return float(np.mean(np.abs(curve_a[m] - curve_b[m])))

    # Pairwise differences — overall and per-band
    pairwise = {}
    for i, a in enumerate(cab_names):
        for b in cab_names[i+1:]:
            diff = cab_curves[a] - cab_curves[b]
            entry = {
                "mae_db": round(float(np.mean(np.abs(diff))), 2),
                "max_diff_db": round(float(np.max(np.abs(diff))), 2),
                "bands": {},
            }
            for bname, (lo, hi) in BANDS.items():
                entry["bands"][bname] = round(band_mae(cab_curves[a], cab_curves[b], lo, hi), 2)
            pairwise[f"{a} vs {b}"] = entry

    # Overall spread: at each frequency, how much do the cabs vary?
    all_curves = np.array([cab_curves[c] for c in cab_names])
    spread_db = np.ptp(all_curves, axis=0)  # max - min at each freq bin
    band_spread = {}
    for bname, (lo, hi) in BANDS.items():
        m = band_mask(lo, hi)
        band_spread[bname] = {
            "mean_spread_db": round(float(np.mean(spread_db[m])), 2),
            "max_spread_db": round(float(np.max(spread_db[m])), 2),
        }

    # Decision metrics
    # "Guitar cab character" band: 200Hz-5kHz
    character_mask = band_mask(200, 5000)
    character_spread_mean = float(np.mean(spread_db[character_mask]))
    character_spread_max = float(np.max(spread_db[character_mask]))

    # Average pairwise MAE in character band
    character_maes = []
    for i, a in enumerate(cab_names):
        for b in cab_names[i+1:]:
            m = character_mask
            character_maes.append(float(np.mean(np.abs(cab_curves[a][m] - cab_curves[b][m]))))
    avg_character_mae = np.mean(character_maes) if character_maes else 0

    # Sort pairs by how different they are
    pairs_ranked = sorted(pairwise.items(), key=lambda x: x[1]["mae_db"], reverse=True)

    # Print decision summary
    print("\n" + "=" * 70)
    print("ANALYSIS: Are V30 cabs meaningfully different?")
    print("=" * 70)
    print(f"\nSpread across {len(cab_names)} cabs (max-min at each frequency):")
    for bname, vals in band_spread.items():
        lo, hi = BANDS[bname]
        bar = "█" * int(vals["mean_spread_db"])
        print(f"  {bname:12s} ({lo:5d}-{hi:5d}Hz): mean {vals['mean_spread_db']:5.1f}dB  max {vals['max_spread_db']:5.1f}dB  {bar}")

    print(f"\nCharacter band (200-5kHz):")
    print(f"  Mean spread: {character_spread_mean:.1f} dB")
    print(f"  Max spread:  {character_spread_max:.1f} dB")
    print(f"  Avg pairwise MAE: {avg_character_mae:.1f} dB")

    print(f"\nMost different cab pairs (top 10):")
    for pair, vals in pairs_ranked[:10]:
        print(f"  {pair:45s}  MAE {vals['mae_db']:4.1f}dB  (presence: {vals['bands']['presence']:.1f}dB, mids: {vals['bands']['mids']:.1f}dB)")

    print(f"\nMost similar cab pairs (bottom 5):")
    for pair, vals in pairs_ranked[-5:]:
        print(f"  {pair:45s}  MAE {vals['mae_db']:4.1f}dB")

    # Verdict
    print(f"\n--- VERDICT ---")
    if avg_character_mae >= 3.0:
        print(f"STRONG: Cabs differ by {avg_character_mae:.1f}dB avg in character band. Clearly audible differences.")
    elif avg_character_mae >= 1.5:
        print(f"MODERATE: Cabs differ by {avg_character_mae:.1f}dB avg in character band. Audible but subtle.")
    else:
        print(f"WEAK: Cabs differ by only {avg_character_mae:.1f}dB avg in character band. Barely audible.")
    print("=" * 70)

    # Dump JSON
    json_data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "description": "V30 canonical magnitude curves across all available cabs with perceptual analysis",
        "speaker": "V30",
        "smoothing": smooth_label(primary_level),
        "num_cabs": len(cab_curves),
        "frequencies_hz": freqs_sparse,
        "frequency_bands": {k: {"low_hz": v[0], "high_hz": v[1]} for k, v in BANDS.items()},
        "cabs": {},
        "band_spread": band_spread,
        "character_band_200_5000hz": {
            "mean_spread_db": round(character_spread_mean, 2),
            "max_spread_db": round(character_spread_max, 2),
            "avg_pairwise_mae_db": round(avg_character_mae, 2),
        },
        "pairwise_differences": pairwise,
        "pairwise_ranked_by_mae": [
            {"pair": pair, **vals} for pair, vals in pairs_ranked
        ],
    }

    for cab, curve in sorted(cab_curves.items()):
        json_data["cabs"][cab] = {
            "num_files_averaged": len(cab_files[cab]),
            "magnitude_db": curve[::stride].tolist(),
            "mean_db": round(float(np.mean(curve)), 2),
            "peak_db": round(float(np.max(curve)), 2),
            "peak_freq_hz": round(float(log_freqs[np.argmax(curve)]), 1),
            "per_band_mean_db": {
                bname: round(float(np.mean(curve[band_mask(lo, hi)])), 2)
                for bname, (lo, hi) in BANDS.items()
            },
        }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(json_data, f, indent=2)
    print(f"\nSaved JSON: {OUTPUT_JSON}")

    # Plot
    def smooth_label(level):
        if level is None:
            return "Raw (no smoothing)"
        if level and 1/level == int(1/level):
            return f"1/{int(1/level)} octave"
        return f"{level} octave"

    if len(smooth_levels) == 1:
        fig, ax = plt.subplots(figsize=(14, 8))
        for cab, curve in sorted(cab_curves.items()):
            ax.semilogx(log_freqs, curve, label=cab, linewidth=1.3, alpha=0.85)
        ax.set_xlim(20, 20000)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Magnitude (dB)")
        ax.set_title(f"V30 Across {len(cab_curves)} Cabs ({smooth_label(smooth_levels[0])})")
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, alpha=0.3)
    else:
        ncols = len(smooth_levels)
        fig, axes = plt.subplots(1, ncols, figsize=(7 * ncols, 8))
        if ncols == 1:
            axes = [axes]
        for idx, level in enumerate(smooth_levels):
            ax = axes[idx]
            curves = cab_curves_by_level[level]
            for cab, curve in sorted(curves.items()):
                ax.semilogx(log_freqs, curve, label=cab, linewidth=1.1, alpha=0.8)
            ax.set_xlim(20, 20000)
            ax.set_xlabel("Frequency (Hz)")
            ax.set_ylabel("Magnitude (dB)")
            ax.set_title(smooth_label(level))
            ax.legend(loc="upper right", fontsize=6)
            ax.grid(True, alpha=0.3)
        fig.suptitle(f"V30 Across {len(cab_raw)} Cabs — Smoothing Comparison", fontsize=14)

    fig.tight_layout()
    fig.savefig(OUTPUT_PNG, dpi=150)
    print(f"Saved PNG: {OUTPUT_PNG}")
    plt.show()


if __name__ == "__main__":
    main()
