#!/usr/bin/env python3
"""Compare curves from all sources (ATK, datasheet, RH) side by side.

Plots each source's primary curve overlaid, plus a theoretical average.
Output: /tmp/poser/source_comparison_{slug}.png per mic,
        /tmp/poser/source_comparison_all.png summary grid.
"""

import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths
from registry import MICS

TARGET_FREQS = np.logspace(np.log10(20), np.log10(20000), 512)


def load_source(path):
    """Load all curves from a JSON file. Returns list of (freqs, dbs) or None."""
    if not path.exists():
        return None
    with open(path) as f:
        d = json.load(f)
    try:
        curves_list = d["curves"]["single"]["curves"]
    except (KeyError, TypeError):
        return None
    results = []
    for c in curves_list:
        pts = c.get("data", [])
        if pts:
            freqs = np.array([p["hz"] for p in pts])
            dbs = np.array([p["db"] for p in pts])
            results.append((freqs, dbs))
    return results if results else None


def load_atk(slug):
    """Load ATK CSV. Returns (freqs, dbs) or None."""
    path = paths.atk_original(slug)
    if not path.exists():
        return None
    freqs, dbs = [], []
    with open(path) as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                try:
                    freqs.append(float(row[0]))
                    dbs.append(float(row[1]))
                except ValueError:
                    continue
    if not freqs:
        return None
    return np.array(freqs), np.array(dbs)


def normalize_1k(freqs, dbs):
    """Normalize to 0dB at 1kHz, then subtract mean (matches compile pipeline)."""
    ref = np.interp(1000, freqs, dbs)
    normed = dbs - ref
    return normed - np.mean(normed)


def interp_to_grid(freqs, dbs):
    """Interpolate to common log-spaced grid."""
    log_src = np.log10(np.maximum(freqs, 1.0))
    log_tgt = np.log10(TARGET_FREQS)
    return np.interp(log_tgt, log_src, dbs)


def main():
    out_dir = Path("/tmp/poser")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collect mics with at least 2 sources
    mics_to_plot = []
    for slug in sorted(MICS):
        info = MICS[slug]
        sources = {}  # name → list of interpolated curves

        atk = load_atk(slug)
        if atk:
            f, d = atk
            sources["ATK"] = [interp_to_grid(f, normalize_1k(f, d))]

        ds = load_source(paths.datasheet_curve(slug))
        if ds:
            curves = []
            ref = np.interp(1000, ds[0][0], ds[0][1])
            for f, d in ds:
                normed = d - ref
                grid = interp_to_grid(f, normed)
                curves.append(grid - np.mean(grid))
            sources["Datasheet"] = curves

        rh = load_source(paths.rh_curve(slug))
        if rh:
            curves = []
            ref = np.interp(1000, rh[0][0], rh[0][1])
            for f, d in rh:
                normed = d - ref
                grid = interp_to_grid(f, normed)
                curves.append(grid - np.mean(grid))
            sources["RH"] = curves

        if len(sources) >= 2:
            mics_to_plot.append((slug, info["name"], sources))

    if not mics_to_plot:
        print("No mics with multiple sources found.")
        return

    # Per-mic plots
    colors = {"ATK": "#00bb00", "Datasheet": "#dd0000", "RH": "#0066dd"}
    for slug, name, sources in mics_to_plot:
        fig, ax = plt.subplots(1, 1, figsize=(12, 5))
        for src_name, curves in sources.items():
            for vi, curve in enumerate(curves):
                label = src_name if vi == 0 else None
                ax.semilogx(TARGET_FREQS, curve, color=colors[src_name],
                            linewidth=2.5 if src_name == "ATK" else 1.8,
                            alpha=0.9 if vi == 0 else 0.5, label=label)

        # Average of primary curves only
        primaries = [curves[0] for curves in sources.values()]
        avg = np.mean(primaries, axis=0)
        ax.semilogx(TARGET_FREQS, avg, color="#000000", linewidth=2,
                    linestyle="--", alpha=0.7, label="Avg (primary)")

        # Spread of primaries
        lo = np.min(primaries, axis=0)
        hi = np.max(primaries, axis=0)
        ax.fill_between(TARGET_FREQS, lo, hi, alpha=0.08, color="#000000")

        ax.set_xlim(20, 20000)
        ax.set_ylim(-20, 15)
        ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("dB (normalized at 1kHz)")
        total_curves = sum(len(c) for c in sources.values())
        ax.set_title(f"{name} — source comparison ({total_curves} curves from {len(sources)} sources)", fontweight="bold")
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, which="both", alpha=0.3)
        plt.tight_layout()

        plot_path = out_dir / f"source_comparison_{slug}.png"
        fig.savefig(plot_path, dpi=150)
        plt.close(fig)
        print(f"  {name:12s} {' + '.join(sources.keys()):30s} → {plot_path.name}")

    # Summary grid
    n = len(mics_to_plot)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 3.5 * rows))
    axes = axes.flatten() if n > 1 else [axes]

    for i, (slug, name, sources) in enumerate(mics_to_plot):
        ax = axes[i]
        for src_name, curves in sources.items():
            for vi, curve in enumerate(curves):
                ax.semilogx(TARGET_FREQS, curve, color=colors[src_name],
                            linewidth=1.5 if src_name == "ATK" else 1.0,
                            alpha=0.85 if vi == 0 else 0.4)

        primaries = [curves[0] for curves in sources.values()]
        avg = np.mean(primaries, axis=0)
        ax.semilogx(TARGET_FREQS, avg, color="#000", linewidth=1.2,
                    linestyle="--", alpha=0.6)

        lo = np.min(primaries, axis=0)
        hi = np.max(primaries, axis=0)
        ax.fill_between(TARGET_FREQS, lo, hi, alpha=0.08, color="#000")
        spread = np.mean(hi - lo)

        ax.set_xlim(20, 20000)
        ax.set_ylim(-15, 12)
        ax.axhline(0, color="gray", linewidth=0.3, linestyle="--")
        ax.set_title(f"{name} (±{spread:.1f}dB avg)", fontsize=9, fontweight="bold")
        ax.grid(True, which="both", alpha=0.2)
        ax.tick_params(labelsize=7)

    # Hide unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle("Source Comparison: ATK (green) · Datasheet (red) · RH (blue) · Average (dashed)",
                 fontsize=11, y=1.01)
    plt.tight_layout()
    grid_path = out_dir / "source_comparison_all.png"
    fig.savefig(grid_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Summary grid → {grid_path}")
    print(f"  {n} mics compared across {out_dir}/")


if __name__ == "__main__":
    main()
