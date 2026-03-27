#!/usr/bin/env python3
"""Digitize microphone frequency response curves from RecordingHacks single-mic PNGs.

Downloads single-mic graphs from recordinghacks.com, extracts red curve pixels
as masks for hand-editing, then digitizes the cleaned masks into frequency/dB data.

Usage:
    python3 tools/curves/digitize.py prepare   # Download sources, export masks
    python3 tools/curves/digitize.py build     # Digitize masks → JSON curves
"""

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import requests
from PIL import Image


# --- Constants ---

DB_TOP = 20.0
DB_BOTTOM = -20.0

# RecordingHacks ID -> mic name
RH_MIC_NAMES = {
    "0006": "Shure SM57",
    "0219": "Shure Beta 52A",
    "0253": "Shure SM58",
    "0255": "Shure SM7B",
    "0307": "AKG C414 XL II",
    "0323": "AKG C451 B",
    "0335": "AKG D112",
    "0417": "Electro-Voice RE20",
    "0429": "AEA R84",
    "0552": "Sennheiser MD421",
    "0567": "Audix D6",
    "0701": "Coles 4038",
    "0860": "Neumann U87 Ai",
    "1009": "Beyerdynamic M88 TG",
    "1091": "Neumann KM184",
    "1184": "Sennheiser e906",
}

# Canonical slug for each mic (used for filenames)
MIC_SLUGS = {
    "0006": "sm57",
    "0219": "beta-52a",
    "0253": "sm58",
    "0255": "sm7b",
    "0307": "c414",
    "0323": "c451b",
    "0335": "d112",
    "0417": "re20",
    "0429": "r84",
    "0552": "md421",
    "0567": "d6",
    "0701": "coles-4038",
    "0860": "u87",
    "1009": "m88-tg",
    "1091": "km184",
    "1184": "e906",
}

# Reverse lookup: slug -> RH ID
SLUG_TO_ID = {v: k for k, v in MIC_SLUGS.items()}


# --- Plot geometry ---

def detect_plot_bounds(img_rgb):
    """Find plot area by locating black border lines.

    Returns (left, right, top, bottom) pixel coordinates.
    """
    w, h = img_rgb.size
    pixels = img_rgb.load()

    h_lines = []
    for y in range(h):
        black_count = sum(1 for x in range(w) if pixels[x, y][:3] == (0, 0, 0))
        if black_count > w * 0.7:
            h_lines.append(y)

    v_lines = []
    for x in range(w):
        black_count = sum(1 for y in range(h) if pixels[x, y][:3] == (0, 0, 0))
        if black_count > h * 0.5:
            v_lines.append(x)

    def cluster(vals):
        if not vals:
            return []
        clusters = [[vals[0]]]
        for v in vals[1:]:
            if v - clusters[-1][-1] <= 3:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [int(np.mean(c)) for c in clusters]

    h_clusters = cluster(h_lines)
    v_clusters = cluster(v_lines)

    if len(h_clusters) >= 2 and len(v_clusters) >= 2:
        return v_clusters[0], v_clusters[-1], h_clusters[0], h_clusters[-1]

    print("  WARNING: Could not detect plot boundaries, using defaults")
    return 40, 1179, 30, 371


def calibrate_x_axis(img_orig, left, right, top, bottom):
    """Calibrate log-frequency X axis from actual gridline positions.

    Finds vertical gray gridlines, identifies decade groups, and computes
    the log-frequency mapping. The plot spans wider than 20Hz-20kHz —
    the borders are at ~10Hz and ~39kHz with the labeled range inside.

    Returns (A, B) where freq = 10^((x - B) / A).
    """
    px = img_orig.load()

    # Find vertical gray gridlines (palette index 3 = 148,148,148)
    grid_cols = []
    for x in range(left + 2, right - 2):
        gray_count = 0
        for y in range(top + 2, bottom - 2):
            val = px[x, y]
            # Handle both palette mode and RGB mode
            if img_orig.mode == "P":
                is_grid = (val == 3)
            else:
                is_grid = (val[:3] == (148, 148, 148))
            if is_grid:
                gray_count += 1
        if gray_count > (bottom - top) * 0.6:
            grid_cols.append(x)

    # Cluster adjacent columns into single gridlines
    gridlines = []
    if grid_cols:
        cluster = [grid_cols[0]]
        for x in grid_cols[1:]:
            if x - cluster[-1] <= 2:
                cluster.append(x)
            else:
                gridlines.append(sum(cluster) / len(cluster))
                cluster = [x]
        gridlines.append(sum(cluster) / len(cluster))

    print(f"  Found {len(gridlines)} gridlines")

    if len(gridlines) < 8:
        # Fallback: assume borders are 10Hz and ~39kHz
        print("  WARNING: Not enough gridlines, using fallback calibration")
        A = (right - left) / (math.log10(39000) - math.log10(10))
        B = left - A * math.log10(10)
        return A, B

    # Group gridlines into decades by finding large gaps
    # Within a decade, gridlines are at 2x,3x,...,9x (8 lines)
    # Between decades, there's a larger gap (from 9x to 20x of next decade)
    decade_groups = [[gridlines[0]]]
    for gl in gridlines[1:]:
        if gl - decade_groups[-1][-1] > 80:
            decade_groups.append([gl])
        else:
            decade_groups[-1].append(gl)

    # The first line of each group is at 2x of the decade start
    # Group 0: 20Hz, Group 1: 200Hz, Group 2: 2kHz, Group 3: 20kHz
    decade_freqs = [20, 200, 2000, 20000]

    # Use the first two complete decades for calibration
    if len(decade_groups) >= 2:
        x1 = decade_groups[0][0]
        f1 = decade_freqs[0]
        x2 = decade_groups[1][0]
        f2 = decade_freqs[1]
        A = (x2 - x1) / (math.log10(f2) - math.log10(f1))
        B = x1 - A * math.log10(f1)
    else:
        A = (right - left) / (math.log10(39000) - math.log10(10))
        B = left - A * math.log10(10)

    return A, B


def pixel_to_freq(x, A, B):
    return 10 ** ((x - B) / A)


def pixel_to_db(y, top, bottom):
    return DB_TOP - (y - top) * (DB_TOP - DB_BOTTOM) / (bottom - top)

# --- Data conversion ---

def pixels_to_data(points, A, B, top, bottom):
    """Convert (x_pixel, y_pixel) to (freq_hz, db) pairs."""
    data = []
    for x, y in points:
        freq = pixel_to_freq(x, A, B)
        db = pixel_to_db(y, top, bottom)
        data.append((round(freq, 2), round(db, 2)))
    return data


def filter_continuity(data, max_jump_db=4.0, window=5):
    """Remove points that deviate sharply from their local neighborhood.

    A real frequency response is smooth — sudden jumps indicate noise from
    watermark blends or misdetected pixels. We use a median filter to find
    the local trend, then reject points that deviate too far from it.
    """
    if len(data) < window * 2:
        return data

    freqs = np.array([d[0] for d in data])
    dbs = np.array([d[1] for d in data])

    # Compute local median for each point
    half = window // 2
    keep = []
    for i in range(len(dbs)):
        lo = max(0, i - half)
        hi = min(len(dbs), i + half + 1)
        local_median = np.median(dbs[lo:hi])
        if abs(dbs[i] - local_median) <= max_jump_db:
            keep.append(i)

    filtered = [(freqs[i], dbs[i]) for i in keep]
    removed = len(data) - len(filtered)
    if removed > 0:
        print(f"  Continuity filter: removed {removed} outlier points")
    return [(round(f, 2), round(d, 2)) for f, d in filtered]


def resample_log(data, num_points=256):
    """Resample onto a uniform log-frequency grid."""
    if len(data) < 2:
        return data
    freqs = np.array([d[0] for d in data])
    dbs = np.array([d[1] for d in data])
    grid = np.logspace(np.log10(freqs[0]), np.log10(freqs[-1]), num_points)
    grid_db = np.interp(grid, freqs, dbs)
    return [(round(f, 2), round(d, 2)) for f, d in zip(grid, grid_db)]


# --- Comparison plot ---

def make_comparison_plot(source_img_path, curves, out_path, mic_ids):
    """Generate side-by-side: original image (top) + all digitized curves (bottom)."""
    src = Image.open(source_img_path)

    fig, (ax_orig, ax_dig) = plt.subplots(2, 1, figsize=(12, 6),
                                           gridspec_kw={"height_ratios": [1, 1]})

    # Top: original image cropped to plot area only
    src_rgb = np.array(src.convert("RGB"))
    # Detect plot bounds from the image
    gray = np.mean(src_rgb, axis=2)
    h_img, w_img = gray.shape
    h_lines = [y for y in range(h_img) if np.sum(gray[y, :] < 40) > w_img * 0.6]
    v_lines = [x for x in range(w_img) if np.sum(gray[:, x] < 40) > h_img * 0.6]
    if len(h_lines) >= 2 and len(v_lines) >= 2:
        top_c = min(h_lines)
        bot_c = max(h_lines)
        left_c = min(v_lines)
        right_c = max(v_lines)
        cropped = src_rgb[top_c:bot_c, left_c:right_c]
    else:
        cropped = src_rgb
    ax_orig.imshow(cropped, aspect="auto")
    ax_orig.set_title("Original (RecordingHacks)", fontsize=11)
    ax_orig.set_xticks([])
    ax_orig.set_yticks([])

    # Bottom: all digitized curves
    base_colors = ["#ff0000", "#ff0000", "#ff0000"]  # pure red to match source
    line_styles = ["-", "--", ":", "-."]

    # Build key/label pairs based on what's in the data
    key_labels = []
    if "single" in curves:
        key_labels.append(("single", mic_ids[0]))
    else:
        if "first" in curves:
            key_labels.append(("first", mic_ids[0]))
        if "second" in curves and len(mic_ids) > 1:
            key_labels.append(("second", mic_ids[1]))

    for i, (key, label_prefix) in enumerate(key_labels):
        if key not in curves:
            continue
        info = curves[key]
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
            ax_dig.semilogx(freqs, dbs, color=base_colors[i % len(base_colors)],
                            linewidth=lw, linestyle=style, alpha=alpha, label=label)

    ax_dig.set_xlim(10, 40000)
    ax_dig.set_ylim(-20, 20)
    ax_dig.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax_dig.set_xlabel("Frequency (Hz)")
    ax_dig.set_ylabel("dB")
    ax_dig.set_title("Digitized", fontsize=11)
    ax_dig.legend(loc="upper left", fontsize=8)
    ax_dig.grid(True, which="both", alpha=0.3)
    ax_dig.set_xticks([10, 20, 100, 200, 1000, 2000, 10000, 20000])
    ax_dig.set_xticklabels(["10", "20", "100", "200", "1k", "2k", "10k", "20k"])

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Comparison plot: {out_path}")


# --- Single-mic graph support ---

def digitize_single(image_path):
    """Digitize a single-mic RecordingHacks graph (476x159, RGBA, red curve).

    These are simpler than comparison graphs: one red curve on white background,
    RGBA mode (not paletted), axis from ~10Hz to ~40kHz.

    Returns dict with same structure as digitize() for consistency.
    """
    print(f"\nAnalyzing single-mic graph: {image_path}")
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    print(f"  Image: {w}x{h}")
    px = img.load()

    # Find plot bounds from dark lines
    h_lines = []
    for y in range(h):
        dark = sum(1 for x in range(w) if px[x, y][0] < 50 and px[x, y][1] < 50 and px[x, y][2] < 50)
        if dark > w * 0.5:
            h_lines.append(y)
    v_lines = []
    for x in range(w):
        dark = sum(1 for y in range(h) if px[x, y][0] < 50 and px[x, y][1] < 50 and px[x, y][2] < 50)
        if dark > h * 0.3:
            v_lines.append(x)

    # Cluster
    def cluster(vals):
        if not vals:
            return []
        groups = [[vals[0]]]
        for v in vals[1:]:
            if v - groups[-1][-1] <= 2:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [int(sum(g) / len(g)) for g in groups]

    h_bounds = cluster(h_lines)
    v_bounds = cluster(v_lines)

    if len(h_bounds) < 2 or len(v_bounds) < 2:
        print("  ERROR: Could not detect plot bounds")
        return {}

    top, bottom = h_bounds[0], h_bounds[-1]
    left, right = v_bounds[0], v_bounds[-1]
    print(f"  Plot bounds: x=[{left}, {right}], y=[{top}, {bottom}]")

    # Calibrate X axis from internal gridlines (decade boundaries)
    # Single graphs have gridlines at 100Hz, 1kHz, 10kHz
    internal_v = [x for x in v_bounds if left < x < right]
    if len(internal_v) >= 2:
        # First two internal gridlines are typically 100Hz and 1kHz (or similar decades)
        # Use the spacing between them = 1 decade
        A = internal_v[1] - internal_v[0]  # pixels per decade
        B = internal_v[0] - A * math.log10(100)  # assuming first internal = 100Hz
        # Verify: third internal should be 10kHz
        if len(internal_v) >= 3:
            predicted_10k = A * math.log10(10000) + B
            if abs(predicted_10k - internal_v[2]) < 5:
                print(f"  Calibration verified: 100Hz, 1kHz, 10kHz gridlines match")
            else:
                print(f"  WARNING: 10kHz gridline off by {abs(predicted_10k - internal_v[2]):.0f}px")
    else:
        # Fallback: assume ~125px per decade based on standard 476px graphs
        A = 125.0
        B = left - A * math.log10(10)

    print(f"  Calibration: A={A:.1f}, B={B:.1f}")
    print(f"  Freq range: {pixel_to_freq(left, A, B):.0f}Hz - {pixel_to_freq(right, A, B):.0f}Hz")

    # Build red pixel mask — simple RGB threshold on RGBA image
    plot_h = bottom - top
    plot_w = right - left
    mask = np.zeros((plot_h, plot_w), dtype=bool)
    for c in range(plot_w):
        for r in range(plot_h):
            red, g, b, a = px[c + left, r + top]
            if red > 180 and g < 120 and b < 120:
                mask[r, c] = True

    total_red = int(np.sum(mask))
    print(f"  Red pixels: {total_red}")

    # Build per-column clusters and track (reuse existing tracker logic)
    col_centers = {}
    for c in range(plot_w):
        ys = [r + top for r in range(plot_h) if mask[r, c]]
        if ys:
            clusters = _cluster_ys(ys, gap=5)
            col_centers[c + left] = [sum(cl) / len(cl) for cl in clusters]

    x_values = sorted(col_centers.keys())
    if not x_values:
        print("  WARNING: No red curve pixels found")
        return {}

    max_clusters = max(len(col_centers[x]) for x in x_values)
    print(f"  Columns with data: {len(x_values)}, max simultaneous lines: {max_clusters}")

    # Multi-object tracking
    active = []
    MATCH_DIST = 10  # tighter for smaller images
    MAX_GAP = 8

    for x in x_values:
        centers = col_centers[x]
        candidates = []
        for ci, cy in enumerate(centers):
            for pi, (last_y, _, gap) in enumerate(active):
                if gap > MAX_GAP:
                    continue
                candidates.append((abs(cy - last_y), ci, pi))
        candidates.sort()

        matched_paths = set()
        matched_centers = set()
        for dist, ci, pi in candidates:
            if ci in matched_centers or pi in matched_paths:
                continue
            if dist <= MATCH_DIST:
                _, pts, _ = active[pi]
                pts.append((x, centers[ci]))
                active[pi] = (centers[ci], pts, 0)
                matched_paths.add(pi)
                matched_centers.add(ci)

        for ci, cy in enumerate(centers):
            if ci not in matched_centers:
                active.append((cy, [(x, cy)], 0))

        for pi in range(len(active)):
            if pi not in matched_paths:
                last_y, pts, gap = active[pi]
                active[pi] = (last_y, pts, gap + 1)

    # Filter paths
    min_span = plot_w * 0.20
    paths = []
    for _, pts, _ in active:
        if len(pts) < 10:
            continue
        span = pts[-1][0] - pts[0][0]
        if span >= min_span:
            paths.append(pts)

    # Deduplicate
    paths.sort(key=lambda p: -(p[-1][0] - p[0][0]))
    unique = []
    for path in paths:
        is_dup = False
        for existing in unique:
            ex_dict = dict(existing)
            diffs = []
            for x, y in path[::max(1, len(path) // 10)]:
                if x in ex_dict:
                    diffs.append(abs(y - ex_dict[x]))
            if len(diffs) >= 3 and sum(diffs) / len(diffs) < 3:
                is_dup = True
                break
        if not is_dup:
            unique.append(path)

    print(f"  Tracked {len(unique)} path(s)")

    # Complete fragment curves using the main (widest) curve.
    # Many mic charts show multiple response variants (proximity effect, bass
    # switches) that share the same high-frequency response but diverge in the
    # bass. The tracker follows each line through the split region, but when
    # lines merge back, secondary paths die. We splice the main curve's data
    # onto fragments to produce complete full-range curves.
    if len(unique) > 1:
        main = unique[0]  # widest span (sorted by -span earlier)
        main_dict = dict(main)
        main_x_min = main[0][0]
        main_x_max = main[-1][0]
        completed = [main]
        for frag in unique[1:]:
            frag_x_min = frag[0][0]
            frag_x_max = frag[-1][0]
            frag_span = frag_x_max - frag_x_min
            main_span = main_x_max - main_x_min
            if frag_span >= main_span * 0.8:
                # Already near-full range, keep as-is
                completed.append(frag)
                continue
            # Splice: use fragment data where it exists, main curve elsewhere
            frag_dict = dict(frag)
            merged = []
            for x, y in main:
                if frag_x_min <= x <= frag_x_max:
                    # Use fragment's value in its range
                    if x in frag_dict:
                        merged.append((x, frag_dict[x]))
                else:
                    # Outside fragment range, use main curve
                    merged.append((x, y))
            # Smooth the splice points (average over a few pixels at boundaries)
            completed.append(merged)
            print(f"  Completed fragment ({frag_span:.0f}px) → full range using main curve")
        unique = completed

    # Convert to freq/dB
    curves = []
    for i, raw_path in enumerate(unique):
        data = pixels_to_data(raw_path, A, B, top, bottom)
        data = filter_continuity(data)
        if data:
            freqs = [d[0] for d in data]
            dbs = [d[1] for d in data]
            print(f"  Curve {i}: {len(data)} pts, {min(freqs):.0f}-{max(freqs):.0f}Hz, {min(dbs):.1f} to {max(dbs):.1f}dB")
            curves.append(data)

    return {
        "single": {
            "raw_paths": len(unique),
            "curves": curves,
        }
    }


# --- Download ---

def download_single_graph(mic_id, save_path):
    """Download a single-mic RecordingHacks graph PNG."""
    url = f"https://recordinghacks.com/graphs2.php/{mic_id}"
    print(f"Downloading {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(resp.content)
    print(f"  Saved to {save_path} ({len(resp.content)} bytes)")




# --- Mask export ---

def _export_mask(image_path, mic_id, out_dir, mask_path=None):
    """Export the red curve pixels as a clean PNG for manual editing.

    Outputs a white image with red pixels only (no grid, no background, no text).
    The image is the same dimensions as the plot area. Calibration JSON is saved
    alongside for use by _digitize_mask.
    """
    slug = MIC_SLUGS.get(mic_id, mic_id)
    img = Image.open(image_path).convert("RGBA")
    px = img.load()
    w, h = img.size

    # Detect plot bounds (same logic as digitize_single)
    gray = img.convert("L")
    gpx = gray.load()
    h_lines, v_lines = [], []
    for y in range(h):
        dark = sum(1 for x in range(w) if gpx[x, y] < 40)
        if dark > w * 0.6:
            h_lines.append(y)
    for x in range(w):
        dark = sum(1 for y in range(h) if gpx[x, y] < 40)
        if dark > h * 0.6:
            v_lines.append(x)

    def cluster(vals):
        if not vals:
            return []
        groups = [[vals[0]]]
        for v in vals[1:]:
            if v - groups[-1][-1] <= 2:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [int(sum(g) / len(g)) for g in groups]

    h_bounds = cluster(h_lines)
    v_bounds = cluster(v_lines)
    top, bottom = h_bounds[0], h_bounds[-1]
    left, right = v_bounds[0], v_bounds[-1]
    plot_h = bottom - top
    plot_w = right - left

    # Build red pixel mask
    mask = np.zeros((plot_h, plot_w), dtype=bool)
    for c in range(plot_w):
        for r in range(plot_h):
            red, g, b, a = px[c + left, r + top]
            if red > 180 and g < 120 and b < 120:
                mask[r, c] = True

    # Create output image: white background, red curve pixels
    out = Image.new("RGB", (plot_w, plot_h), (255, 255, 255))
    out_px = out.load()
    for r in range(plot_h):
        for c in range(plot_w):
            if mask[r, c]:
                out_px[c, r] = (255, 0, 0)

    if mask_path is None:
        mask_path = out_dir / f"{slug}.png"
    out.save(mask_path)
    red_count = int(np.sum(mask))

    # Calibrate axes (same as digitize_single)
    internal_v = [x for x in v_bounds if left < x < right]
    if len(internal_v) >= 2:
        A = internal_v[1] - internal_v[0]
        B = internal_v[0] - A * math.log10(100)
    else:
        A = 125.0
        B = left - A * math.log10(10)

    # Save calibration alongside mask (one per mic, shared by all variants)
    cal_path = out_dir / f"{slug}.json"
    cal = {"A": A, "B": B, "left": left, "right": right, "top": top, "bottom": bottom}
    with open(cal_path, "w") as f:
        json.dump(cal, f, indent=2)

    print(f"  Mask: {mask_path.name} ({plot_w}x{plot_h}, {red_count} red pixels)")


def _digitize_mask(mask_path, mic_id, cal_dir):
    """Digitize a cleaned mask PNG using saved calibration.

    The mask is a white image with red pixels only — same dimensions as the
    original plot area. Calibration (A, B, bounds) comes from the JSON saved
    alongside the original mask export.
    """
    slug = MIC_SLUGS.get(mic_id, mic_id)
    cal_path = cal_dir / f"{slug}.json"
    if not cal_path.exists():
        print(f"ERROR: Calibration file not found: {cal_path}")
        print(f"  Run 'prepare' first to generate it.")
        sys.exit(1)

    with open(cal_path) as f:
        cal = json.load(f)
    A, B = cal["A"], cal["B"]
    left, right = cal["left"], cal["right"]
    top, bottom = cal["top"], cal["bottom"]

    img = Image.open(mask_path).convert("RGB")
    px = img.load()
    w, h = img.size
    print(f"\nDigitizing mask: {mask_path} ({w}x{h})")

    # The mask image IS the plot area — coordinates are relative to (0,0)
    # but calibration expects absolute pixel coords, so offset by left/top
    mask = np.zeros((h, w), dtype=bool)
    for r in range(h):
        for c in range(w):
            red, g, b = px[c, r]
            if red > 180 and g < 120 and b < 120:
                mask[r, c] = True

    total_red = int(np.sum(mask))
    print(f"  Red pixels: {total_red}")

    # Build per-column clusters (x coords offset to match original calibration)
    col_centers = {}
    for c in range(w):
        ys = [r + top for r in range(h) if mask[r, c]]
        if ys:
            clusters = _cluster_ys(ys, gap=5)
            col_centers[c + left] = [sum(cl) / len(cl) for cl in clusters]

    x_values = sorted(col_centers.keys())
    if not x_values:
        print("  WARNING: No red pixels found in mask")
        return {}

    # Multi-object tracking (same params as single mode)
    active = []
    MATCH_DIST = 10
    MAX_GAP = 8

    for x in x_values:
        centers = col_centers[x]
        candidates = []
        for ci, cy in enumerate(centers):
            for pi, (last_y, _, gap) in enumerate(active):
                if gap > MAX_GAP:
                    continue
                candidates.append((abs(cy - last_y), ci, pi))
        candidates.sort()

        matched_paths = set()
        matched_centers = set()
        for dist, ci, pi in candidates:
            if ci in matched_centers or pi in matched_paths:
                continue
            if dist <= MATCH_DIST:
                _, pts, _ = active[pi]
                pts.append((x, centers[ci]))
                active[pi] = (centers[ci], pts, 0)
                matched_paths.add(pi)
                matched_centers.add(ci)

        for ci, cy in enumerate(centers):
            if ci not in matched_centers:
                active.append((cy, [(x, cy)], 0))

        for pi in range(len(active)):
            if pi not in matched_paths:
                last_y, pts, gap = active[pi]
                active[pi] = (last_y, pts, gap + 1)

    # Filter paths
    plot_w = right - left
    min_span = plot_w * 0.20
    paths = []
    for _, pts, _ in active:
        if len(pts) < 10:
            continue
        span = pts[-1][0] - pts[0][0]
        if span >= min_span:
            paths.append(pts)

    # Deduplicate
    paths.sort(key=lambda p: -(p[-1][0] - p[0][0]))
    unique = []
    for path in paths:
        is_dup = False
        for existing in unique:
            ex_dict = dict(existing)
            diffs = []
            for x, y in path[::max(1, len(path) // 10)]:
                if x in ex_dict:
                    diffs.append(abs(y - ex_dict[x]))
            if len(diffs) >= 3 and sum(diffs) / len(diffs) < 3:
                is_dup = True
                break
        if not is_dup:
            unique.append(path)

    print(f"  Tracked {len(unique)} path(s)")

    # Convert to freq/dB
    curves = []
    for i, raw_path in enumerate(unique):
        data = pixels_to_data(raw_path, A, B, top, bottom)
        data = filter_continuity(data)
        if data:
            freqs = [d[0] for d in data]
            dbs = [d[1] for d in data]
            print(f"  Curve {i}: {len(data)} pts, {min(freqs):.0f}-{max(freqs):.0f}Hz, "
                  f"{min(dbs):.1f} to {max(dbs):.1f}dB")
            curves.append(data)

    return {
        "single": {
            "raw_paths": len(unique),
            "curves": curves,
        }
    }


# --- Main pipeline ---


def _results_to_curve_list(results, key="single"):
    """Convert extraction results to JSON curve list."""
    if key not in results:
        return []
    curve_list = []
    for i, data in enumerate(results[key]["curves"]):
        curve_list.append({
            "index": i,
            "points": len(data),
            "data": [{"hz": hz, "db": db} for hz, db in data],
        })
    return curve_list


def cmd_prepare(args):
    """Download source images, export masks, report status.

    For each mic in the registry:
      1. Download source PNG if not cached in data/curves/sources/
      2. Export red pixel mask to data/curves/masks/ (if not already there)
      3. Report status: hand-edited variants exist, or base mask only
    """
    repo = Path(__file__).resolve().parent.parent.parent
    source_dir = repo / "data" / "curves" / "sources"
    mask_dir = repo / "data" / "curves" / "masks"
    source_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    summary = []

    for mic_id, slug in sorted(MIC_SLUGS.items(), key=lambda x: x[1]):
        name = RH_MIC_NAMES[mic_id]
        source_path = source_dir / f"{slug}.png"

        # Download if not cached
        if not source_path.exists():
            print(f"\n--- {name} ({slug}) ---")
            download_single_graph(mic_id, source_path)
        else:
            print(f"\n--- {name} ({slug}) --- [cached]")

        # Check if hand-edited masks already exist
        edited_masks = sorted(mask_dir.glob(f"{slug}_*.png"))
        if edited_masks:
            names = [p.name for p in edited_masks]
            print(f"  Hand-edited masks: {len(names)} ({', '.join(names)})")
            summary.append((slug, name, "edited", names))
        else:
            # Export base mask if missing
            mask_path = mask_dir / f"{slug}.png"
            if not mask_path.exists():
                _export_mask(source_path, mic_id, mask_dir, mask_path)
            else:
                print(f"  Base mask: {mask_path.name} [exists]")
            summary.append((slug, name, "base_only", []))

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    base_only = []
    for slug, name, status, masks in summary:
        if status == "edited":
            print(f"  {name:<25} {slug:<15} ✓ {len(masks)} variant(s)")
        else:
            print(f"  {name:<25} {slug:<15}   base mask only")
            base_only.append(slug)

    if base_only:
        print(f"\n{len(base_only)} mic(s) have only a base mask (no hand-edited variants):")
        print(f"  {', '.join(base_only)}")
        print(f"\nIf any of these have multiple response curves (proximity, switches, etc.):")
        print(f"  1. Open the mask in data/curves/masks/{{slug}}.png")
        print(f"  2. Make copies — erase unwanted lines in each")
        print(f"  3. Save as {{slug}}_1.png, {{slug}}_2.png, etc.")
        print(f"\nThen run: python3 tools/curves/digitize.py build")


def cmd_build(args):
    """Digitize all masks and write JSONs.

    For each mic:
      - If hand-edited masks exist ({slug}_1.png, etc.), digitize each as a
        separate curve variant
      - If only the base mask exists, digitize it directly from the source image
      - Write results to data/curves/digitized/{slug}.json
    """
    repo = Path(__file__).resolve().parent.parent.parent
    source_dir = repo / "data" / "curves" / "sources"
    mask_dir = repo / "data" / "curves" / "masks"
    out_dir = repo / "data" / "curves" / "digitized"
    tmp_dir = Path("/tmp/poser")
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for mic_id, slug in sorted(MIC_SLUGS.items(), key=lambda x: x[1]):
        name = RH_MIC_NAMES[mic_id]
        source_path = source_dir / f"{slug}.png"
        print(f"\n--- {name} ({slug}) ---")

        if not source_path.exists():
            print(f"  SKIP: no source image (run 'prepare' first)")
            continue

        # Check for hand-edited masks
        edited_masks = sorted(mask_dir.glob(f"{slug}_*.png"))

        if edited_masks:
            # Digitize each edited mask as a separate curve
            all_curves = []
            for mask_path in edited_masks:
                print(f"  Mask: {mask_path.name}")
                results = _digitize_mask(mask_path, mic_id, mask_dir)
                curves = _results_to_curve_list(results)
                if curves:
                    # Use the first (should be only) curve from each mask
                    all_curves.append(curves[0])

            if all_curves:
                # Re-index
                for i, c in enumerate(all_curves):
                    c["index"] = i

                output = {
                    "source": f"https://recordinghacks.com/graphs2.php/{mic_id}",
                    "mic_id": mic_id,
                    "mic_name": name,
                    "slug": slug,
                    "mode": "single",
                    "hand_edited": True,
                    "curves": {
                        "single": {
                            "num_curves": len(all_curves),
                            "curves": all_curves,
                        }
                    },
                }
            else:
                print(f"  WARNING: no curves extracted from edited masks")
                continue
        else:
            # No edited masks — digitize source image directly
            results = digitize_single(source_path)
            curve_list = _results_to_curve_list(results)

            output = {
                "source": f"https://recordinghacks.com/graphs2.php/{mic_id}",
                "mic_id": mic_id,
                "mic_name": name,
                "slug": slug,
                "mode": "single",
                "hand_edited": False,
                "curves": {},
            }
            if curve_list:
                output["curves"]["single"] = {
                    "num_curves": len(curve_list),
                    "curves": curve_list,
                }

        json_path = out_dir / f"{slug}.json"
        with open(json_path, "w") as f:
            json.dump(output, f, indent=2)

        n = output.get("curves", {}).get("single", {}).get("num_curves", 0)
        edited = " (hand-edited)" if output.get("hand_edited") else ""
        print(f"  Wrote {json_path}: {n} curve(s){edited}")

        for c in output.get("curves", {}).get("single", {}).get("curves", []):
            pts = c["data"]
            if pts:
                freqs = [p["hz"] for p in pts]
                dbs = [p["db"] for p in pts]
                print(f"    [{c['index']}] {c['points']} pts, "
                      f"{min(freqs):.0f}-{max(freqs):.0f}Hz, "
                      f"{min(dbs):.1f} to {max(dbs):.1f} dB")

        # Comparison plot
        plot_path = tmp_dir / f"{slug}_comparison.png"
        make_comparison_plot(source_path, output["curves"], plot_path, [mic_id])

    print(f"\nDone. JSONs in {out_dir}/")
    print(f"Plots in {tmp_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Digitize RecordingHacks frequency response curves",
        epilog="Workflow: run 'prepare' → edit masks if needed → run 'build'",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("prepare",
                    help="Download sources, export masks, report which need editing")
    sub.add_parser("build",
                    help="Digitize all masks → JSON curves")

    # Legacy single-mic mode (for one-off use)
    parser.add_argument("--single", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--mask", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--from-mask", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--image", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("id1", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("id2", nargs="?", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command is None:
        parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
