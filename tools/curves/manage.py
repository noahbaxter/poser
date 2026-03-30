#!/usr/bin/env python3
"""Mic curve management — the one script to run.

Usage:
    python3 tools/curves/manage.py prepare          Download sources + export masks
    python3 tools/curves/manage.py build [slugs...]  Digitize → compile → generate header
    python3 tools/curves/manage.py guide <slugs...>  Interactive curve tracer
    python3 tools/curves/manage.py preview [slugs...] Show curves overlaid on source

Aliases: view → preview, trace → guide
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

import fmt
import paths
from digitize import cmd_prepare, cmd_build
from compile import build_components, generate_header
from guide import main as cmd_guide
from registry import MICS


def _find_untraced_mics():
    """Find mics that have a datasheet PNG but no guide data yet."""
    untraced = []
    for slug in sorted(MICS):
        png = paths.datasheet_original(slug)
        if not png.exists():
            continue
        guide = paths.datasheet_guide(slug)
        if not guide.exists():
            untraced.append(slug)
    return untraced


def cmd_full_build(args):
    """Full pipeline: guide untreated mics → digitize → compile → generate header."""
    # Auto-detect mics that need tracing
    untraced = _find_untraced_mics()
    if args.slugs:
        # If specific slugs given, only trace those that need it
        untraced = [s for s in untraced if s in args.slugs]

    if untraced:
        print(fmt.heading(f"Step 0: Trace {len(untraced)} new datasheet(s)"))
        print(fmt.dim(f"  {', '.join(untraced)}"))
        try:
            cmd_guide(slugs=untraced)
        except KeyboardInterrupt:
            plt.close("all")
            print(f"\n{fmt.warn('Interrupted.')}")
            return

    print(fmt.heading("Step 1: Digitize guides → JSON"))
    cmd_build(args)

    print(fmt.heading("Step 2: Compile curves → extracted_components.json"))
    build_components()

    print(fmt.heading("Step 3: Generate CurveData.h"))
    generate_header()

    print(fmt.ok("Done. Rebuild the plugin to hear the new curves."))


def cmd_preview(args):
    """Show digitized curves overlaid on original datasheet/source image."""
    slugs = args.slugs if args.slugs else sorted(MICS.keys())

    for slug in slugs:
        if slug not in MICS:
            print(fmt.err(f"Unknown slug: {slug}"))
            continue

        info = MICS[slug]
        dig_path = paths.find_curve(slug)
        if dig_path is None or not dig_path.exists():
            print(fmt.warn(f"{slug}: no digitized data (run build first)"))
            continue

        with open(dig_path) as f:
            dig = json.load(f)

        curves_data = dig.get("curves", {}).get("single", {}).get("curves", [])
        if not curves_data:
            print(fmt.warn(f"{slug}: no curves in digitized data"))
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

        # Normalize group at 1kHz using first curve as reference
        ref_db = 0
        first_pts = curves_data[0].get("data", [])
        if first_pts:
            ref_f = np.array([p["hz"] for p in first_pts])
            ref_d = np.array([p["db"] for p in first_pts])
            ref_db = float(np.interp(1000, ref_f, ref_d))

        # Plot digitized curves
        colors = ["#dd0000", "#0044dd", "#dd00dd", "#dd6600"]
        for i, curve in enumerate(curves_data):
            pts = curve.get("data", [])
            if not pts:
                continue
            freqs = np.array([p["hz"] for p in pts])
            dbs = np.array([p["db"] for p in pts]) - ref_db
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
        from guide import _format_freq_axis
        _format_freq_axis(ax_curve)
        plt.tight_layout()

    if slugs:
        plt.show()


def main():
    # Resolve aliases before argparse sees them
    aliases = {"view": "preview", "trace": "guide"}
    if len(sys.argv) > 1 and sys.argv[1] in aliases:
        sys.argv[1] = aliases[sys.argv[1]]

    parser = argparse.ArgumentParser(
        description="Mic curve management",
        epilog="Aliases: view → preview, trace → guide\n\nEdit registry.py to add/remove mics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("prepare", help="Download source images and export red-pixel masks")

    build_p = sub.add_parser("build", help="Full pipeline: digitize → compile → generate C++ header")
    build_p.add_argument("slugs", nargs="*", help="Specific mic slugs (default: all)")

    guide_p = sub.add_parser("guide", help="Interactive curve tracer (opens matplotlib windows)")
    guide_p.add_argument("slugs", nargs="*", help="Mic slugs to trace")
    guide_p.add_argument("--all", action="store_true", help="Process all mics with datasheet config")

    preview_p = sub.add_parser("preview", help="Show digitized curves overlaid on source images")
    preview_p.add_argument("slugs", nargs="*", help="Specific mic slugs (default: all)")

    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "build":
        cmd_full_build(args)
    elif args.command == "guide":
        if args.slugs:
            slugs = args.slugs
        elif args.all:
            slugs = []  # empty = all mics
        else:
            # Default: continue where we left off — unbuilt mics with datasheet config
            unbuilt = [s for s, m in MICS.items()
                       if "datasheet" in m
                       and (paths.find_curve(s) is None or not paths.find_curve(s).exists())]
            if not unbuilt:
                print(fmt.ok("All mics with datasheets are already built."))
                print(fmt.dim("  Use --all to re-process, or pass specific slugs."))
                sys.exit(0)
            print(fmt.dim(f"  Continuing with {len(unbuilt)} unbuilt mic(s)..."))
            slugs = sorted(unbuilt)
        try:
            cmd_guide(slugs=slugs)
        except KeyboardInterrupt:
            plt.close("all")
            print(f"\n{fmt.warn('Interrupted.')}")
    elif args.command == "preview":
        try:
            cmd_preview(args)
        except KeyboardInterrupt:
            plt.close("all")
            print(f"\n{fmt.warn('Interrupted.')}")
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        plt.close("all")
        print(f"\n{fmt.warn('Interrupted.')}")
        sys.exit(1)
