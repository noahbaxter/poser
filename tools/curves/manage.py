#!/usr/bin/env python3
"""Mic curve management — the one script to run.

Usage:
    python3 tools/curves/manage.py prepare    Download sources + export masks
    python3 tools/curves/manage.py build      Digitize → compile → generate header

Workflow:
    1. Add mic to registry.py (RH ID, slug, display name)
    2. Run 'prepare' — downloads source image, exports red pixel mask
    3. If the mask has multiple curves (proximity variants, switch positions):
       - Open data/curves/recordinghacks/masks/{slug}.png in an image editor
       - Make copies, erase unwanted lines in each
       - Save as {slug}_1.png, {slug}_2.png, etc.
    4. Run 'build' — digitizes all masks, compiles into plugin data
    5. Rebuild the plugin
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

# Run from the tools/curves/ directory so relative imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths
from digitize import cmd_prepare, cmd_build
from compile import build_components, generate_header
from guide import main as cmd_guide
from registry import MICS


def cmd_full_build(args):
    """Digitize masks → compile extracted_components.json → generate CurveData.h"""
    print("=" * 60)
    print("Step 1: Digitize masks → JSON")
    print("=" * 60)
    cmd_build(args)

    print()
    print("=" * 60)
    print("Step 2: Compile curves → extracted_components.json")
    print("=" * 60)
    build_components()

    print()
    print("=" * 60)
    print("Step 3: Generate CurveData.h")
    print("=" * 60)
    generate_header()

    print()
    print("Done. Rebuild the plugin to hear the new curves.")


def cmd_preview(args):
    """Show digitized curves overlaid on original datasheet/source image."""
    slugs = args.slugs if args.slugs else sorted(MICS.keys())

    for slug in slugs:
        if slug not in MICS:
            print(f"Unknown slug: {slug}")
            continue

        info = MICS[slug]
        dig_path = paths.find_curve(slug)
        if dig_path is None or not dig_path.exists():
            print(f"{slug}: no digitized data (run build first)")
            continue

        with open(dig_path) as f:
            dig = json.load(f)

        curves_data = dig.get("curves", {}).get("single", {}).get("curves", [])
        if not curves_data:
            print(f"{slug}: no curves in digitized data")
            continue

        # Find source image
        ds = info.get("datasheet")
        if ds:
            src_path = paths.datasheet_original(slug)
            plot_crop = ds.get("plot_bounds")
        else:
            src_path = paths.rh_original(slug)
            plot_crop = None

        # Load ATK if available
        has_atk = info.get("has_atk")
        atk_f, atk_d = None, None
        if has_atk:
            atk_path = paths.atk_original(slug)
            if atk_path.exists():
                af, ad = [], []
                for line in open(atk_path):
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        try:
                            af.append(float(parts[0]))
                            ad.append(float(parts[1]))
                        except ValueError:
                            continue
                if af:
                    atk_f, atk_d = np.array(af), np.array(ad)
                    ref = np.interp(1000, atk_f, atk_d)
                    atk_d = atk_d - ref

        # Build figure
        has_src = src_path.exists()
        n_rows = 2 if has_src else 1
        fig, axes = plt.subplots(n_rows, 1, figsize=(14, 4 * n_rows),
                                  gridspec_kw={"height_ratios": [1, 1.2] if has_src else [1]})
        fig.canvas.manager.set_window_title(f"Preview: {slug}")

        if has_src:
            ax_img, ax_curve = axes
            src = np.array(Image.open(src_path).convert("RGB"))
            if plot_crop:
                l, t, r, b = plot_crop
                src = src[t:b, l:r]
            ax_img.imshow(src, aspect="auto")
            ax_img.set_title(f"{slug} — {info['name']}", fontsize=12, fontweight="bold")
            ax_img.set_xticks([])
            ax_img.set_yticks([])
        else:
            ax_curve = axes if n_rows == 1 else axes[0]

        # Plot ATK
        if atk_f is not None:
            ax_curve.semilogx(atk_f, atk_d, color="#00bb00", linewidth=2.5,
                              alpha=0.8, label="ATK lab", zorder=2)

        # Plot digitized curves
        colors = ["#dd0000", "#0044dd", "#dd00dd", "#dd6600"]
        for i, curve in enumerate(curves_data):
            pts = curve.get("data", [])
            if not pts:
                continue
            freqs = [p["hz"] for p in pts]
            dbs = [p["db"] for p in pts]
            src_label = curve.get("source", "")
            note = curve.get("note", "")
            label = f"#{i} {note} ({src_label}, {len(pts)} pts)".strip()
            ax_curve.semilogx(freqs, dbs, color=colors[i % len(colors)],
                              linewidth=3, label=label, zorder=3)

        ax_curve.set_xlim(20, 20000)
        ax_curve.axhline(0, color="gray", linewidth=0.5, linestyle="--")
        ax_curve.set_xlabel("Frequency (Hz)")
        ax_curve.set_ylabel("dB")
        ax_curve.set_title("Digitized curves", fontsize=11)
        ax_curve.legend(loc="upper left", fontsize=9)
        ax_curve.grid(True, which="both", alpha=0.3)
        plt.tight_layout()

    if slugs:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Mic curve management",
        epilog="Edit registry.py to add/remove mics.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("prepare", help="Download sources, export masks")
    sub.add_parser("build", help="Digitize → compile → generate header (full pipeline)")
    guide_parser = sub.add_parser("guide", help="Interactive guide tracer for datasheets")
    guide_parser.add_argument("slugs", nargs="*", help="Specific mic slugs (default: all)")
    preview_parser = sub.add_parser("preview", help="Show digitized curves vs source image")
    preview_parser.add_argument("slugs", nargs="*", help="Specific mic slugs (default: all)")

    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "build":
        cmd_full_build(args)
    elif args.command == "guide":
        sys.argv = ["guide"] + (args.slugs or [])
        cmd_guide()
    elif args.command == "preview":
        cmd_preview(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
