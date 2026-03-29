#!/usr/bin/env python3
"""Curve extraction engine — image analysis, mask export, curve digitization.

Internal module used by manage.py. Not meant to be run directly.
"""

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import requests
from PIL import Image

import paths
from registry import MICS


# --- Constants ---

DB_TOP = 20.0
DB_BOTTOM = -20.0


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

def _cluster_ys(ys, gap=8):
    """Cluster y values into groups separated by gaps.

    Returns list of clusters, each a list of y values.
    A gap of 8px (~2.5dB) separates distinct lines.
    """
    if not ys:
        return []
    ys_sorted = sorted(ys)
    clusters = [[ys_sorted[0]]]
    for y in ys_sorted[1:]:
        if y - clusters[-1][-1] <= gap:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    return clusters


# --- Shared path tracking ---

def _track_paths(col_centers, plot_w, match_dist=10, max_gap=8, min_span_frac=0.20):
    """Multi-object tracker: follow curve lines across columns.

    col_centers: dict {x_pixel: [list of y-center values]}
    plot_w: plot width in pixels (for min span filtering)

    Returns list of paths, each a list of (x, y) tuples, sorted by span descending.
    """
    x_values = sorted(col_centers.keys())
    if not x_values:
        return []

    active = []
    for x in x_values:
        centers = col_centers[x]
        candidates = []
        for ci, cy in enumerate(centers):
            for pi, (last_y, _, gap) in enumerate(active):
                if gap > max_gap:
                    continue
                candidates.append((abs(cy - last_y), ci, pi))
        candidates.sort()

        matched_paths = set()
        matched_centers = set()
        for dist, ci, pi in candidates:
            if ci in matched_centers or pi in matched_paths:
                continue
            if dist <= match_dist:
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

    # Filter paths by minimum span and point count
    min_span = plot_w * min_span_frac
    paths = []
    for _, pts, _ in active:
        if len(pts) < 10:
            continue
        span = pts[-1][0] - pts[0][0]
        if span >= min_span:
            paths.append(pts)

    # Sort by span descending (widest first)
    paths.sort(key=lambda p: -(p[-1][0] - p[0][0]))
    return paths


def _deduplicate_paths(paths):
    """Remove near-duplicate paths (avg y-diff < 3px at sampled points)."""
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
    return unique


def _stitch_fragments(paths, max_gap_px=80, max_y_diff=10):
    """Merge path fragments that are clearly part of the same line.

    Hand-drawn masks often have gaps (dashed source lines, imperfect tracing).
    The tracker produces many short fragments. This stitches consecutive
    fragments when the Y positions at the join are close enough.

    max_gap_px:  max X gap between end of one fragment and start of next
    max_y_diff:  max Y difference at the join point (pixels)
    """
    if len(paths) <= 1:
        return paths

    # Sort fragments by start X
    frags = sorted(paths, key=lambda p: p[0][0])

    merged = [list(frags[0])]
    for frag in frags[1:]:
        prev = merged[-1]
        prev_end_x, prev_end_y = prev[-1]
        frag_start_x, frag_start_y = frag[0]

        gap = frag_start_x - prev_end_x
        y_diff = abs(frag_start_y - prev_end_y)

        if 0 < gap <= max_gap_px and y_diff <= max_y_diff:
            # Stitch: linearly interpolate across the gap
            if gap > 1:
                for x in range(int(prev_end_x) + 1, int(frag_start_x)):
                    t = (x - prev_end_x) / gap
                    y = prev_end_y + t * (frag_start_y - prev_end_y)
                    prev.append((x, y))
            prev.extend(frag)
        else:
            merged.append(list(frag))

    stitched = len(frags) - len(merged)
    if stitched > 0:
        print(f"  Stitched {len(frags)} fragments → {len(merged)} path(s)")

    # Re-sort by span descending
    merged.sort(key=lambda p: -(p[-1][0] - p[0][0]))
    return merged


def _complete_fragments(paths):
    """Splice fragment curves onto the main (widest) curve.

    Many mic charts show multiple response variants (proximity effect, bass
    switches) that share the same high-frequency response but diverge in the
    bass. The tracker follows each line through the split region, but when
    lines merge back, secondary paths die. We splice the main curve's data
    onto fragments to produce complete full-range curves.
    """
    if len(paths) <= 1:
        return paths

    main = paths[0]  # widest span (sorted by -span earlier)
    main_dict = dict(main)
    main_x_min = main[0][0]
    main_x_max = main[-1][0]
    main_span = main_x_max - main_x_min
    completed = [main]

    for frag in paths[1:]:
        frag_x_min = frag[0][0]
        frag_x_max = frag[-1][0]
        frag_span = frag_x_max - frag_x_min
        if frag_span >= main_span * 0.8:
            # Already near-full range, keep as-is
            completed.append(frag)
            continue
        # Splice: use fragment data where it exists, main curve elsewhere
        frag_dict = dict(frag)
        merged = []
        for x, y in main:
            if frag_x_min <= x <= frag_x_max:
                if x in frag_dict:
                    merged.append((x, frag_dict[x]))
            else:
                merged.append((x, y))
        completed.append(merged)
        print(f"  Completed fragment ({frag_span:.0f}px) → full range using main curve")

    return completed


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


def resample_log(data, num_points=256, smooth=True):
    """Resample onto a uniform log-frequency grid, with optional smoothing.

    Smoothing removes pixel-level stairstepping from mask digitization
    without losing real curve features. Uses a gentle moving average.
    """
    if len(data) < 2:
        return data
    freqs = np.array([d[0] for d in data])
    dbs = np.array([d[1] for d in data])
    grid = np.logspace(np.log10(freqs[0]), np.log10(freqs[-1]), num_points)
    grid_db = np.interp(grid, freqs, dbs)

    if smooth and num_points >= 20:
        # Gentle smoothing: 5-point moving average, applied twice.
        # Preserves shape but removes quantization staircase.
        kernel = np.ones(5) / 5
        for _ in range(2):
            padded = np.pad(grid_db, 2, mode='edge')
            grid_db = np.convolve(padded, kernel, mode='valid')[:num_points]

    return [(round(f, 2), round(d, 2)) for f, d in zip(grid, grid_db)]


# --- Comparison plot ---

def make_comparison_plot(source_img_path, curves, out_path, mic_ids, plot_crop=None):
    """Generate side-by-side: original image (top) + all digitized curves (bottom).

    plot_crop: optional [left, top, right, bottom] pixel coords to crop source image.
               If None, auto-detects plot bounds from dark border lines.
    """
    src = Image.open(source_img_path)

    fig, (ax_orig, ax_dig) = plt.subplots(2, 1, figsize=(12, 6),
                                           gridspec_kw={"height_ratios": [1, 1]})

    # Top: original image cropped to plot area
    src_rgb = np.array(src.convert("RGB"))
    if plot_crop:
        left_c, top_c, right_c, bot_c = plot_crop
        cropped = src_rgb[top_c:bot_c, left_c:right_c]
    else:
        # Auto-detect from dark border lines
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
    is_datasheet = plot_crop is not None
    ax_orig.imshow(cropped, aspect="auto")
    ax_orig.set_title("Original (Datasheet)" if is_datasheet else "Original (RecordingHacks)",
                      fontsize=11)
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

    paths = _track_paths(col_centers, plot_w)
    unique = _deduplicate_paths(paths)
    print(f"  Tracked {len(unique)} path(s)")
    unique = _complete_fragments(unique)

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

def _export_mask(image_path, slug, out_dir, mask_path=None):
    """Export the red curve pixels as a clean PNG for manual editing.

    Outputs a white image with red pixels only (no grid, no background, no text).
    The image is the same dimensions as the plot area. Calibration JSON is saved
    alongside for use by _digitize_mask.
    """
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


def _digitize_mask(mask_path, slug, cal_dir):
    """Digitize a cleaned mask PNG using saved calibration.

    One mask = one curve. Finds the median red pixel Y per column, fits a
    smooth spline through them (rejecting outliers), and outputs a clean curve.
    Handles dashed lines, gaps, and stray pixels gracefully.

    Supports two calibration formats:
      - RH-style: {A, B, left, right, top, bottom}
      - Datasheet-style: {plot_bounds, freq_range, db_range, source: "datasheet"}
    """
    from scipy.interpolate import UnivariateSpline

    cal_path = cal_dir / f"{slug}.json"
    if not cal_path.exists():
        print(f"ERROR: Calibration file not found: {cal_path}")
        print(f"  Run 'prepare' first to generate it.")
        raise SystemExit(1)

    with open(cal_path) as f:
        cal = json.load(f)

    # Detect calibration format
    is_datasheet = cal.get("source") == "datasheet"

    if is_datasheet:
        left, top, right, bottom = cal["plot_bounds"]
        freq_lo, freq_hi = cal["freq_range"]
        cal_db_top, cal_db_bottom = cal["db_range"]
    else:
        A, B = cal["A"], cal["B"]
        left, right = cal["left"], cal["right"]
        top, bottom = cal["top"], cal["bottom"]

    img = Image.open(mask_path).convert("RGB")
    px = img.load()
    w, h = img.size
    print(f"\nDigitizing mask: {mask_path} ({w}x{h})")

    # Find red pixels
    mask = np.zeros((h, w), dtype=bool)
    for r in range(h):
        for c in range(w):
            red, g, b = px[c, r]
            if red > 180 and g < 120 and b < 120:
                mask[r, c] = True

    total_red = int(np.sum(mask))
    print(f"  Red pixels: {total_red}")

    # One median Y per column — simple, no clustering needed
    xs = []
    ys = []
    for c in range(w):
        col_ys = np.where(mask[:, c])[0]
        if len(col_ys) > 0:
            xs.append(c)
            ys.append(np.median(col_ys))

    if not xs:
        print("  WARNING: No red pixels found in mask")
        return {}

    xs = np.array(xs, dtype=float)
    ys = np.array(ys, dtype=float)

    # Remove isolated clumps — find gaps > 50px and drop any clump with
    # fewer than 20 columns (stray marks, not real curve data)
    gaps = np.diff(xs)
    split_indices = np.where(gaps > 50)[0] + 1
    clumps = np.split(np.arange(len(xs)), split_indices)
    keep_mask = np.zeros(len(xs), dtype=bool)
    for clump in clumps:
        if len(clump) >= 20:
            keep_mask[clump] = True
    n_removed = int(np.sum(~keep_mask))
    if n_removed > 0:
        print(f"  Removed {n_removed} isolated pixel(s)")
        xs = xs[keep_mask]
        ys = ys[keep_mask]

    print(f"  Columns with data: {len(xs)} of {w}")

    # Pass 1: rough spline to identify outliers
    # s = smoothing factor — larger = smoother. Scale by number of points.
    s_factor = len(xs) * 2.0
    spline = UnivariateSpline(xs, ys, s=s_factor, k=3)
    fitted = spline(xs)
    residuals = np.abs(ys - fitted)

    # Reject points > 3 * median absolute deviation from the spline
    mad = np.median(residuals)
    threshold = max(mad * 4.0, 3.0)  # at least 3px tolerance
    keep = residuals <= threshold
    n_rejected = int(np.sum(~keep))
    if n_rejected > 0:
        print(f"  Outlier rejection: removed {n_rejected} points (threshold: {threshold:.1f}px)")
    xs_clean = xs[keep]
    ys_clean = ys[keep]

    # Pass 2: final spline on clean data
    s_final = len(xs_clean) * 1.0
    spline_final = UnivariateSpline(xs_clean, ys_clean, s=s_final, k=3)

    # Evaluate on a uniform grid spanning the data range
    n_out = min(512, int(xs_clean[-1] - xs_clean[0]))
    x_out = np.linspace(xs_clean[0], xs_clean[-1], n_out)
    y_out = spline_final(x_out)

    # Convert pixel coords to freq/dB
    # x_out is in mask-relative coords (0..w), offset by left for calibration
    data = []
    for x_px, y_px in zip(x_out, y_out):
        x_abs = x_px + left
        y_abs = y_px + top
        if is_datasheet:
            freq = _pixel_to_freq_ds(x_abs, left, right, freq_lo, freq_hi)
            db = _pixel_to_db_ds(y_abs, top, bottom, cal_db_top, cal_db_bottom)
        else:
            freq = pixel_to_freq(x_abs, A, B)
            db = pixel_to_db(y_abs, top, bottom)
        if freq > 0:
            data.append((round(freq, 2), round(db, 2)))

    if data:
        freqs = [d[0] for d in data]
        dbs = [d[1] for d in data]
        print(f"  Curve: {len(data)} pts, {min(freqs):.0f}-{max(freqs):.0f}Hz, "
              f"{min(dbs):.1f} to {max(dbs):.1f}dB")

    return {
        "single": {
            "raw_paths": 1,
            "curves": [data] if data else [],
        }
    }


# --- Datasheet digitization ---

COLOR_PRESETS = {
    "black": lambda r, g, b: r < 80 and g < 80 and b < 80,
    "blue":  lambda r, g, b: b > 100 and b - r > 20 and b - g > 20,
    "red":   lambda r, g, b: r > 100 and r - g > 20 and r - b > 20,
}


def _pixel_to_freq_ds(x, left, right, freq_lo, freq_hi):
    """Log-frequency mapping from pixel x using config bounds."""
    t = (x - left) / (right - left)
    return freq_lo * (freq_hi / freq_lo) ** t


def _pixel_to_db_ds(y, top, bottom, db_top, db_bottom):
    """Linear dB mapping from pixel y using config bounds."""
    t = (y - top) / (bottom - top)
    return db_top + t * (db_bottom - db_top)


def _classify_line_style(path):
    """Classify a tracked path as solid or dashed by gap density.

    Returns gap_ratio: solid < 0.1, dashed > 0.2.
    """
    if len(path) < 2:
        return 0.0
    xs = [p[0] for p in path]
    total_span = xs[-1] - xs[0]
    if total_span == 0:
        return 0.0
    # Count columns where the path has no point
    x_set = set(xs)
    gaps = sum(1 for x in range(xs[0], xs[-1] + 1) if x not in x_set)
    return gaps / total_span


def digitize_datasheet(slug, ds_config, datasheets_dir):
    """Digitize a manufacturer datasheet PNG using explicit config.

    ds_config fields:
        color:       "black" | "blue" | "red"
        plot_bounds: [left, top, right, bottom] pixel coords
        freq_range:  [freq_lo_hz, freq_hi_hz]
        db_range:    [db_top, db_bottom]
        curves:      optional list of {label, line_style} for multi-curve
        min_thickness: optional int, min cluster height to keep (default 2 for black)

    Returns dict with same structure as digitize_single().
    """
    ds_path = datasheets_dir / f"{slug}.png"
    print(f"\nDigitizing datasheet: {ds_path}")

    img = Image.open(ds_path).convert("RGB")
    w, h = img.size
    px = img.load()

    left, top, right, bottom = ds_config["plot_bounds"]
    freq_lo, freq_hi = ds_config["freq_range"]
    db_top, db_bottom = ds_config["db_range"]
    color_name = ds_config["color"]
    print(f"  Image: {w}x{h}, plot: [{left},{top}]-[{right},{bottom}]")
    print(f"  Axes: {freq_lo}-{freq_hi}Hz, {db_top} to {db_bottom}dB")

    # Color test function
    if isinstance(color_name, dict):
        r_lo, r_hi = color_name["r"]
        g_lo, g_hi = color_name["g"]
        b_lo, b_hi = color_name["b"]
        is_curve = lambda r, g, b: r_lo <= r <= r_hi and g_lo <= g <= g_hi and b_lo <= b <= b_hi
    else:
        is_curve = COLOR_PRESETS[color_name]

    # For black curves on black grids, require minimum cluster thickness
    min_thickness = ds_config.get("min_thickness", 2 if color_name == "black" else 1)

    plot_w = right - left
    plot_h = bottom - top

    # Build pixel mask
    mask = np.zeros((plot_h, plot_w), dtype=bool)
    for r in range(plot_h):
        for c in range(plot_w):
            red_v, g_v, b_v = px[c + left, r + top]
            if is_curve(red_v, g_v, b_v):
                mask[r, c] = True

    total_px = int(np.sum(mask))
    print(f"  Color-matched pixels: {total_px}")

    # For black curves: surgically erase gridline pixels from the mask.
    # Strategy: detect continuous horizontal/vertical runs that span a large
    # fraction of the plot — these are gridlines. Erase those runs. The curve
    # pixels at gridline intersections get erased too, but the tracker bridges
    # the small gaps (MAX_GAP=8 handles 1-3px gridline thickness easily).
    if color_name == "black":
        # Horizontal gridlines: find rows where a single continuous run of
        # black pixels spans > 60% of plot width
        h_run_threshold = plot_w * 0.6
        grid_rows = set()
        for r in range(plot_h):
            # Find longest continuous run in this row
            run_len = 0
            max_run = 0
            for c in range(plot_w):
                if mask[r, c]:
                    run_len += 1
                    max_run = max(max_run, run_len)
                else:
                    run_len = 0
            if max_run > h_run_threshold:
                grid_rows.add(r)

        # Vertical gridlines: columns where a single continuous run spans > 60% of height
        v_run_threshold = plot_h * 0.6
        grid_cols = set()
        for c in range(plot_w):
            run_len = 0
            max_run = 0
            for r in range(plot_h):
                if mask[r, c]:
                    run_len += 1
                    max_run = max(max_run, run_len)
                else:
                    run_len = 0
            if max_run > v_run_threshold:
                grid_cols.add(c)

        # Erase gridline pixels
        erased = 0
        for r in grid_rows:
            erased += int(np.sum(mask[r, :]))
            mask[r, :] = False
        for c in grid_cols:
            erased += int(np.sum(mask[:, c]))
            mask[:, c] = False

        if grid_rows or grid_cols:
            print(f"  Erased {len(grid_rows)} grid rows, {len(grid_cols)} grid cols "
                  f"({erased} pixels)")

    # Build per-column cluster centers
    col_centers = {}
    for c in range(plot_w):
        ys = [r + top for r in range(plot_h) if mask[r, c]]
        if ys:
            clusters = _cluster_ys(ys, gap=5)
            thick = [cl for cl in clusters if len(cl) >= min_thickness]
            if thick:
                col_centers[c + left] = [sum(cl) / len(cl) for cl in thick]

    if not col_centers:
        print("  WARNING: No curve pixels found")
        return {}

    x_values = sorted(col_centers.keys())
    max_clusters = max(len(col_centers[x]) for x in x_values)
    print(f"  Columns with data: {len(x_values)}, max simultaneous lines: {max_clusters}")

    # Track, deduplicate, stitch gaps, complete fragments
    paths = _track_paths(col_centers, plot_w)
    unique = _deduplicate_paths(paths)
    unique = _stitch_fragments(unique)
    print(f"  Tracked {len(unique)} path(s)")

    # Filter out gridlines: real curves have significant dB variation,
    # horizontal gridlines are nearly flat. Convert to dB first, then filter.
    min_db_range = ds_config.get("min_db_range", 2.0)
    non_flat = []
    for path in unique:
        ys = [_pixel_to_db_ds(y, top, bottom, db_top, db_bottom) for _, y in path]
        db_range = max(ys) - min(ys)
        if db_range >= min_db_range:
            non_flat.append(path)
        else:
            print(f"  Filtered gridline ({db_range:.1f}dB range)")
    if non_flat:
        unique = non_flat
        print(f"  After gridline filter: {len(unique)} path(s)")

    unique = _complete_fragments(unique)

    # Solid/dashed classification
    curve_configs = ds_config.get("curves")
    if curve_configs and len(unique) > 1:
        # Classify each path
        styles = [(i, _classify_line_style(p)) for i, p in enumerate(unique)]
        solid = sorted([(i, gr) for i, gr in styles if gr < 0.15], key=lambda x: x[1])
        dashed = sorted([(i, gr) for i, gr in styles if gr >= 0.15], key=lambda x: x[1])

        # Reorder to match config: solid first, then dashed
        ordered = []
        solid_idx = 0
        dashed_idx = 0
        for cc in curve_configs:
            style = cc.get("line_style", "solid")
            if style == "solid" and solid_idx < len(solid):
                ordered.append(unique[solid[solid_idx][0]])
                solid_idx += 1
            elif style == "dashed" and dashed_idx < len(dashed):
                ordered.append(unique[dashed[dashed_idx][0]])
                dashed_idx += 1
            elif unique:
                # Fallback: take next available
                ordered.append(unique[0])
                unique = unique[1:]
        unique = ordered

    # Convert to freq/dB using config-driven mapping
    curves = []
    for i, raw_path in enumerate(unique):
        data = []
        for x, y in raw_path:
            freq = _pixel_to_freq_ds(x, left, right, freq_lo, freq_hi)
            db = _pixel_to_db_ds(y, top, bottom, db_top, db_bottom)
            data.append((round(freq, 2), round(db, 2)))
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


# --- Guide-assisted digitization ---


def digitize_guided(slug, ds_config, guide_data, datasheets_dir, corridor_db=4.0):
    """Digitize a datasheet using a human-traced guide.

    Strategy depends on curve color:
    - Black curves: use the guide trace directly (pixel refinement is unreliable
      when curve and grid are the same color — human eyes beat pixel matching).
    - Colored curves (blue, red): use guide as a corridor to find actual curve
      pixels, since color separation from the grid is clean.

    The guide trace alone is typically within ~1dB of lab measurements, which
    is within the variance between mic specimens anyway.
    """
    ds_path = datasheets_dir / f"{slug}.png"
    print(f"\nDigitizing (guided): {ds_path}")

    # Guide JSON may override axis config (user-confirmed values take priority)
    left, top, right, bottom = guide_data.get("plot_bounds", ds_config["plot_bounds"])
    freq_lo, freq_hi = guide_data.get("freq_range", ds_config["freq_range"])
    db_top, db_bottom = guide_data.get("db_range", ds_config["db_range"])
    color_name = guide_data.get("color", ds_config["color"])
    plot_w = right - left
    plot_h = bottom - top

    use_pixels = color_name not in ("black",)
    if use_pixels:
        print(f"  Color '{color_name}' — using pixel refinement within ±{corridor_db}dB corridor")
        img = Image.open(ds_path).convert("RGB")
        px = img.load()
        db_range = abs(db_top - db_bottom)
        corridor_px = int(corridor_db / db_range * plot_h)

        if isinstance(color_name, dict):
            r_lo, r_hi = color_name["r"]
            g_lo, g_hi = color_name["g"]
            b_lo, b_hi = color_name["b"]
            is_curve = lambda r, g, b: r_lo <= r <= r_hi and g_lo <= g <= g_hi and b_lo <= b <= b_hi
        else:
            is_curve = COLOR_PRESETS[color_name]
    else:
        print(f"  Color '{color_name}' — using guide trace directly (no pixel refinement)")

    all_curves = []

    for gi, guide_curve in enumerate(guide_data["curves"]):
        guide_pts = guide_curve["points"]  # [[hz, db], ...]
        label = guide_curve.get("label", f"curve_{gi}")
        print(f"  Guide curve {gi} ({label}): {len(guide_pts)} guide points")

        # Guide points are already in freq/dB — just resample
        g_freqs = [p[0] for p in guide_pts]
        g_dbs = [p[1] for p in guide_pts]

        if not use_pixels:
            # Black curve: guide trace IS the data. Just resample.
            data = [(round(f, 2), round(d, 2)) for f, d in zip(g_freqs, g_dbs)]
            data = resample_log(data, num_points=256)

        else:
            # Colored curve: refine guide with pixel data from corridor search.
            # Convert guide to pixel coords for corridor search
            guide_px_x = []
            guide_px_y = []
            for hz, db in guide_pts:
                t_x = math.log10(hz / freq_lo) / math.log10(freq_hi / freq_lo)
                guide_px_x.append(left + t_x * plot_w)
                t_y = (db - db_top) / (db_bottom - db_top)
                guide_px_y.append(top + t_y * plot_h)

            guide_px_x = np.array(guide_px_x)
            guide_px_y = np.array(guide_px_y)
            col_start = max(left, int(guide_px_x[0]))
            col_end = min(right, int(guide_px_x[-1]) + 1)
            all_cols = np.arange(col_start, col_end)
            guide_interp = np.interp(all_cols, guide_px_x, guide_px_y)

            result_ys = np.copy(guide_interp)
            pixel_count = 0

            for idx, (col, expected_y) in enumerate(zip(all_cols, guide_interp)):
                y_lo = max(top, int(expected_y - corridor_px))
                y_hi = min(bottom, int(expected_y + corridor_px))

                matched_ys = []
                for y in range(y_lo, y_hi):
                    r, g, b = px[int(col), y]
                    if is_curve(r, g, b):
                        matched_ys.append(y)

                if matched_ys:
                    clusters = _cluster_ys(matched_ys, gap=3)
                    best = min(clusters, key=lambda cl: abs(np.mean(cl) - expected_y))
                    result_ys[idx] = np.mean(best)
                    pixel_count += 1

            print(f"    Pixel hits: {pixel_count}/{len(all_cols)} "
                  f"({pixel_count/len(all_cols)*100:.0f}%)")

            data = []
            for col, y in zip(all_cols, result_ys):
                freq = _pixel_to_freq_ds(col, left, right, freq_lo, freq_hi)
                db = _pixel_to_db_ds(y, top, bottom, db_top, db_bottom)
                data.append((round(freq, 2), round(db, 2)))
            data = resample_log(data, num_points=256)

        if data:
            freqs = [d[0] for d in data]
            dbs = [d[1] for d in data]
            print(f"    Result: {len(data)} pts, {min(freqs):.0f}-{max(freqs):.0f}Hz, "
                  f"{min(dbs):.1f} to {max(dbs):.1f}dB")
            all_curves.append(data)

    return {
        "single": {
            "raw_paths": len(all_curves),
            "curves": all_curves,
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
      1. If datasheet config exists, verify PNG is present
      2. If rh_id exists, download source PNG if not cached
      3. Export red pixel mask to recordinghacks/masks/ (if not already there)
      4. Report status
    """
    paths.RH_ORIGINALS.mkdir(parents=True, exist_ok=True)
    paths.RH_MASKS.mkdir(parents=True, exist_ok=True)

    summary = []

    for slug in sorted(MICS):
        info = MICS[slug]
        name = info["name"]
        ds = info.get("datasheet")
        rh_id = info.get("rh_id")

        # Datasheet source
        if ds:
            ds_path = paths.datasheet_original(slug)
            if ds_path.exists():
                print(f"\n--- {name} ({slug}) --- [datasheet: {ds_path.name}]")
                summary.append((slug, name, "datasheet", []))
                continue
            else:
                print(f"\n--- {name} ({slug}) ---")
                print(f"  WARNING: datasheet not found: {ds_path}")
                summary.append((slug, name, "datasheet_missing", []))
                # Fall through to RH if available

        # RH source (fallback or primary if no datasheet)
        if not rh_id:
            if not ds:
                print(f"\n--- {name} ({slug}) ---")
                print(f"  SKIP: no datasheet config and no rh_id")
                summary.append((slug, name, "no_source", []))
            continue

        source_path = paths.rh_original(slug)
        if not source_path.exists() or source_path.stat().st_size == 0:
            print(f"\n--- {name} ({slug}) ---")
            download_single_graph(rh_id, source_path)
            if source_path.stat().st_size == 0:
                print(f"  WARNING: download returned 0 bytes, skipping")
                summary.append((slug, name, "download_failed", []))
                continue
        else:
            print(f"\n--- {name} ({slug}) --- [cached]")

        # Check if hand-edited masks already exist
        edited_masks = sorted(paths.RH_MASKS.glob(f"{slug}_*.png"))
        if edited_masks:
            names = [p.name for p in edited_masks]
            print(f"  Hand-edited masks: {len(names)} ({', '.join(names)})")
            summary.append((slug, name, "edited", names))
        else:
            mask_path = paths.RH_MASKS / f"{slug}.png"
            if not mask_path.exists():
                _export_mask(source_path, slug, paths.RH_MASKS, mask_path)
            else:
                print(f"  Base mask: {mask_path.name} [exists]")
            summary.append((slug, name, "base_only", []))

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    ds_count = 0
    rh_count = 0
    missing = []
    for slug, name, status, masks in summary:
        if status == "datasheet":
            print(f"  {name:<25} {slug:<15} ★ datasheet")
            ds_count += 1
        elif status == "edited":
            print(f"  {name:<25} {slug:<15} ✓ {len(masks)} mask variant(s)")
            rh_count += 1
        elif status == "base_only":
            print(f"  {name:<25} {slug:<15}   RH base mask")
            rh_count += 1
        else:
            print(f"  {name:<25} {slug:<15}   ⚠ {status}")
            missing.append(slug)

    print(f"\n  Datasheets: {ds_count}  |  RH masks: {rh_count}  |  Missing: {len(missing)}")


def cmd_build(args):
    """Digitize curves and write JSONs.

    Priority per mic:
      1. Hand-edited masks → _digitize_mask() (includes datasheet-generated masks)
      2. Datasheet config → digitize_datasheet() (unguided fallback)
      3. RH source image → digitize_single()
    """
    tmp_dir = Path("/tmp/poser")
    for d in [paths.DATASHEET_CURVES, paths.RH_CURVES]:
        d.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    slugs = args.slugs if hasattr(args, 'slugs') and args.slugs else sorted(MICS)
    for slug in slugs:
        if slug not in MICS:
            print(f"\nUnknown slug: {slug}")
            continue
        info = MICS[slug]
        name = info["name"]
        ds = info.get("datasheet")
        rh_id = info.get("rh_id")
        print(f"\n--- {name} ({slug}) ---")

        source_img = None  # for comparison plot
        plot_crop = None    # [left, top, right, bottom] for comparison plot
        output = None

        # Priority 1: Masks — check datasheet masks first, then RH masks
        mask_dir = None
        for candidate_dir in [paths.DATASHEET_MASKS, paths.RH_MASKS]:
            edited = sorted(candidate_dir.glob(f"{slug}_*.png"))
            single = candidate_dir / f"{slug}.png"
            if edited or single.exists():
                mask_dir = candidate_dir
                break

        edited_masks = sorted(mask_dir.glob(f"{slug}_*.png")) if mask_dir else []
        single_mask = (mask_dir / f"{slug}.png") if mask_dir else Path("/nonexistent")
        has_mask = bool(edited_masks) or single_mask.exists()

        if has_mask:
            mask_files = edited_masks if edited_masks else [single_mask]
            all_curves = []
            for mask_path in mask_files:
                print(f"  Mask: {mask_path.name}")
                results = _digitize_mask(mask_path, slug, mask_dir)
                curves = _results_to_curve_list(results)
                if curves:
                    # Single mask may contain multiple tracked paths
                    if len(mask_files) == 1:
                        all_curves.extend(curves)
                    else:
                        all_curves.append(curves[0])

            if all_curves:
                for i, c in enumerate(all_curves):
                    c["index"] = i
                    c["source"] = "mask"

                output = {
                    "slug": slug,
                    "name": name,
                    "hand_edited": True,
                    "curves": {
                        "single": {
                            "num_curves": len(all_curves),
                            "curves": all_curves,
                        }
                    },
                }
                # Use datasheet image for comparison if available
                if ds:
                    ds_path = paths.datasheet_original(slug)
                    if ds_path.exists():
                        source_img = ds_path
                        plot_crop = ds.get("plot_bounds")
                if source_img is None:
                    source_img = paths.rh_original(slug)
            else:
                print(f"  WARNING: no curves extracted from masks")

        # Priority 2: Datasheet (unguided auto-extraction)
        if output is None and ds:
            ds_path = paths.datasheet_original(slug)
            if ds_path.exists():
                results = digitize_datasheet(slug, ds, paths.DATASHEET_ORIGINALS)
                curve_list = _results_to_curve_list(results)

                curve_configs = ds.get("curves", [])
                for i, c in enumerate(curve_list):
                    c["source"] = "datasheet"
                    if i < len(curve_configs):
                        label = curve_configs[i].get("label")
                        if label:
                            c["note"] = label

                output = {
                    "slug": slug,
                    "name": name,
                    "hand_edited": False,
                    "curves": {},
                }
                if curve_list:
                    output["curves"]["single"] = {
                        "num_curves": len(curve_list),
                        "curves": curve_list,
                    }
                source_img = ds_path
                plot_crop = ds["plot_bounds"]
            else:
                print(f"  WARNING: datasheet not found: {ds_path}, falling back")

        # Priority 3: RH source image
        if output is None:
            source_path = paths.rh_original(slug)
            if not source_path.exists() or source_path.stat().st_size == 0:
                print(f"  SKIP: no source available")
                continue

            results = digitize_single(source_path)
            curve_list = _results_to_curve_list(results)

            output = {
                "slug": slug,
                "name": name,
                "hand_edited": False,
                "curves": {},
            }
            if curve_list:
                output["curves"]["single"] = {
                    "num_curves": len(curve_list),
                    "curves": curve_list,
                }
            source_img = source_path

        if output is None:
            continue

        # Route output to source-specific directory
        if mask_dir and mask_dir == paths.DATASHEET_MASKS:
            target_dir = paths.DATASHEET_CURVES
        elif ds and source_img and str(paths.DATASHEET_ORIGINALS) in str(source_img):
            target_dir = paths.DATASHEET_CURVES
        else:
            target_dir = paths.RH_CURVES
        target_dir.mkdir(parents=True, exist_ok=True)
        json_path = target_dir / f"{slug}.json"
        with open(json_path, "w") as f:
            json.dump(output, f, indent=2)

        n = output.get("curves", {}).get("single", {}).get("num_curves", 0)
        src_label = " (datasheet)" if target_dir == paths.DATASHEET_CURVES else ""
        edited_label = " (hand-edited)" if output.get("hand_edited") else ""
        print(f"  Wrote {json_path}: {n} curve(s){src_label}{edited_label}")

        for c in output.get("curves", {}).get("single", {}).get("curves", []):
            pts = c["data"]
            if pts:
                freqs = [p["hz"] for p in pts]
                dbs = [p["db"] for p in pts]
                print(f"    [{c.get('index', '?')}] {c.get('points', len(pts))} pts, "
                      f"{min(freqs):.0f}-{max(freqs):.0f}Hz, "
                      f"{min(dbs):.1f} to {max(dbs):.1f} dB")

        # Comparison plot
        if source_img and source_img.exists():
            plot_path = tmp_dir / f"{slug}_comparison.png"
            make_comparison_plot(source_img, output["curves"], plot_path,
                                [rh_id or slug], plot_crop=plot_crop)

    print(f"\nDone. JSONs in {paths.DATASHEET_CURVES}/ and {paths.RH_CURVES}/")
    print(f"Plots in {tmp_dir}/")


