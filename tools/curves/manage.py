#!/usr/bin/env python3
"""Mic curve management — the one script to run.

Usage:
    python3 tools/curves/manage.py prepare    Download sources + export masks
    python3 tools/curves/manage.py build      Digitize → compile → generate header

Workflow:
    1. Add mic to registry.py (RH ID, slug, display name)
    2. Run 'prepare' — downloads source image, exports red pixel mask
    3. If the mask has multiple curves (proximity variants, switch positions):
       - Open data/curves/masks/{slug}.png in an image editor
       - Make copies, erase unwanted lines in each
       - Save as {slug}_1.png, {slug}_2.png, etc.
    4. Run 'build' — digitizes all masks, compiles into plugin data
    5. Rebuild the plugin
"""

import argparse
import sys
from pathlib import Path

# Run from the tools/curves/ directory so relative imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from digitize import cmd_prepare, cmd_build
from compile import build_components, generate_header


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


def main():
    parser = argparse.ArgumentParser(
        description="Mic curve management",
        epilog="Edit registry.py to add/remove mics.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("prepare", help="Download sources, export masks")
    sub.add_parser("build", help="Digitize → compile → generate header (full pipeline)")

    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "build":
        cmd_full_build(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
