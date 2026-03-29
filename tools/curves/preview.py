#!/usr/bin/env python3
"""Preview a datasheet extraction: side-by-side source image vs extracted curve.

Usage:
    python3 tools/curves/preview.py sm57          # single mic
    python3 tools/curves/preview.py sm57 e602     # multiple mics
    python3 tools/curves/preview.py --all         # all mics with datasheets

Output goes to /tmp/poser/preview_{slug}.png and opens in Preview.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from digitize import digitize_datasheet, _pixel_to_freq_ds, _pixel_to_db_ds
from registry import MICS

OUT_DIR = Path("/tmp/poser")


def preview_mic(slug):
    """Extract and preview a single mic."""
    info = MICS.get(slug)
    if not info:
        print(f"Unknown slug: {slug}")
        return False

    ds = info.get("datasheet")
    if not ds:
        print(f"{slug}: no datasheet config")
        return False

    ds_path = paths.datasheet_original(slug)
    if not ds_path.exists():
        print(f"{slug}: datasheet not found: {ds_path}")
        return False

    # Extract curves
    results = digitize_datasheet(slug, ds, paths.DATASHEET_ORIGINALS)
    if not results or "single" not in results or not results["single"]["curves"]:
        print(f"{slug}: extraction failed")
        return False

    curves = results["single"]["curves"]

    # Build figure
    left, top, right, bottom = ds["plot_bounds"]
    freq_lo, freq_hi = ds["freq_range"]
    db_top, db_bottom = ds["db_range"]

    fig, (ax_img, ax_curve) = plt.subplots(2, 1, figsize=(14, 8),
                                            gridspec_kw={"height_ratios": [1, 1]})

    # Top: source image cropped to plot area
    src = np.array(Image.open(ds_path).convert("RGB"))
    cropped = src[top:bottom, left:right]
    ax_img.imshow(cropped, aspect="auto")
    ax_img.set_title(f"{info['name']} — Datasheet ({ds_path.name})", fontsize=12)
    ax_img.set_xticks([])
    ax_img.set_yticks([])

    # Bottom: extracted curves
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12"]
    for i, data in enumerate(curves):
        freqs = [d[0] for d in data]
        dbs = [d[1] for d in data]
        color = colors[i % len(colors)]
        ax_curve.semilogx(freqs, dbs, color=color, linewidth=1.5,
                          label=f"Curve {i} ({len(data)} pts)")

    ax_curve.set_xlim(max(10, freq_lo * 0.8), freq_hi * 1.2)
    ax_curve.set_ylim(db_bottom - 2, db_top + 2)
    ax_curve.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax_curve.set_xlabel("Frequency (Hz)")
    ax_curve.set_ylabel("dB")
    ax_curve.set_title(f"{info['name']} — Extracted ({len(curves)} curve(s))", fontsize=12)
    ax_curve.legend(loc="lower right", fontsize=8)
    ax_curve.grid(True, which="both", alpha=0.3)

    # Standard frequency ticks
    ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    visible = [t for t in ticks if freq_lo * 0.8 <= t <= freq_hi * 1.2]
    ax_curve.set_xticks(visible)
    ax_curve.set_xticklabels([f"{t//1000}k" if t >= 1000 else str(t) for t in visible])

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"preview_{slug}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → {out_path}")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    if sys.argv[1] == "--all":
        slugs = [s for s in sorted(MICS) if "datasheet" in MICS[s]]
    else:
        slugs = sys.argv[1:]

    generated = []
    for slug in slugs:
        if preview_mic(slug):
            generated.append(slug)

    if generated:
        print(f"\n{len(generated)} preview(s) saved to {OUT_DIR}/")
        # Open the last one in Preview
        import subprocess
        last = OUT_DIR / f"preview_{generated[-1]}.png"
        subprocess.run(["open", str(last)], check=False)


if __name__ == "__main__":
    main()
