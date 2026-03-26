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


# --- Curve extraction ---

def _detect_watermark_mask(img_orig, left, right, top, bottom):
    """Detect watermark region by finding columns with watermark-only palette entries.

    The watermark uses unique yellow/brown palette entries that don't appear in
    the curve or grid. Returns a set of (x, y) pixel positions.
    """
    if img_orig.mode != "P":
        return set()

    pal = img_orig.getpalette()
    n = len(pal) // 3
    px = img_orig.load()

    # Find palette entries that are clearly watermark (yellow/brown/olive tones)
    wm_indices = set()
    for i in range(n):
        r, g, b = pal[i*3], pal[i*3+1], pal[i*3+2]
        if r == g == b:
            continue
        # Watermark uses olive/brown/yellow-green tones
        # and pale yellow highlights
        is_olive = (r > 50 and g > 50 and b < r * 0.6 and abs(r - g) < 40)
        is_pale_yellow = (r > 200 and g > 200 and b > 150 and b < g and r >= g - 10)
        if is_olive or is_pale_yellow:
            wm_indices.add(i)

    if wm_indices:
        pal_info = img_orig.getpalette()
        wm_colors = [(i, (pal_info[i*3], pal_info[i*3+1], pal_info[i*3+2])) for i in wm_indices]
        print(f"  Watermark palette entries: {', '.join(f'[{i}]({r},{g},{b})' for i,(r,g,b) in wm_colors)}")

    mask = set()
    for x in range(left + 1, right):
        for y in range(top + 1, bottom):
            if px[x, y] in wm_indices:
                mask.add((x, y))

    return mask


def extract_curve(img_orig, img_rgb, target_color, left, right, top, bottom):
    """Extract curve pixels by color, using palette when available.

    Two-pass approach:
    1. First pass: extract using only pure curve colors (high confidence)
    2. Second pass: for columns with NO pure matches, try blend colors
       (fills gaps where watermark occludes the curve)

    Returns list of (x_pixel, y_avg) pairs.
    """
    # Detect regions to skip
    # Legend has colored swatches + mic name text in top-left of plot area.
    # Empirically extends to about x=left+215, y=top+75.
    legend_right = left + 215
    legend_bottom = top + 75
    watermark = _detect_watermark_mask(img_orig, left, right, top, bottom)
    print(f"  Watermark pixels detected: {len(watermark)}")

    # Classify palette
    pal_weights = classify_palette(img_orig, target_color)
    use_palette = pal_weights is not None

    if use_palette:
        pal = img_orig.getpalette()
        # Split into pure curve vs blend entries
        pure_indices = {}
        blend_indices = {}
        for i, w in pal_weights.items():
            r, g, b = pal[i*3], pal[i*3+1], pal[i*3+2]
            dist = color_dist((r, g, b), target_color)
            if dist < COLOR_THRESHOLD:
                pure_indices[i] = w
            else:
                blend_indices[i] = w

        print(f"  Pure curve entries: {len(pure_indices)}")
        for i, w in sorted(pure_indices.items(), key=lambda x: -x[1]):
            r, g, b = pal[i*3], pal[i*3+1], pal[i*3+2]
            print(f"    [{i:2d}] ({r:3d},{g:3d},{b:3d}) w={w:.2f}")
        print(f"  Blend entries (gap-fill only): {len(blend_indices)}")
        for i, w in sorted(blend_indices.items(), key=lambda x: -x[1]):
            r, g, b = pal[i*3], pal[i*3+1], pal[i*3+2]
            print(f"    [{i:2d}] ({r:3d},{g:3d},{b:3d}) w={w:.2f}")

        px = img_orig.load()
    else:
        px = img_rgb.load()
        pure_indices = None
        blend_indices = None

    # Pass 1: pure curve colors only
    pure_points = {}  # x -> (avg_y)
    for x in range(left + 1, right):
        matching_ys = []
        matching_ws = []

        for y in range(top + 1, bottom):
            # Skip legend area
            if x < legend_right and y < legend_bottom:
                continue
            # Skip watermark pixels for pure detection
            # (pure curve colors shouldn't appear in watermark)

            if use_palette:
                idx = px[x, y]
                if idx in pure_indices:
                    matching_ys.append(y)
                    matching_ws.append(pure_indices[idx])
            else:
                dist = color_dist(px[x, y][:3], target_color)
                if dist < COLOR_THRESHOLD:
                    matching_ys.append(y)
                    matching_ws.append(1.0 - dist / COLOR_THRESHOLD)

        if matching_ys:
            pure_points[x] = _best_cluster_y(matching_ys, matching_ws)

    print(f"  Pass 1 (pure): {len(pure_points)} columns")

    # Pass 2: fill gaps using blend colors (watermark-occluded regions)
    # Only fill between pure points and extend a limited distance past the last one.
    # Don't extend past where the curve actually ends.
    blend_points = {}
    if use_palette and blend_indices and pure_points:
        x_min = min(pure_points.keys())
        x_max = max(pure_points.keys())
        # Allow blend to extend a bit past last pure point, but not forever.
        # Use a trailing guide: track the last known y position and stop when
        # we go too many consecutive columns without a blend match.
        max_gap = 15  # stop after 15 consecutive empty columns
        consecutive_empty = 0
        last_y = pure_points[x_max]

        for x in range(x_min, right):
            if x in pure_points:
                last_y = pure_points[x]
                consecutive_empty = 0
                continue

            if consecutive_empty > max_gap:
                break

            matching_ys = []
            matching_ws = []
            for y in range(top + 1, bottom):
                idx = px[x, y]
                if idx in blend_indices:
                    if abs(y - last_y) > 25:
                        continue
                    matching_ys.append(y)
                    matching_ws.append(blend_indices[idx])

            if matching_ys:
                y_val = _best_cluster_y(matching_ys, matching_ws)
                blend_points[x] = y_val
                last_y = y_val
                consecutive_empty = 0
            else:
                consecutive_empty += 1

    print(f"  Pass 2 (blend gap-fill): {len(blend_points)} columns")

    # Merge: pure takes precedence
    all_points = {**blend_points, **pure_points}
    points = sorted(all_points.items())
    return [(x, y) for x, y in points]


def _best_cluster_y(ys, weights):
    """Weighted average of the tightest y-cluster (handles watermark noise)."""
    if len(ys) <= 3:
        tw = sum(weights)
        return sum(y * w for y, w in zip(ys, weights)) / tw

    pairs = sorted(zip(ys, weights))
    sy = [p[0] for p in pairs]
    sw = [p[1] for p in pairs]

    # Find tightest cluster within 6px (~2dB)
    best_i, best_j, best_count = 0, len(sy) - 1, 0
    for i in range(len(sy)):
        for j in range(i, len(sy)):
            if sy[j] - sy[i] > 6:
                break
            count = j - i + 1
            if count > best_count:
                best_i, best_j, best_count = i, j, count

    cy = sy[best_i:best_j + 1]
    cw = sw[best_i:best_j + 1]
    tw = sum(cw)
    return sum(y * w for y, w in zip(cy, cw)) / tw


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
    """Generate side-by-side: original image (top) + digitized curves (bottom)."""
    src = Image.open(source_img_path)

    fig, (ax_orig, ax_dig) = plt.subplots(2, 1, figsize=(12, 8),
                                           gridspec_kw={"height_ratios": [1, 1.2]})

    # Top: original image
    ax_orig.imshow(np.array(src.convert("RGB")))
    ax_orig.set_title("Original (RecordingHacks)", fontsize=11)
    ax_orig.axis("off")

    # Bottom: our digitized curves
    colors = ["#f69410", "#9410a0"]  # orange, purple
    labels = []
    for i, (key, label_prefix) in enumerate([("first", mic_ids[0]), ("second", mic_ids[1])]):
        if key not in curves:
            continue
        pts = curves[key]["data"]
        freqs = [p["hz"] for p in pts]
        dbs = [p["db"] for p in pts]
        ax_dig.semilogx(freqs, dbs, color=colors[i], linewidth=1.5,
                        label=f"{label_prefix} ({len(pts)} pts)")
        labels.append(label_prefix)

    ax_dig.set_xlim(20, 20000)
    ax_dig.set_ylim(-20, 20)
    ax_dig.set_xlabel("Frequency (Hz)")
    ax_dig.set_ylabel("dB")
    ax_dig.set_title("Digitized", fontsize=11)
    ax_dig.legend(loc="upper left")
    ax_dig.grid(True, which="both", alpha=0.3)
    ax_dig.set_xticks([20, 100, 1000, 10000, 20000])
    ax_dig.set_xticklabels(["20Hz", "100Hz", "1kHz", "10kHz", "20kHz"])

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Comparison plot: {out_path}")


# --- Download ---

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
        raw = extract_curve(img_orig, img_rgb, color, left, right, top, bottom)
        print(f"  Raw pixel columns: {len(raw)}")

        data = pixels_to_data(raw, A, B, top, bottom)
        data = filter_continuity(data)
        print(f"  After filtering: {len(data)} points")

        if data:
            freqs = [d[0] for d in data]
            dbs = [d[1] for d in data]
            print(f"  Coverage: {min(freqs):.0f}Hz - {max(freqs):.0f}Hz")
            print(f"  dB range: {min(dbs):.1f} to {max(dbs):.1f}")

        results[key] = {
            "raw_points": len(raw),
            "data": data,
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="Digitize RecordingHacks frequency response curves")
    parser.add_argument("id1", nargs="?", default="0006", help="First mic ID (default: 0006 = SM57)")
    parser.add_argument("id2", nargs="?", default="0253", help="Second mic ID (default: 0253 = SM58)")
    parser.add_argument("--first", action="store_true", help="Extract first curve only")
    parser.add_argument("--second", action="store_true", help="Extract second curve only")
    parser.add_argument("--image", type=Path, help="Use local image instead of downloading")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    args = parser.parse_args()

    extract = "both"
    if args.first:
        extract = "first"
    elif args.second:
        extract = "second"

    # Paths
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data" / "curves" / "digitized"
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path("/tmp/poser")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Download
    if args.image:
        image_path = args.image
    else:
        image_path = tmp_dir / f"{args.id1}-{args.id2}.png"
        download_graph(args.id1, args.id2, image_path)

    # Digitize
    results = digitize(image_path, extract=extract)

    # Build JSON output
    output = {
        "source": f"https://recordinghacks.com/graphs2.php/{args.id1}-{args.id2}",
        "mic_ids": [args.id1, args.id2],
        "curves": {},
    }
    for key in ("first", "second"):
        if key in results:
            output["curves"][key] = {
                "raw_pixel_count": results[key]["raw_points"],
                "points": len(results[key]["data"]),
                "data": [{"hz": hz, "db": db} for hz, db in results[key]["data"]],
            }

    # Write JSON (data goes in repo)
    json_path = args.output or (data_dir / f"{args.id1}-{args.id2}.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {json_path}")

    for key, label in [("first", "First"), ("second", "Second")]:
        if key in output["curves"]:
            c = output["curves"][key]
            freqs = [p["hz"] for p in c["data"]]
            dbs = [p["db"] for p in c["data"]]
            print(f"  {label}: {c['points']} pts, "
                  f"{min(freqs):.0f}-{max(freqs):.0f}Hz, "
                  f"{min(dbs):.1f} to {max(dbs):.1f} dB")

    # Comparison plot (ephemeral, goes to /tmp)
    plot_path = tmp_dir / f"{args.id1}-{args.id2}_comparison.png"
    make_comparison_plot(image_path, output["curves"], plot_path, [args.id1, args.id2])


if __name__ == "__main__":
    main()
