#!/usr/bin/env python3
"""Regenerate comparison plots for all digitized curves.

Reads existing JSON data and source PNGs, generates fresh comparison plots.
Does NOT re-digitize — just re-plots from saved data.
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

TMP_DIR = Path("/tmp/poser")


def plot_one(json_path):
    with open(json_path) as f:
        data = json.load(f)

    file_id = json_path.stem  # e.g., "0006-0253"
    source_png = TMP_DIR / f"{file_id}.png"
    out_path = TMP_DIR / f"{file_id}_comparison.png"

    has_source = source_png.exists()
    nrows = 2 if has_source else 1
    height = 8 if has_source else 5
    ratios = {"height_ratios": [1, 1.2]} if has_source else {}

    fig, axes = plt.subplots(nrows, 1, figsize=(12, height),
                              gridspec_kw=ratios if has_source else {})
    if nrows == 1:
        axes = [axes]

    if has_source:
        src = Image.open(source_png)
        axes[0].imshow(np.array(src.convert("RGB")))
        axes[0].set_title("Original (RecordingHacks)", fontsize=11)
        axes[0].axis("off")

    ax = axes[-1]
    base_colors = ["#f69410", "#9410a0"]
    line_styles = ["-", "--", ":", "-."]

    mic_ids = data.get("mic_ids", ["?", "?"])
    for i, (key, label_prefix) in enumerate([("first", mic_ids[0]), ("second", mic_ids[1])]):
        if key not in data["curves"]:
            continue
        info = data["curves"][key]
        for j, curve in enumerate(info["curves"]):
            pts = curve["data"]
            if not pts:
                continue
            freqs = [p["hz"] for p in pts]
            dbs = [p["db"] for p in pts]
            style = line_styles[j % len(line_styles)]
            alpha = 1.0 if j == 0 else 0.6
            lw = 1.5 if j == 0 else 1.0
            label = f"{label_prefix} #{j} ({len(pts)} pts)"
            ax.semilogx(freqs, dbs, color=base_colors[i], linewidth=lw,
                        linestyle=style, alpha=alpha, label=label)

    ax.set_xlim(20, 20000)
    ax.set_ylim(-20, 20)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("dB")
    ax.set_title("Digitized (cleaned)", fontsize=11)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xticks([20, 100, 1000, 10000, 20000])
    ax.set_xticklabels(["20Hz", "100Hz", "1kHz", "10kHz", "20kHz"])

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {out_path}")


def main():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    jsons = sorted(
        list(paths.DATASHEET_CURVES.glob("*.json")) +
        list(paths.RH_CURVES.glob("*.json")) +
        list(paths.ATK_CURVES.glob("*.json"))
    )
    print(f"Plotting {len(jsons)} files...\n")
    for j in jsons:
        print(f"{j.stem}:")
        plot_one(j)
    print(f"\nDone. Open with: open /tmp/poser/*_comparison.png")


if __name__ == "__main__":
    main()
