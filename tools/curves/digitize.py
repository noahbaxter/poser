#!/usr/bin/env python3
"""Digitize microphone frequency response curves from RecordingHacks comparison PNGs.

Downloads a comparison graph from recordinghacks.com/graphs2.php/{id1}-{id2}
(1200x401 PNG), extracts the two colored curves, and outputs frequency/dB data
as JSON plus a side-by-side comparison image.

Usage:
    python3 digitize_curve.py                    # Default: SM57 vs SM58
    python3 digitize_curve.py 0006 0253          # Explicit mic IDs
    python3 digitize_curve.py 0006 0253 --first  # Extract first curve only
    python3 digitize_curve.py 0006 0253 --second # Extract second curve only
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
COLOR_THRESHOLD = 70
BLEND_THRESHOLD = 160

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


def color_dist(c1, c2):
    """Euclidean distance between two RGB tuples."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


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


# --- Color detection ---

def detect_curve_colors(img_rgb, left, top):
    """Detect the two curve colors from legend swatches in top-left."""
    from collections import Counter
    pixels = img_rgb.load()

    swatch_colors = []
    for y in range(top + 10, top + 80):
        for x in range(left + 5, left + 30):
            r, g, b = pixels[x, y][:3]
            if r == g == b:
                continue
            if (r, g, b) == (246, 246, 246):
                continue
            swatch_colors.append((r, g, b))

    if not swatch_colors:
        print("  WARNING: Could not detect legend colors, using defaults")
        return (246, 148, 16), (148, 16, 148)

    counts = Counter(swatch_colors)
    result_colors = []
    for color, _ in counts.most_common(10):
        if all(color_dist(color, c) >= 50 for c in result_colors):
            result_colors.append(color)
        if len(result_colors) == 2:
            break

    if len(result_colors) == 2:
        # Order by vertical position in legend (top = first mic)
        def first_y(color):
            for y in range(top + 10, top + 80):
                for x in range(left + 5, left + 30):
                    if color_dist(pixels[x, y][:3], color) < 30:
                        return y
            return 999
        result_colors.sort(key=first_y)
        return tuple(result_colors[0]), tuple(result_colors[1])

    print("  WARNING: Could not find two distinct legend colors, using defaults")
    return (246, 148, 16), (148, 16, 148)


# --- Palette classification ---

def classify_palette(img, target_color):
    """For paletted images, classify each palette entry as curve/blend/other.

    Returns dict of palette_index -> weight, or None if not paletted.
    """
    if img.mode != "P":
        return None

    pal = img.getpalette()
    n_colors = len(pal) // 3
    weights = {}
    tr, tg, tb = target_color

    for i in range(n_colors):
        r, g, b = pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]

        # Skip pure grays (background, gridlines, borders)
        if r == g == b:
            continue

        dist = color_dist((r, g, b), target_color)

        if dist < COLOR_THRESHOLD:
            # Direct curve match
            weights[i] = 1.0 - (dist / COLOR_THRESHOLD)
        elif dist < BLEND_THRESHOLD:
            # Possible watermark blend — check if it retains curve color character
            is_blend = False
            if tr > tb:  # Orange-ish target
                is_blend = r > g and r > b
            else:  # Purple-ish target
                is_blend = r > g and b > g
            if is_blend:
                weights[i] = 0.3 * (1.0 - (dist / BLEND_THRESHOLD))

    return weights


# --- Curve extraction (connected component approach) ---

def _build_color_mask(img_orig, img_rgb, target_color, left, right, top, bottom):
    """Build a binary mask of all pixels matching the target color.

    Returns a 2D numpy array (height x width) where True = matches target color.
    Uses palette classification for paletted images.
    """
    plot_w = right - left
    plot_h = bottom - top
    mask = np.zeros((plot_h, plot_w), dtype=bool)

    pal_weights = classify_palette(img_orig, target_color)

    if pal_weights is not None:
        # Palette mode: use classified indices
        pure_indices = set()
        for i, w in pal_weights.items():
            pal = img_orig.getpalette()
            r, g, b = pal[i*3], pal[i*3+1], pal[i*3+2]
            dist = color_dist((r, g, b), target_color)
            if dist < COLOR_THRESHOLD:
                pure_indices.add(i)

        px = img_orig.load()
        for x in range(left + 1, right - 1):
            for y in range(top + 1, bottom - 1):
                if px[x, y] in pure_indices:
                    mask[y - top, x - left] = True

        print(f"  Pure palette indices: {sorted(pure_indices)}")
    else:
        # RGB mode: distance-based matching
        px = img_rgb.load()
        for x in range(left + 1, right - 1):
            for y in range(top + 1, bottom - 1):
                if color_dist(px[x, y][:3], target_color) < COLOR_THRESHOLD:
                    mask[y - top, x - left] = True

    total = int(np.sum(mask))
    print(f"  Color mask: {total} pixels")
    return mask


def _find_connected_components(mask):
    """Find connected components in a binary mask using flood fill.

    Uses 8-connectivity (diagonal pixels count as connected).
    Returns list of components, each a set of (row, col) tuples.
    """
    visited = np.zeros_like(mask, dtype=bool)
    components = []
    rows, cols = mask.shape

    for r in range(rows):
        for c in range(cols):
            if mask[r, c] and not visited[r, c]:
                # BFS flood fill
                component = set()
                queue = [(r, c)]
                visited[r, c] = True
                while queue:
                    cr, cc = queue.pop(0)
                    component.add((cr, cc))
                    # 8-connectivity neighbors
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = cr + dr, cc + dc
                            if 0 <= nr < rows and 0 <= nc < cols:
                                if mask[nr, nc] and not visited[nr, nc]:
                                    visited[nr, nc] = True
                                    queue.append((nr, nc))
                components.append(component)

    return components


def _component_x_span(component, left):
    """Get the x-pixel span (min_x, max_x) of a component in plot coordinates."""
    cols = [c for _, c in component]
    return min(cols) + left, max(cols) + left


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


def _trace_component(component, left, top):
    """Trace a connected component into one or more curves using multi-object tracking.

    Scans every column for y-clusters and tracks each line independently.
    New lines start when an unmatched cluster appears. Lines survive gaps
    (dashed lines, gridline crossings). Multiple solid or dashed lines
    in the same component each get their own path.

    Returns list of curves, each a list of (x_pixel, y_avg) pairs.
    Sorted by x-span (widest first).
    """
    # Group pixels by column
    col_ys = {}
    for r, c in component:
        x = c + left
        y = r + top
        col_ys.setdefault(x, []).append(y)

    x_values = sorted(col_ys.keys())
    if not x_values:
        return []

    # Build cluster centers per column
    col_centers = {}
    for x in x_values:
        clusters = _cluster_ys(col_ys[x])
        col_centers[x] = [sum(c) / len(c) for c in clusters]

    # Multi-object tracking across columns
    # Each active path: [last_y, points_list, gap_count]
    active = []
    MAX_GAP = 12     # survive this many empty columns (handles dashes, gridlines)
    MATCH_DIST = 20   # max y-distance to match a cluster to a path

    for x in x_values:
        centers = col_centers[x]

        # Build candidate matches: (distance, center_idx, path_idx)
        candidates = []
        for ci, cy in enumerate(centers):
            for pi, (last_y, _, _) in enumerate(active):
                candidates.append((abs(cy - last_y), ci, pi))
        candidates.sort()

        matched_paths = set()
        matched_centers = set()

        # Greedy closest-first matching
        for dist, ci, pi in candidates:
            if ci in matched_centers or pi in matched_paths:
                continue
            if dist <= MATCH_DIST:
                last_y, pts, _ = active[pi]
                pts.append((x, centers[ci]))
                active[pi] = (centers[ci], pts, 0)
                matched_paths.add(pi)
                matched_centers.add(ci)

        # Unmatched centers → new paths (a line just appeared)
        for ci, cy in enumerate(centers):
            if ci not in matched_centers:
                active.append((cy, [(x, cy)], 0))

        # Unmatched paths → increment gap counter
        for pi in range(len(active)):
            if pi not in matched_paths:
                last_y, pts, gap = active[pi]
                active[pi] = (last_y, pts, gap + 1)

        # Remove dead paths (gap too large) — move to finished
        # (keep them in active but skip matching once dead)

    # Collect all paths with enough points
    min_points = max(20, len(x_values) * 0.05)  # at least 5% of columns
    paths = [pts for _, pts, _ in active if len(pts) >= min_points]

    # Deduplicate near-identical paths
    paths.sort(key=lambda p: -(p[-1][0] - p[0][0]) if len(p) > 1 else 0)
    unique = []
    for path in paths:
        is_dup = False
        for existing in unique:
            # Sample both at ~10 evenly spaced x positions
            ex_dict = dict(existing)
            diffs = []
            for x, y in path[::max(1, len(path) // 10)]:
                if x in ex_dict:
                    diffs.append(abs(y - ex_dict[x]))
            if len(diffs) >= 3 and sum(diffs) / len(diffs) < 4:
                is_dup = True
                break
        if not is_dup:
            unique.append(path)

    return unique if unique else [[(x, sum(col_ys[x]) / len(col_ys[x])) for x in x_values]]


def extract_curve(img_orig, img_rgb, target_color, left, right, top, bottom):
    """Extract curve pixels and trace all distinct lines using multi-object tracking.

    Skips connected component analysis entirely — instead builds per-column
    y-clusters directly from the color mask and tracks each line independently.
    This correctly separates solid lines, dashed lines, and multi-line charts
    even when they touch or cross.

    Returns list of paths (each a list of (x_pixel, y_avg) pairs), sorted
    by span (widest first).
    """
    # Build color mask
    mask = _build_color_mask(img_orig, img_rgb, target_color, left, right, top, bottom)

    # Legend zone: skip colored pixels in the top-left area (swatch + mic name text)
    legend_max_x = left + 300
    legend_max_y = top + 80

    # Build per-column y-clusters directly from the mask (gap=5 for fine separation)
    col_centers = {}
    plot_h, plot_w = mask.shape
    for c in range(plot_w):
        x = c + left
        ys = []
        for r in range(plot_h):
            y = r + top
            if mask[r, c]:
                # Skip legend zone
                if x < legend_max_x and y < legend_max_y:
                    continue
                ys.append(y)
        if ys:
            clusters = _cluster_ys(ys, gap=5)
            col_centers[x] = [sum(cl) / len(cl) for cl in clusters]

    x_values = sorted(col_centers.keys())
    if not x_values:
        print("  WARNING: No curve pixels found")
        return []

    # Count max simultaneous lines
    max_clusters = max(len(col_centers[x]) for x in x_values)
    print(f"  Columns with data: {len(x_values)}, max simultaneous lines: {max_clusters}")

    # Multi-object tracking across columns
    active = []  # list of [last_y, points_list, gap_count]
    MATCH_DIST = 15
    MAX_GAP = 15  # survive gaps (dashes, gridline crossings)

    for x in x_values:
        centers = col_centers[x]

        # Build candidate matches: (distance, center_idx, path_idx)
        candidates = []
        for ci, cy in enumerate(centers):
            for pi, (last_y, _, gap) in enumerate(active):
                if gap > MAX_GAP:
                    continue  # path is dead
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

        # Unmatched centers → new paths
        for ci, cy in enumerate(centers):
            if ci not in matched_centers:
                active.append((cy, [(x, cy)], 0))

        # Increment gap for unmatched active paths
        for pi in range(len(active)):
            if pi not in matched_paths:
                last_y, pts, gap = active[pi]
                active[pi] = (last_y, pts, gap + 1)

    # Collect paths, filter short ones (legend text, labels, etc.)
    plot_width = right - left
    min_span = plot_width * 0.20  # must span at least 20% of plot width
    paths = []
    for _, pts, _ in active:
        if len(pts) < 20:
            continue
        span = pts[-1][0] - pts[0][0]
        if span >= min_span:
            paths.append(pts)

    # Deduplicate near-identical paths
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
            if len(diffs) >= 3 and sum(diffs) / len(diffs) < 4:
                is_dup = True
                break
        if not is_dup:
            unique.append(path)

    print(f"  Tracked {len(unique)} distinct path(s)")
    for i, path in enumerate(unique):
        span = path[-1][0] - path[0][0]
        print(f"    Path {i}: {len(path)} pts, span={span}px")

    # Extend each path with blend colors through watermark region
    pal_weights = classify_palette(img_orig, target_color)
    blend_indices = {}
    if pal_weights is not None and img_orig.mode == "P":
        pal = img_orig.getpalette()
        for i, w in pal_weights.items():
            r, g, b = pal[i*3], pal[i*3+1], pal[i*3+2]
            if color_dist((r, g, b), target_color) >= COLOR_THRESHOLD:
                blend_indices[i] = w

    extended = []
    for path in unique:
        if blend_indices and path:
            path = _extend_with_blends(path, img_orig, blend_indices, top, bottom, right)
        extended.append(path)

    for i, path in enumerate(extended):
        print(f"  Path {i} final: {len(path)} points")

    return extended


def _extend_with_blends(points, img_orig, blend_indices, top, bottom, right):
    """Extend a single path using blend-colored pixels (watermark fill)."""
    px = img_orig.load()
    point_dict = {x: y for x, y in points}
    last_y = point_dict[max(point_dict.keys())]
    blend_count = 0
    consecutive_empty = 0

    for x in range(min(point_dict.keys()), right):
        if x in point_dict:
            last_y = point_dict[x]
            consecutive_empty = 0
            continue
        if consecutive_empty > 15:
            break

        matching_ys = []
        for y in range(top + 1, bottom - 1):
            if px[x, y] in blend_indices and abs(y - last_y) <= 25:
                matching_ys.append(y)

        if matching_ys:
            avg_y = sum(matching_ys) / len(matching_ys)
            point_dict[x] = avg_y
            last_y = avg_y
            consecutive_empty = 0
            blend_count += 1
        else:
            consecutive_empty += 1

    if blend_count:
        print(f"    +{blend_count} blend columns")
    return sorted(point_dict.items())


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

    fig, (ax_orig, ax_dig) = plt.subplots(2, 1, figsize=(12, 8),
                                           gridspec_kw={"height_ratios": [1, 1.2]})

    # Top: original image
    ax_orig.imshow(np.array(src.convert("RGB")))
    ax_orig.set_title("Original (RecordingHacks)", fontsize=11)
    ax_orig.axis("off")

    # Bottom: all digitized curves
    base_colors = ["#f69410", "#9410a0", "#cc0000"]  # orange, purple, red
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

    ax_dig.set_xlim(20, 20000)
    ax_dig.set_ylim(-20, 20)
    ax_dig.set_xlabel("Frequency (Hz)")
    ax_dig.set_ylabel("dB")
    ax_dig.set_title("Digitized", fontsize=11)
    ax_dig.legend(loc="upper left", fontsize=8)
    ax_dig.grid(True, which="both", alpha=0.3)
    ax_dig.set_xticks([20, 100, 1000, 10000, 20000])
    ax_dig.set_xticklabels(["20Hz", "100Hz", "1kHz", "10kHz", "20kHz"])

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


def download_graph(id1, id2, save_path):
    """Download a RecordingHacks comparison graph PNG."""
    url = f"https://recordinghacks.com/graphs2.php/{id1}-{id2}"
    print(f"Downloading {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    if not resp.content[:4] == b"\x89PNG":
        print(f"  ERROR: Response is not a PNG")
        sys.exit(1)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(resp.content)
    print(f"  Saved to {save_path} ({len(resp.content)} bytes)")


# --- Main pipeline ---

def digitize(image_path, extract="both"):
    """Main digitization pipeline. Returns (results_dict, calibration_info)."""
    print(f"\nAnalyzing {image_path}")

    # Keep original (paletted) AND RGB versions
    img_orig = Image.open(image_path)
    img_rgb = img_orig.convert("RGB")
    w, h = img_orig.size
    print(f"  Image: {w}x{h}, mode={img_orig.mode}")

    if img_orig.mode == "P":
        pal = img_orig.getpalette()
        n = len(pal) // 3
        print(f"  Palette: {n} colors")

    # Detect geometry
    left, right, top, bottom = detect_plot_bounds(img_rgb)
    print(f"  Plot bounds: x=[{left}, {right}], y=[{top}, {bottom}]")

    A, B = calibrate_x_axis(img_orig, left, right, top, bottom)
    print(f"  Calibration: A={A:.1f}, B={B:.1f}")
    print(f"  Freq range: {pixel_to_freq(left, A, B):.0f}Hz - {pixel_to_freq(right, A, B):.0f}Hz")

    # Detect colors
    color1, color2 = detect_curve_colors(img_rgb, left, top)
    print(f"  Curve 1 color: RGB{color1}")
    print(f"  Curve 2 color: RGB{color2}")

    results = {}
    curve_configs = []
    if extract in ("both", "first"):
        curve_configs.append(("first", color1))
    if extract in ("both", "second"):
        curve_configs.append(("second", color2))

    for key, color in curve_configs:
        print(f"\nExtracting {key} curve (target RGB{color})...")
        all_paths = extract_curve(img_orig, img_rgb, color, left, right, top, bottom)

        # Convert each path to frequency/dB data
        curves = []
        for i, raw_path in enumerate(all_paths):
            data = pixels_to_data(raw_path, A, B, top, bottom)
            data = filter_continuity(data)
            if data:
                freqs = [d[0] for d in data]
                dbs = [d[1] for d in data]
                print(f"  Curve {i}: {len(data)} pts, {min(freqs):.0f}-{max(freqs):.0f}Hz, {min(dbs):.1f} to {max(dbs):.1f}dB")
                curves.append(data)

        results[key] = {
            "raw_paths": len(all_paths),
            "curves": curves,
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="Digitize RecordingHacks frequency response curves")
    parser.add_argument("id1", nargs="?", default="0006", help="First mic ID (or single mic ID with --single)")
    parser.add_argument("id2", nargs="?", default="0253", help="Second mic ID (ignored with --single)")
    parser.add_argument("--single", action="store_true", help="Single-mic graph mode (476x159, red curve)")
    parser.add_argument("--first", action="store_true", help="Extract first curve only (comparison mode)")
    parser.add_argument("--second", action="store_true", help="Extract second curve only (comparison mode)")
    parser.add_argument("--image", type=Path, help="Use local image instead of downloading")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    args = parser.parse_args()

    # Paths
    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_root / "data" / "curves" / "digitized"
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path("/tmp/poser")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    if args.single:
        # Single-mic graph mode
        mic_id = args.id1
        if args.image:
            image_path = args.image
        else:
            image_path = tmp_dir / f"single_{mic_id}.png"
            download_single_graph(mic_id, image_path)

        results = digitize_single(image_path)

        output = {
            "source": f"https://recordinghacks.com/graphs2.php/{mic_id}",
            "mic_ids": [mic_id],
            "mic_names": [RH_MIC_NAMES.get(mic_id, mic_id)],
            "mode": "single",
            "curves": {},
        }
        if "single" in results:
            curve_list = []
            for i, data in enumerate(results["single"]["curves"]):
                curve_list.append({
                    "index": i,
                    "points": len(data),
                    "data": [{"hz": hz, "db": db} for hz, db in data],
                })
            output["curves"]["single"] = {
                "num_curves": len(curve_list),
                "curves": curve_list,
            }

        json_path = args.output or (data_dir / f"single-{mic_id}.json")
        with open(json_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nWrote {json_path}")

        for c in output.get("curves", {}).get("single", {}).get("curves", []):
            pts = c["data"]
            if pts:
                freqs = [p["hz"] for p in pts]
                dbs = [p["db"] for p in pts]
                print(f"  Curve {c['index']}: {c['points']} pts, "
                      f"{min(freqs):.0f}-{max(freqs):.0f}Hz, "
                      f"{min(dbs):.1f} to {max(dbs):.1f} dB")

        # Comparison plot
        plot_path = tmp_dir / f"single-{mic_id}_comparison.png"
        make_comparison_plot(image_path, output["curves"], plot_path, [mic_id])
        return

    # Comparison mode (original behavior)
    extract = "both"
    if args.first:
        extract = "first"
    elif args.second:
        extract = "second"

    if args.image:
        image_path = args.image
    else:
        image_path = tmp_dir / f"{args.id1}-{args.id2}.png"
        download_graph(args.id1, args.id2, image_path)

    # Digitize
    results = digitize(image_path, extract=extract)

    # Build JSON output — all curves, not just one
    output = {
        "source": f"https://recordinghacks.com/graphs2.php/{args.id1}-{args.id2}",
        "mic_ids": [args.id1, args.id2],
        "mic_names": [RH_MIC_NAMES.get(args.id1, args.id1), RH_MIC_NAMES.get(args.id2, args.id2)],
        "mode": "comparison",
        "curves": {},
    }
    for key in ("first", "second"):
        if key in results:
            curve_list = []
            for i, data in enumerate(results[key]["curves"]):
                curve_list.append({
                    "index": i,
                    "points": len(data),
                    "data": [{"hz": hz, "db": db} for hz, db in data],
                })
            output["curves"][key] = {
                "num_curves": len(curve_list),
                "curves": curve_list,
            }

    # Write JSON (data goes in repo)
    json_path = args.output or (data_dir / f"{args.id1}-{args.id2}.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {json_path}")

    for key, label in [("first", "First"), ("second", "Second")]:
        if key in output["curves"]:
            info = output["curves"][key]
            print(f"  {label}: {info['num_curves']} curve(s)")
            for c in info["curves"]:
                freqs = [p["hz"] for p in c["data"]]
                dbs = [p["db"] for p in c["data"]]
                print(f"    [{c['index']}] {c['points']} pts, "
                      f"{min(freqs):.0f}-{max(freqs):.0f}Hz, "
                      f"{min(dbs):.1f} to {max(dbs):.1f} dB")

    # Comparison plot (ephemeral, goes to /tmp)
    plot_path = tmp_dir / f"{args.id1}-{args.id2}_comparison.png"
    make_comparison_plot(image_path, output["curves"], plot_path, [args.id1, args.id2])


if __name__ == "__main__":
    main()
