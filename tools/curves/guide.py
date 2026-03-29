#!/usr/bin/env python3
"""Interactive guide curve tracer for manufacturer datasheets.

Opens each datasheet image and lets you trace the frequency response curve(s)
by clicking or click-dragging. Saves guide data that the digitizer uses as a
search corridor for more accurate extraction.

Usage:
    python3 tools/curves/guide.py              # All mics with datasheet config
    python3 tools/curves/guide.py sm57 md421   # Specific slugs only

Controls:
    Click        — place a single point
    Click+drag   — freehand trace (points placed as you drag)
    U            — undo last point
    C            — clear all points on current curve
    N            — finish current curve, start tracing next curve on same image
    Enter        — finish and save all curves for this mic, move to next
    Q / Escape   — skip this mic without saving
"""

import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backend_bases import MouseButton
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry import MICS
import paths

# Colors for successive curves
CURVE_COLORS = ["#ff2222", "#22dd22", "#ffcc00", "#ff00ff", "#00ccff", "#ff8800"]


def _px_to_freq(x_crop, left, right, freq_lo, freq_hi):
    """Convert crop-relative pixel x to frequency (log scale)."""
    x_abs = x_crop + left
    t = (x_abs - left) / (right - left)
    return freq_lo * (freq_hi / freq_lo) ** t


def _px_to_db(y_crop, top, bottom, db_top, db_bottom):
    """Convert crop-relative pixel y to dB."""
    y_abs = y_crop + top
    t = (y_abs - top) / (bottom - top)
    return db_top + t * (db_bottom - db_top)


def _freq_to_px(freq, left, right, freq_lo, freq_hi):
    """Convert frequency to crop-relative pixel x."""
    t = math.log10(freq / freq_lo) / math.log10(freq_hi / freq_lo)
    return t * (right - left)


def _db_to_px(db, top, bottom, db_top, db_bottom):
    """Convert dB to crop-relative pixel y."""
    t = (db - db_top) / (db_bottom - db_top)
    return t * (bottom - top)


class GuideTracer:
    """Interactive matplotlib widget for tracing curves on a datasheet image."""

    DRAG_THRESHOLD = 4  # pixels of movement before click becomes drag
    THIN_DISTANCE = 3   # min pixel distance between consecutive drag points

    def __init__(self, img_array, slug, ds_config):
        self.slug = slug
        self.ds = ds_config
        self.left, self.top, self.right, self.bottom = ds_config["plot_bounds"]
        self.freq_lo, self.freq_hi = ds_config["freq_range"]
        self.db_top, self.db_bottom = ds_config["db_range"]

        # Crop to plot area
        self.crop = img_array[self.top:self.bottom, self.left:self.right]
        self.plot_w = self.right - self.left
        self.plot_h = self.bottom - self.top

        # State
        self.points = []           # current curve: list of (x_crop, y_crop)
        self.completed = []        # finished curves: list of point lists
        self._press_xy = None      # (x, y) of mouse press for drag detection
        self._is_drag = False
        self.skipped = False

        # Set up figure
        self.fig, self.ax = plt.subplots(1, 1, figsize=(14, 7))
        self.fig.canvas.manager.set_window_title(f"Guide: {slug}")
        self.ax.imshow(self.crop, aspect="auto")
        self._set_title()
        self._add_axis_labels()

        # Line artists for current curve
        ci = 0
        self.dot_artist, = self.ax.plot([], [], ".", color=CURVE_COLORS[ci],
                                        markersize=4, zorder=5)
        self.line_artist, = self.ax.plot([], [], "-", color=CURVE_COLORS[ci],
                                         linewidth=1.5, alpha=0.8, zorder=4)

        # Artists for completed curves (added dynamically)
        self.completed_artists = []

        # Connect events
        self.fig.canvas.mpl_connect("button_press_event", self._on_press)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig.canvas.mpl_connect("button_release_event", self._on_release)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

    def _set_title(self):
        n = len(self.completed) + 1
        self.ax.set_title(
            f"{self.slug} — curve #{n}  |  "
            "click/drag to trace · Z=undo · C=clear · N=next curve · Enter=done · Q=skip",
            fontsize=10,
        )

    def _add_axis_labels(self):
        freq_ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
        freq_labels = ["20", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"]
        x_pos, x_lab = [], []
        for f, lab in zip(freq_ticks, freq_labels):
            if self.freq_lo <= f <= self.freq_hi:
                px = _freq_to_px(f, self.left, self.right, self.freq_lo, self.freq_hi)
                x_pos.append(px)
                x_lab.append(lab)
        self.ax.set_xticks(x_pos)
        self.ax.set_xticklabels(x_lab)

        db_range = abs(self.db_top - self.db_bottom)
        step = 5 if db_range <= 40 else 10
        lo, hi = sorted([self.db_top, self.db_bottom])
        for db in np.arange(lo, hi + 1, step):
            py = _db_to_px(db, self.top, self.bottom, self.db_top, self.db_bottom)
            self.ax.axhline(py, color="#ffffff", linewidth=0.3, alpha=0.3)
        db_vals = np.arange(lo, hi + 1, step)
        y_pos = [_db_to_px(d, self.top, self.bottom, self.db_top, self.db_bottom) for d in db_vals]
        self.ax.set_yticks(y_pos)
        self.ax.set_yticklabels([f"{d:+.0f}" for d in db_vals])

    # --- Mouse events ---

    def _on_press(self, event):
        if event.inaxes != self.ax or event.button != MouseButton.LEFT:
            return
        self._press_xy = (event.xdata, event.ydata)
        self._is_drag = False

    def _on_motion(self, event):
        if self._press_xy is None or event.inaxes != self.ax:
            return
        x, y = event.xdata, event.ydata
        px, py = self._press_xy
        if not self._is_drag:
            dist = math.hypot(x - px, y - py)
            if dist < self.DRAG_THRESHOLD:
                return
            self._is_drag = True
            # Add the press origin as first drag point
            self._add_point(px, py)
        self._add_point(x, y)

    def _on_release(self, event):
        if self._press_xy is None:
            return
        if not self._is_drag and event.inaxes == self.ax:
            # Single click — place one point
            self._add_point(event.xdata, event.ydata)
        self._press_xy = None
        self._is_drag = False

    def _add_point(self, x, y):
        if x is None or y is None:
            return
        x = max(0, min(x, self.plot_w - 1))
        y = max(0, min(y, self.plot_h - 1))
        # Thin: skip if too close to last point
        if self.points:
            lx, ly = self.points[-1]
            if math.hypot(x - lx, y - ly) < self.THIN_DISTANCE:
                return
        self.points.append((x, y))
        self._redraw()

    # --- Keyboard events ---

    def _on_key(self, event):
        if event.key == "enter":
            self._finish_curve()
            plt.close(self.fig)
        elif event.key == "n":
            self._finish_curve()
            self._start_new_curve()
        elif event.key in ("z", "ctrl+z", "super+z", "cmd+z"):
            if self.points:
                self.points.pop()
                self._redraw()
        elif event.key == "c":
            self.points.clear()
            self._redraw()
        elif event.key in ("q", "escape"):
            self.skipped = True
            plt.close(self.fig)

    # --- Curve management ---

    def _finish_curve(self):
        if not self.points:
            return
        sorted_pts = sorted(self.points, key=lambda p: p[0])
        self.completed.append(sorted_pts)
        n = len(sorted_pts)
        print(f"  Curve {len(self.completed)}: {n} points")

        # Freeze as a completed-curve artist
        ci = (len(self.completed) - 1) % len(CURVE_COLORS)
        self.ax.plot(
            [p[0] for p in sorted_pts], [p[1] for p in sorted_pts],
            "-", color=CURVE_COLORS[ci], linewidth=2, alpha=0.5, zorder=3,
        )
        self.points.clear()

    def _start_new_curve(self):
        ci = len(self.completed) % len(CURVE_COLORS)
        self.dot_artist, = self.ax.plot([], [], ".", color=CURVE_COLORS[ci],
                                        markersize=4, zorder=5)
        self.line_artist, = self.ax.plot([], [], "-", color=CURVE_COLORS[ci],
                                         linewidth=1.5, alpha=0.8, zorder=4)
        self._set_title()
        self._redraw()

    # --- Display ---

    def _redraw(self):
        if not self.points:
            self.dot_artist.set_data([], [])
            self.line_artist.set_data([], [])
        else:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            self.dot_artist.set_data(xs, ys)
            sorted_pts = sorted(self.points, key=lambda p: p[0])
            self.line_artist.set_data(
                [p[0] for p in sorted_pts], [p[1] for p in sorted_pts],
            )
        self.fig.canvas.draw_idle()

    # --- Conversion & output ---

    def _pixels_to_data(self, pts):
        """Convert crop-pixel points to (freq_hz, db) pairs."""
        data = []
        for x, y in pts:
            freq = _px_to_freq(x, self.left, self.right, self.freq_lo, self.freq_hi)
            db = _px_to_db(y, self.top, self.bottom, self.db_top, self.db_bottom)
            data.append([round(freq, 1), round(db, 2)])
        return data

    def run(self):
        """Show the window, block until closed. Returns list of curve dicts or None."""
        plt.show()
        if self.skipped or not self.completed:
            return None
        curves = []
        for pts in self.completed:
            curves.append({"points": self._pixels_to_data(pts)})
        return curves


def _prompt_labels(curves):
    """Ask for curve labels if multiple curves were traced."""
    if len(curves) == 1:
        curves[0]["label"] = "main"
        return
    print(f"  {len(curves)} curves traced. Enter a label for each (or Enter to skip):")
    for i, curve in enumerate(curves):
        label = input(f"    Curve {i+1}: ").strip()
        curve["label"] = label if label else f"curve_{i+1}"


def _build_mask_data(img_array, working_ds, guide_curves):
    """Precompute color mask and guide interpolations for corridor masking.

    Returns (full_mask, guide_interps, plot_h, plot_w) where:
      full_mask: boolean array of all color-matched pixels in plot area
      guide_interps: list of arrays, one per curve, giving expected y per column
    """
    left, top, right, bottom = working_ds["plot_bounds"]
    freq_lo, freq_hi = working_ds["freq_range"]
    db_top, db_bottom = working_ds["db_range"]
    color_name = working_ds["color"]
    plot_w = right - left
    plot_h = bottom - top

    plot_rgb = img_array[top:bottom, left:right]

    COLOR_TESTS = {
        "black": lambda rgb: (rgb[:,:,0] < 100) & (rgb[:,:,1] < 100) & (rgb[:,:,2] < 100),
        "blue": lambda rgb: ((rgb[:,:,2] > 80) &
                             (rgb[:,:,2].astype(int) - rgb[:,:,0].astype(int) > 15) &
                             (rgb[:,:,2].astype(int) - rgb[:,:,1].astype(int) > 15)),
        "red": lambda rgb: ((rgb[:,:,0] > 80) &
                            (rgb[:,:,0].astype(int) - rgb[:,:,1].astype(int) > 15) &
                            (rgb[:,:,0].astype(int) - rgb[:,:,2].astype(int) > 15)),
    }

    full_mask = COLOR_TESTS.get(color_name, lambda _: np.zeros((plot_h, plot_w), dtype=bool))(plot_rgb)

    guide_interps = []
    for guide_curve in guide_curves:
        guide_pts = guide_curve["points"]
        guide_px_x, guide_px_y = [], []
        for hz, db in guide_pts:
            t_x = math.log10(hz / freq_lo) / math.log10(freq_hi / freq_lo)
            guide_px_x.append(t_x * plot_w)
            t_y = (db - db_top) / (db_bottom - db_top)
            guide_px_y.append(t_y * plot_h)
        cols = np.arange(plot_w)
        interp_ys = np.interp(cols, guide_px_x, guide_px_y)
        guide_interps.append(interp_ys)

    return full_mask, guide_interps, plot_h, plot_w


def _apply_corridor(full_mask, guide_interp, corridor_px, plot_h, plot_w):
    """Apply corridor to a single guide curve. Returns masked boolean array."""
    # Build corridor bounds per column (vectorized)
    cols = np.arange(plot_w)
    y_lo = np.clip((guide_interp - corridor_px).astype(int), 0, plot_h)
    y_hi = np.clip((guide_interp + corridor_px).astype(int), 0, plot_h)

    corridor_mask = np.zeros((plot_h, plot_w), dtype=bool)
    for c in range(plot_w):
        corridor_mask[y_lo[c]:y_hi[c], c] = True

    return full_mask & corridor_mask


def _mask_to_image(curve_mask, plot_h, plot_w):
    """Convert boolean mask to RGB numpy array (white + red)."""
    img = np.full((plot_h, plot_w, 3), 255, dtype=np.uint8)
    img[curve_mask] = [255, 0, 0]
    return img


class CorridorTuner:
    """Interactive corridor width tuner — adjust how tight the mask is before editing.

    Scroll or Up/Down to adjust corridor width. Enter to accept.
    """

    def __init__(self, full_mask, guide_interp, plot_h, plot_w, slug):
        self.full_mask = full_mask
        self.guide_interp = guide_interp
        self.plot_h = plot_h
        self.plot_w = plot_w

        # Start with a tight corridor
        self.corridor_px = max(5, plot_h // 20)  # ~5% of plot height
        self.done = False

        self.fig, self.ax = plt.subplots(1, 1, figsize=(16, 6))
        self.fig.canvas.manager.set_window_title(f"Corridor: {slug}")

        # Initial render
        masked = _apply_corridor(full_mask, guide_interp, self.corridor_px, plot_h, plot_w)
        self.img_data = _mask_to_image(masked, plot_h, plot_w)
        self.im_artist = self.ax.imshow(self.img_data, aspect="equal")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self._update_title(masked)

        self.fig.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

    def _update_title(self, masked=None):
        px_count = int(np.sum(masked)) if masked is not None else "?"
        self.ax.set_title(
            f"Corridor ±{self.corridor_px}px · scroll/↑↓ to adjust · "
            f"Enter=accept · {px_count} red px",
            fontsize=11, fontweight="bold",
        )

    def _recompute(self):
        masked = _apply_corridor(self.full_mask, self.guide_interp,
                                  self.corridor_px, self.plot_h, self.plot_w)
        self.img_data = _mask_to_image(masked, self.plot_h, self.plot_w)
        self.im_artist.set_data(self.img_data)
        self._update_title(masked)
        self.fig.canvas.draw_idle()

    def _adjust(self, delta):
        self.corridor_px = max(2, self.corridor_px + delta)
        self._recompute()

    def _on_scroll(self, event):
        step = max(2, self.corridor_px // 5)
        if event.button == "up":
            self._adjust(step)
        elif event.button == "down":
            self._adjust(-step)

    def _on_key(self, event):
        step = max(2, self.corridor_px // 5)
        if event.key == "enter":
            self.done = True
            plt.close(self.fig)
        elif event.key in ("q", "escape"):
            plt.close(self.fig)
        elif event.key == "up":
            self._adjust(step)
        elif event.key == "down":
            self._adjust(-step)

    def run(self):
        plt.show()
        return self.img_data if self.done else None


def _generate_mask(img_array, working_ds, guide_curves, slug):
    """Generate mask PNGs with interactive corridor tuning.

    Returns list of mask file paths.
    """
    full_mask, guide_interps, plot_h, plot_w = _build_mask_data(
        img_array, working_ds, guide_curves)

    mask_dir = paths.DATASHEET_MASKS
    mask_dir.mkdir(parents=True, exist_ok=True)

    mask_paths = []

    for ci, guide_interp in enumerate(guide_interps):
        # Interactive corridor tuning
        tuner = CorridorTuner(full_mask, guide_interp, plot_h, plot_w, slug)
        result = tuner.run()

        if result is None:
            print(f"  Skipped corridor tuning")
            return []

        # Save mask
        if len(guide_interps) == 1:
            mask_name = f"{slug}.png"
        else:
            mask_name = f"{slug}_{ci + 1}.png"
        mask_path = mask_dir / mask_name
        Image.fromarray(result).save(mask_path)

        red_count = int(np.sum((result[:,:,0] > 180) & (result[:,:,1] < 120)))
        print(f"  Mask: {mask_path.name} ({plot_w}x{plot_h}, {red_count} red pixels)")
        mask_paths.append(mask_path)

    # Save calibration JSON
    cal_path = mask_dir / f"{slug}.json"
    cal = {
        "plot_bounds": working_ds["plot_bounds"],
        "freq_range": working_ds["freq_range"],
        "db_range": working_ds["db_range"],
        "source": "datasheet",
    }
    with open(cal_path, "w") as f:
        json.dump(cal, f, indent=2)

    return mask_paths


class MaskEditor:
    """Interactive mask editor — erase stray pixels from a generated mask.

    Controls:
        Left click/drag  — erase pixels (white out) under brush
        Scroll wheel     — change brush size
        +/-              — change brush size
        Z                — undo last stroke
        Enter            — save and close
        Q/Escape         — discard changes and close

    Zoom/pan: use the matplotlib toolbar buttons (magnifier, arrows).
    """

    def __init__(self, mask_path):
        self.mask_path = mask_path
        self.img = Image.open(mask_path).convert("RGB")
        self.img_array = np.array(self.img)
        self.undo_stack = []  # list of img_array snapshots

        self.brush_size = 8
        self.erasing = False
        self.saved = False
        self._pan_start = None  # for right-click pan

        self.fig, self.ax = plt.subplots(1, 1, figsize=(16, 6))
        # Disable default toolbar to avoid conflicting with our controls
        self.fig.canvas.toolbar.pack_forget() if hasattr(self.fig.canvas.toolbar, 'pack_forget') else None
        self.fig.canvas.manager.set_window_title(f"Mask Editor: {mask_path.name}")
        self.im_artist = self.ax.imshow(self.img_array, aspect="equal")
        self._update_title()
        self.ax.set_xticks([])
        self.ax.set_yticks([])

        # Store full view limits for reset
        h, w = self.img_array.shape[:2]
        self._full_xlim = (-0.5, w - 0.5)
        self._full_ylim = (h - 0.5, -0.5)

        # Brush cursor (circle)
        self.cursor = plt.Circle((0, 0), self.brush_size, fill=False,
                                  color="blue", linewidth=1, visible=False)
        self.ax.add_patch(self.cursor)

        self.fig.canvas.mpl_connect("button_press_event", self._on_press)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig.canvas.mpl_connect("button_release_event", self._on_release)
        self.fig.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

    def _update_title(self):
        red_count = np.sum((self.img_array[:,:,0] > 180) &
                           (self.img_array[:,:,1] < 120) &
                           (self.img_array[:,:,2] < 120))
        self.ax.set_title(
            f"brush={self.brush_size}px · scroll=size · ⌘scroll=zoom · "
            f"right-drag=pan · R=reset · Z=undo · Enter=save · {red_count} px",
            fontsize=10,
        )

    def _erase_at(self, x, y):
        if x is None or y is None:
            return
        h, w = self.img_array.shape[:2]
        x, y = int(x), int(y)
        r = self.brush_size
        y_lo = max(0, y - r)
        y_hi = min(h, y + r + 1)
        x_lo = max(0, x - r)
        x_hi = min(w, x + r + 1)

        # Build a distance mask for the brush circle using numpy
        ys = np.arange(y_lo, y_hi)
        xs = np.arange(x_lo, x_hi)
        if len(ys) == 0 or len(xs) == 0:
            return
        yy, xx = np.meshgrid(ys, xs, indexing='ij')
        circle = (xx - x) ** 2 + (yy - y) ** 2 <= r ** 2
        self.img_array[y_lo:y_hi, x_lo:x_hi][circle] = [255, 255, 255]
        self._dirty = True

    def _refresh(self):
        if getattr(self, '_dirty', False):
            self.im_artist.set_data(self.img_array)
            self._dirty = False
        self.fig.canvas.draw_idle()

    def _on_press(self, event):
        if event.inaxes != self.ax:
            return
        # Right click = start pan
        if event.button == 3:
            self._pan_start = (event.xdata, event.ydata)
            return
        # Left click = erase
        if event.button != 1:
            return
        self.undo_stack.append(self.img_array.copy())
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.erasing = True
        self._erase_at(event.xdata, event.ydata)
        self._refresh()

    def _on_motion(self, event):
        # Pan with right-click drag (skip cursor update for performance)
        if self._pan_start and event.inaxes == self.ax and event.xdata and event.ydata:
            dx = self._pan_start[0] - event.xdata
            dy = self._pan_start[1] - event.ydata
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            self.ax.set_xlim(xlim[0] + dx, xlim[1] + dx)
            self.ax.set_ylim(ylim[0] + dy, ylim[1] + dy)
            self.fig.canvas.draw_idle()
            return

        if self.erasing and event.inaxes == self.ax:
            self.cursor.center = (event.xdata, event.ydata)
            self.cursor.set_visible(True)
            self._erase_at(event.xdata, event.ydata)
            self._refresh()
            return

        # Only update cursor when not doing anything intensive
        if event.inaxes == self.ax:
            self.cursor.center = (event.xdata or 0, event.ydata or 0)
            self.cursor.set_radius(self.brush_size)
            self.cursor.set_visible(True)
        else:
            self.cursor.set_visible(False)
        self.fig.canvas.draw_idle()

    def _on_release(self, event):
        if event.button == 3:
            self._pan_start = None
            return
        if self.erasing:
            self.erasing = False
            self._update_title()
            self._refresh()

    def _zoom(self, event, factor):
        """Zoom in toward cursor, zoom out toward image center."""
        if event.inaxes != self.ax:
            return

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        cur_w = xlim[1] - xlim[0]
        cur_h = ylim[0] - ylim[1]  # inverted for images

        full_w = self._full_xlim[1] - self._full_xlim[0]
        full_h = self._full_ylim[0] - self._full_ylim[1]

        new_w = cur_w * factor
        new_h = cur_h * factor

        # Clamp: don't zoom out past full image
        if new_w >= full_w or new_h >= full_h:
            self.ax.set_xlim(self._full_xlim)
            self.ax.set_ylim(self._full_ylim)
            self._refresh()
            return

        if factor < 1:
            # Zoom IN: keep the cursor point fixed on screen.
            # The cursor position should map to the same pixel before and after.
            cx, cy = event.xdata, event.ydata
            # How far (0-1) is the cursor within the current view?
            fx = (cx - xlim[0]) / cur_w
            fy = (cy - ylim[1]) / cur_h  # ylim[1] is the top (smaller y)
            self.ax.set_xlim(cx - fx * new_w, cx + (1 - fx) * new_w)
            self.ax.set_ylim(cy + (1 - fy) * new_h, cy - fy * new_h)
        else:
            # Zoom OUT: same logic — keep cursor point fixed on screen
            cx, cy = event.xdata, event.ydata
            fx = (cx - xlim[0]) / cur_w
            fy = (cy - ylim[1]) / cur_h
            self.ax.set_xlim(cx - fx * new_w, cx + (1 - fx) * new_w)
            self.ax.set_ylim(cy + (1 - fy) * new_h, cy - fy * new_h)

        self._refresh()

    def _on_scroll(self, event):
        # Ctrl/Cmd + scroll = zoom
        if event.key in ("control", "ctrl+control", "super", "cmd"):
            if event.button == "up":
                self._zoom(event, 0.7)  # zoom in
            elif event.button == "down":
                self._zoom(event, 1.4)  # zoom out
            return

        # Plain scroll = brush size (proportional steps)
        step = max(3, self.brush_size // 3)
        if event.button == "up":
            self.brush_size = min(200, self.brush_size + step)
        elif event.button == "down":
            self.brush_size = max(1, self.brush_size - step)
        self.cursor.set_radius(self.brush_size)
        self._update_title()
        self._refresh()

    def _on_key(self, event):
        if event.key == "enter":
            self._save()
            plt.close(self.fig)
        elif event.key in ("q", "escape"):
            plt.close(self.fig)
        elif event.key in ("z", "ctrl+z", "super+z", "cmd+z") and self.undo_stack:
            self.img_array = self.undo_stack.pop()
            self.im_artist.set_data(self.img_array)
            self._update_title()
            self.fig.canvas.draw_idle()
        elif event.key == "+":
            self.brush_size = min(80, self.brush_size + 2)
            self._update_title()
            self._refresh()
        elif event.key == "-":
            self.brush_size = max(1, self.brush_size - 2)
            self._update_title()
            self._refresh()
        elif event.key == "r":
            self.ax.set_xlim(self._full_xlim)
            self.ax.set_ylim(self._full_ylim)
            self._refresh()

    def _save(self):
        out = Image.fromarray(self.img_array)
        out.save(self.mask_path)
        self.saved = True
        red_count = np.sum((self.img_array[:,:,0] > 180) &
                           (self.img_array[:,:,1] < 120) &
                           (self.img_array[:,:,2] < 120))
        print(f"  Saved cleaned mask: {self.mask_path.name} ({red_count} red pixels)")

    def run(self):
        plt.show()
        return self.saved


def _load_atk_data(slug, mic_config):
    """Load ATK lab CSV if available. Returns (freqs, dbs) or None."""
    if not mic_config.get("has_atk"):
        return None
    atk_path = paths.atk_original(slug)
    if not atk_path.exists():
        return None
    freqs, dbs = [], []
    with open(atk_path) as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 2:
                try:
                    freqs.append(float(parts[0]))
                    dbs.append(float(parts[1]))
                except ValueError:
                    continue
    if not freqs:
        return None
    # Normalize: center at 1kHz = 0dB
    arr_f, arr_d = np.array(freqs), np.array(dbs)
    ref_db = np.interp(1000, arr_f, arr_d)
    arr_d -= ref_db
    return arr_f.tolist(), arr_d.tolist()


def _load_existing_digitized(slug):
    """Load previously digitized RH/mask data if available. Returns list of (freqs, dbs) or None."""
    dig_path = paths.find_curve(slug)
    if dig_path is None:
        return None
    with open(dig_path) as f:
        data = json.load(f)
    curves_section = data.get("curves", {}).get("single", {}).get("curves", [])
    if not curves_section:
        return None
    # Only return if this wasn't already a guided result
    result = []
    for c in curves_section:
        if c.get("source") == "guided":
            continue
        pts = c.get("data", [])
        if pts:
            result.append(([p["hz"] for p in pts], [p["db"] for p in pts]))
    return result if result else None


def _show_comparison(slug, mic_config, ds_config, guide_data):
    """Digitize with guide and show comparison plot. Returns the results."""
    ds_path = paths.datasheet_original(slug)
    results = digitize_guided(slug, ds_config, guide_data, paths.DATASHEET_ORIGINALS)
    curve_list = _results_to_curve_list(results)

    if not curve_list:
        print("  WARNING: no curves extracted")
        return results

    # Load reference data
    atk = _load_atk_data(slug, mic_config)
    existing = _load_existing_digitized(slug)

    # Build comparison: original image (top) + all curves (bottom)
    src = np.array(Image.open(ds_path).convert("RGB"))
    left, top, right, bottom = ds_config["plot_bounds"]
    freq_lo, freq_hi = ds_config["freq_range"]
    db_top, db_bottom = ds_config["db_range"]
    cropped = src[top:bottom, left:right]

    fig, (ax_orig, ax_dig) = plt.subplots(2, 1, figsize=(14, 8),
                                           gridspec_kw={"height_ratios": [1, 1.2]})
    fig.canvas.manager.set_window_title(f"Result: {slug}")

    ax_orig.imshow(cropped, aspect="auto")
    ax_orig.set_title(f"{slug} — original datasheet", fontsize=12, fontweight="bold")
    ax_orig.set_xticks([])
    ax_orig.set_yticks([])

    # 1) Guide trace — thin, background, low visibility
    for i, gc in enumerate(guide_data["curves"]):
        gfreqs = [p[0] for p in gc["points"]]
        gdbs = [p[1] for p in gc["points"]]
        ax_dig.semilogx(gfreqs, gdbs, color="#cccccc", linewidth=1, linestyle="--",
                        alpha=0.5, label=f"guide trace", zorder=1)

    # 2) Existing RH/mask digitized — if available
    if existing:
        for i, (ef, ed) in enumerate(existing):
            lbl = "RH/mask digitized" if i == 0 else None
            ax_dig.semilogx(ef, ed, color="#ffaa00", linewidth=2.5, alpha=0.7,
                            linestyle="-.", label=lbl, zorder=2)

    # 3) ATK lab measurement — if available (gold standard)
    if atk:
        ax_dig.semilogx(atk[0], atk[1], color="#00bb00", linewidth=3, alpha=0.85,
                        label="ATK lab measurement", zorder=3)

    # 4) Guided digitized — bold, prominent, on top
    dig_colors = ["#dd0000", "#0044dd", "#dd00dd", "#dd6600"]
    for i, curve in enumerate(curve_list):
        pts = curve["data"]
        freqs = [p["hz"] for p in pts]
        dbs = [p["db"] for p in pts]
        label = f"guided digitized #{i} ({len(pts)} pts)"
        ax_dig.semilogx(freqs, dbs, color=dig_colors[i % len(dig_colors)],
                        linewidth=3.5, label=label, zorder=4)

    ax_dig.set_xlim(freq_lo, freq_hi)
    pad = abs(db_top - db_bottom) * 0.1
    ax_dig.set_ylim(min(db_top, db_bottom) - pad, max(db_top, db_bottom) + pad)
    ax_dig.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax_dig.set_xlabel("Frequency (Hz)", fontsize=10)
    ax_dig.set_ylabel("dB", fontsize=10)
    ax_dig.set_title("Comparison", fontsize=12, fontweight="bold")
    ax_dig.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax_dig.grid(True, which="both", alpha=0.3)

    plt.tight_layout()

    # Show non-blocking so user can see it while answering the prompt
    plt.ion()
    fig.show()
    fig.canvas.flush_events()

    return results, fig


def _detect_dominant_color(img_array, bounds):
    """Detect the dominant curve color in the plot area.

    Scans for non-gray, non-white, non-black pixels.
    Returns "blue", "red", or "black".
    """
    left, top, right, bottom = bounds
    crop = img_array[top:bottom, left:right].reshape(-1, 3).astype(float)

    # Count saturated pixels (not gray/black/white)
    r, g, b = crop[:, 0], crop[:, 1], crop[:, 2]
    brightness = (r + g + b) / 3
    saturation = np.max(crop, axis=1) - np.min(crop, axis=1)

    # Saturated = not gray, not too dark, not too bright
    sat_mask = (saturation > 40) & (brightness > 30) & (brightness < 230)
    if np.sum(sat_mask) < 20:
        return "black"

    sat_pixels = crop[sat_mask]
    avg_r = np.mean(sat_pixels[:, 0])
    avg_g = np.mean(sat_pixels[:, 1])
    avg_b = np.mean(sat_pixels[:, 2])

    if avg_b > avg_r and avg_b > avg_g:
        return "blue"
    if avg_r > avg_b and avg_r > avg_g:
        return "red"
    return "black"


def _detect_db_range(img_array, bounds):
    """Guess dB range from horizontal gridline count.

    Most datasheets use 5dB or 10dB per gridline.
    Common ranges: ±10 (4 lines), ±15 (6 lines), ±20 (4 or 8 lines), -40 to -90 (dBV).
    Returns (db_top, db_bottom) guess, or None.
    """
    left, top, right, bottom = bounds
    gray = np.mean(img_array, axis=2)
    plot_h = bottom - top

    # Find horizontal gridlines within the plot area
    grid_rows = []
    for y in range(top + 5, bottom - 5):
        row = gray[y, left:right]
        # Gridlines: many pixels with similar low brightness across the row
        dark = np.sum(row < 80)
        light_gray = np.sum((row > 120) & (row < 180))
        if dark > (right - left) * 0.5 or light_gray > (right - left) * 0.5:
            grid_rows.append(y)

    # Cluster adjacent rows
    if not grid_rows:
        return None
    clusters = [[grid_rows[0]]]
    for y in grid_rows[1:]:
        if y - clusters[-1][-1] <= 3:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    gridline_positions = [int(np.mean(c)) for c in clusters]

    n_gridlines = len(gridline_positions)
    if n_gridlines < 2:
        return None

    # Gridline spacing in pixels
    spacings = [gridline_positions[i+1] - gridline_positions[i] for i in range(n_gridlines - 1)]
    median_spacing = np.median(spacings)

    # Common patterns (gridlines = divisions, total_range = divisions * db_per_div):
    # 4 gridlines, 5dB spacing = 20dB total (±10)
    # 6 gridlines, 5dB spacing = 30dB total (e.g. +10 to -20)
    # 4 gridlines, 10dB spacing = 40dB total (±20)
    # 8 gridlines, 5dB spacing = 40dB total
    # 5 gridlines, 10dB spacing = 50dB total (dBV charts)

    # Count how many grid divisions fit in the plot height
    n_divisions = round(plot_h / median_spacing)

    # Guess: most common is 5dB per division for ≤8 divs, 10dB for more
    if n_divisions <= 8:
        db_per_div = 5
    else:
        db_per_div = 10

    total_db = n_divisions * db_per_div

    # Assume symmetric around 0 for relative dB charts
    if total_db <= 40:
        db_top = total_db // 2
        db_bottom = -(total_db // 2)
    else:
        # Probably a dBV chart — can't guess the offset
        return None

    return db_top, db_bottom


def _detect_plot_bounds(img_array):
    """Auto-detect plot area from dark border lines in the image.

    Returns (left, top, right, bottom) pixel coords, or None if detection fails.
    """
    gray = np.mean(img_array, axis=2)
    h, w = gray.shape

    # Find rows/cols with lots of dark pixels (border lines)
    h_lines = [y for y in range(h) if np.sum(gray[y, :] < 60) > w * 0.4]
    v_lines = [x for x in range(w) if np.sum(gray[:, x] < 60) > h * 0.3]

    def cluster(vals, gap=5):
        if not vals:
            return []
        groups = [[vals[0]]]
        for v in vals[1:]:
            if v - groups[-1][-1] <= gap:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [int(np.mean(g)) for g in groups]

    h_bounds = cluster(h_lines)
    v_bounds = cluster(v_lines)

    if len(h_bounds) >= 2 and len(v_bounds) >= 2:
        return v_bounds[0], h_bounds[0], v_bounds[-1], h_bounds[-1]
    return None


def _ask_axis_ranges(slug, ds_config):
    """Ask user for axis ranges, showing defaults from registry if available.

    Returns (freq_lo, freq_hi, db_top, db_bottom).
    """
    # Defaults from registry config
    default_freq = ds_config.get("freq_range", [20, 20000]) if ds_config else [20, 20000]
    default_db = ds_config.get("db_range", [10, -10]) if ds_config else [10, -10]

    print(f"  Axis ranges (read from the image labels):")

    freq_input = input(f"    Freq range [{default_freq[0]}-{default_freq[1]}Hz]: ").strip()
    if freq_input:
        parts = freq_input.replace(",", " ").replace("-", " ").replace("to", " ").split()
        nums = []
        for p in parts:
            p = p.lower().replace("hz", "").replace("k", "000")
            try:
                nums.append(float(p))
            except ValueError:
                continue
        if len(nums) >= 2:
            default_freq = [min(nums), max(nums)]

    db_input = input(f"    dB range (top to bottom) [{default_db[0]} to {default_db[1]}]: ").strip()
    if db_input:
        parts = db_input.replace(",", " ").replace("to", " ").split()
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                continue
        if len(nums) >= 2:
            default_db = [nums[0], nums[1]]  # preserve order: top first, bottom second

    print(f"    → freq: {default_freq[0]}-{default_freq[1]}Hz, dB: {default_db[0]} to {default_db[1]}")
    return default_freq[0], default_freq[1], default_db[0], default_db[1]


def _ask_color(ds_config):
    """Ask user for curve color, with default from registry."""
    default = ds_config.get("color", "black") if ds_config else "black"
    color_input = input(f"    Curve color [{default}]: ").strip().lower()
    return color_input if color_input in ("black", "blue", "red") else default


def _save_guide(slug, curves, freq_range, db_range, plot_bounds, color):
    """Persist guide trace to disk immediately."""
    paths.DATASHEET_GUIDES.mkdir(parents=True, exist_ok=True)
    guide_path = paths.datasheet_guide(slug)
    guide_data = {
        "slug": slug,
        "curves": curves,
        "freq_range": freq_range,
        "db_range": db_range,
        "plot_bounds": plot_bounds,
        "color": color,
    }
    with open(guide_path, "w") as f:
        json.dump(guide_data, f, indent=2)
    print(f"  Guide saved → {guide_path.name}")
    return guide_path, guide_data


def _load_guide(slug):
    """Load existing guide if present. Returns guide_data or None."""
    guide_path = paths.datasheet_guide(slug)
    if not guide_path.exists():
        return None
    with open(guide_path) as f:
        return json.load(f)


def _preview_curve(slug, img, mask_paths, cal_data):
    """Digitize masks and show resulting curve overlaid on datasheet.

    Returns True if user accepts, False to redo masks.
    """
    from digitize import _digitize_mask, _results_to_curve_list

    all_curves = []
    for mp in mask_paths:
        results = _digitize_mask(mp, slug, mp.parent)
        curve_list = _results_to_curve_list(results) if results else []
        if curve_list:
            all_curves.extend(curve_list)

    if not all_curves:
        print("  WARNING: no curves extracted from masks")
        return False

    # Show overlay
    left, top, right, bottom = cal_data["plot_bounds"]
    freq_lo, freq_hi = cal_data["freq_range"]
    db_top, db_bottom = cal_data["db_range"]
    cropped = img[top:bottom, left:right]

    fig, (ax_img, ax_curve) = plt.subplots(2, 1, figsize=(14, 8),
                                            gridspec_kw={"height_ratios": [1, 1.2]})
    fig.canvas.manager.set_window_title(f"Preview: {slug}")

    ax_img.imshow(cropped, aspect="auto")
    ax_img.set_title(f"{slug} — datasheet", fontsize=12, fontweight="bold")
    ax_img.set_xticks([])
    ax_img.set_yticks([])

    colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6"]
    for i, c in enumerate(all_curves):
        pts = c.get("data", [])
        if not pts:
            continue
        freqs = [p["hz"] for p in pts]
        dbs = [p["db"] for p in pts]
        ax_curve.semilogx(freqs, dbs, color=colors[i % len(colors)],
                          linewidth=2, label=f"Curve {i} ({len(pts)} pts)")

    ax_curve.set_xlim(max(10, freq_lo * 0.8), freq_hi * 1.2)
    ax_curve.set_ylim(db_bottom - 2, db_top + 2)
    ax_curve.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax_curve.set_xlabel("Frequency (Hz)")
    ax_curve.set_ylabel("dB")
    ax_curve.set_title(f"Extracted curve(s) — close window to continue", fontsize=11)
    ax_curve.legend(loc="lower right", fontsize=9)
    ax_curve.grid(True, which="both", alpha=0.3)
    ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    visible = [t for t in ticks if freq_lo * 0.8 <= t <= freq_hi * 1.2]
    ax_curve.set_xticks(visible)
    ax_curve.set_xticklabels([f"{t//1000}k" if t >= 1000 else str(t) for t in visible])

    plt.tight_layout()
    plt.ion()
    fig.show()
    fig.canvas.flush_events()

    response = input("  Accept curve? (Y/n/redo-masks): ").strip().lower()
    plt.close(fig)
    plt.ioff()
    return response not in ("n", "no", "redo", "redo-masks")


def guide_mic(slug, mic_config):
    """Run interactive guide tracer for one mic. Returns True if saved.

    Flow:
      1. Check for saved guide → offer resume or retrace
      2. Trace (if needed) → save guide immediately
      3. Generate masks from guide → edit masks → preview curve
      4. If preview looks wrong, redo masks (not trace)
      5. Confirm axis ranges → save calibration → done
    """
    ds = mic_config.get("datasheet", {})

    # Find the datasheet image
    if ds:
        img_path = paths.datasheet_original(slug)
    else:
        candidates = list(paths.DATASHEET_ORIGINALS.glob(f"*{slug}*"))
        if not candidates:
            print(f"  {slug}: no datasheet image found, skipping")
            return False
        img_path = candidates[0]

    if not img_path.exists():
        print(f"  {slug}: datasheet not found: {img_path}")
        return False

    print(f"\n=== {slug} ({mic_config['name']}) ===")
    img = np.array(Image.open(img_path).convert("RGB"))

    # Auto-detect plot bounds
    if ds.get("plot_bounds"):
        plot_bounds = ds["plot_bounds"]
    else:
        detected = _detect_plot_bounds(img)
        if detected:
            plot_bounds = list(detected)
        else:
            h, w = img.shape[:2]
            plot_bounds = [0, 0, w, h]

    # Auto-detect color from image
    if ds.get("color"):
        color_guess = ds["color"]
    else:
        color_guess = _detect_dominant_color(img, plot_bounds)

    # Auto-detect dB range from gridlines
    if ds.get("db_range"):
        db_guess = ds["db_range"]
    else:
        detected_db = _detect_db_range(img, plot_bounds)
        db_guess = list(detected_db) if detected_db else [10, -10]

    freq_guess = ds.get("freq_range", [20, 20000])

    working_ds = {
        "file": img_path.name,
        "color": color_guess,
        "plot_bounds": plot_bounds,
        "freq_range": freq_guess,
        "db_range": db_guess,
    }

    # --- Step 1: Get guide trace (resume or new) ---
    existing_guide = _load_guide(slug)
    curves = None
    guide_data = None

    if existing_guide:
        n_curves = len(existing_guide.get("curves", []))
        n_points = sum(len(c.get("points", [])) for c in existing_guide.get("curves", []))
        print(f"  Found saved guide: {n_curves} curve(s), {n_points} points")

        # Show saved trace overlaid on datasheet so user can judge quality
        guide_bounds = existing_guide.get("plot_bounds", plot_bounds)
        gl, gt, gr, gb = guide_bounds
        guide_freq = existing_guide.get("freq_range", freq_guess)
        guide_db = existing_guide.get("db_range", db_guess)
        cropped = img[gt:gb, gl:gr]

        fig, (ax_img, ax_curve) = plt.subplots(2, 1, figsize=(14, 7),
                                                gridspec_kw={"height_ratios": [1, 1]})
        fig.canvas.manager.set_window_title(f"Saved guide: {slug}")
        ax_img.imshow(cropped, aspect="auto")
        ax_img.set_title(f"{slug} — datasheet", fontsize=11)
        ax_img.set_xticks([])
        ax_img.set_yticks([])

        colors_list = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6"]
        for ci, gc in enumerate(existing_guide.get("curves", [])):
            pts = gc.get("points", [])
            if pts:
                gfreqs = [p[0] for p in pts]
                gdbs = [p[1] for p in pts]
                label_text = gc.get("label", f"Curve {ci}")
                ax_curve.semilogx(gfreqs, gdbs, color=colors_list[ci % len(colors_list)],
                                  linewidth=2, label=f"{label_text} ({len(pts)} pts)")

        ax_curve.set_xlim(max(10, guide_freq[0] * 0.8), guide_freq[1] * 1.2)
        ax_curve.set_ylim(guide_db[1] - 2, guide_db[0] + 2)
        ax_curve.axhline(0, color="gray", linewidth=0.5, linestyle="--")
        ax_curve.set_xlabel("Frequency (Hz)")
        ax_curve.set_ylabel("dB")
        ax_curve.set_title("Saved guide trace", fontsize=11)
        ax_curve.legend(loc="lower right", fontsize=9)
        ax_curve.grid(True, which="both", alpha=0.3)
        plt.tight_layout()
        plt.ion()
        fig.show()
        fig.canvas.flush_events()

        choice = input("  Resume from saved guide, retrace, or skip? (R/retrace/skip): ").strip().lower()
        plt.close(fig)
        plt.ioff()
        if choice in ("skip", "s"):
            print(f"  Skipped")
            return False
        elif choice in ("retrace", "t"):
            existing_guide = None  # fall through to tracing
        else:
            # Resume: use saved guide data
            curves = existing_guide["curves"]
            guide_data = existing_guide
            # Update working_ds from saved guide (may have confirmed axis ranges)
            if "plot_bounds" in existing_guide:
                plot_bounds = existing_guide["plot_bounds"]
                working_ds["plot_bounds"] = plot_bounds
            if "freq_range" in existing_guide:
                freq_guess = existing_guide["freq_range"]
                working_ds["freq_range"] = freq_guess
            if "db_range" in existing_guide:
                db_guess = existing_guide["db_range"]
                working_ds["db_range"] = db_guess
            if "color" in existing_guide:
                color_guess = existing_guide["color"]
                working_ds["color"] = color_guess

    if curves is None:
        # New trace
        tracer = GuideTracer(img, slug, working_ds)
        curves = tracer.run()

        if curves is None:
            print(f"  Skipped")
            return False

        _prompt_labels(curves)

        # Save guide immediately — the human work is preserved
        _, guide_data = _save_guide(slug, curves, freq_guess, db_guess,
                                     plot_bounds, color_guess)

    # --- Step 2: Generate masks, edit, preview (repeatable loop) ---
    while True:
        mask_paths = _generate_mask(img, working_ds, curves, slug)

        if not mask_paths:
            response = input("  Mask generation failed. Retrace? (Y/n): ").strip().lower()
            if response in ("n", "no"):
                return False
            # Retrace but guide is still saved
            tracer = GuideTracer(img, slug, working_ds)
            curves = tracer.run()
            if curves is None:
                return False
            _prompt_labels(curves)
            _, guide_data = _save_guide(slug, curves, freq_guess, db_guess,
                                         plot_bounds, color_guess)
            continue

        # Mask editor
        all_saved = True
        for mp in mask_paths:
            print(f"\n  Editing {mp.name} — erase stray pixels, Enter to save, Q to redo")
            editor = MaskEditor(mp)
            if not editor.run():
                all_saved = False

        if not all_saved:
            response = input("  Redo masks or retrace? (masks/retrace/skip): ").strip().lower()
            if response in ("skip", "s"):
                return False
            if response in ("retrace", "t"):
                tracer = GuideTracer(img, slug, working_ds)
                curves = tracer.run()
                if curves is None:
                    return False
                _prompt_labels(curves)
                _, guide_data = _save_guide(slug, curves, freq_guess, db_guess,
                                             plot_bounds, color_guess)
            continue  # redo masks

        # --- Step 3: Preview extracted curve ---
        # Save calibration so _digitize_mask can read it
        paths.DATASHEET_MASKS.mkdir(parents=True, exist_ok=True)
        cal_path = paths.DATASHEET_MASKS / f"{slug}.json"
        cal = {
            "plot_bounds": plot_bounds,
            "freq_range": freq_guess,
            "db_range": db_guess,
            "source": "datasheet",
        }
        with open(cal_path, "w") as f:
            json.dump(cal, f, indent=2)

        if _preview_curve(slug, img, mask_paths, cal):
            break  # accepted
        else:
            print("  Redoing masks (guide trace is preserved)...")
            continue

    # --- Step 4: Confirm axis ranges ---
    fig_ref, ax_ref = plt.subplots(1, 1, figsize=(14, 7))
    fig_ref.canvas.manager.set_window_title(f"Reference: {slug}")
    ax_ref.imshow(img)
    ax_ref.set_title(f"{slug} — confirm axis ranges from labels", fontsize=12)
    ax_ref.set_xticks([])
    ax_ref.set_yticks([])
    plt.tight_layout()
    plt.ion()
    fig_ref.show()
    fig_ref.canvas.flush_events()

    print(f"\n  Auto-detected: freq={freq_guess[0]}-{freq_guess[1]}Hz, "
          f"dB={db_guess[0]} to {db_guess[1]}")
    freq_lo, freq_hi, db_top, db_bottom = _ask_axis_ranges(slug, {
        "freq_range": freq_guess, "db_range": db_guess,
    })

    plt.close(fig_ref)
    plt.ioff()

    # Update calibration JSON with confirmed values
    cal = {
        "plot_bounds": plot_bounds,
        "freq_range": [freq_lo, freq_hi],
        "db_range": [db_top, db_bottom],
        "source": "datasheet",
    }
    with open(cal_path, "w") as f:
        json.dump(cal, f, indent=2)

    # Update guide with confirmed axis ranges too
    _save_guide(slug, curves, [freq_lo, freq_hi], [db_top, db_bottom],
                plot_bounds, color_guess)

    print(f"\n  Done! Masks + guide saved. Run:")
    print(f"    python3 tools/curves/manage.py build")
    return True


def main():
    slugs = sys.argv[1:] if len(sys.argv) > 1 else None

    if slugs:
        mics_to_do = {s: MICS[s] for s in slugs if s in MICS}
        missing = [s for s in slugs if s not in MICS]
        if missing:
            print(f"Unknown slugs: {', '.join(missing)}")
    else:
        mics_to_do = {s: m for s, m in MICS.items() if "datasheet" in m}

    print(f"Guide tracer: {len(mics_to_do)} mics")
    print("Close window or press Enter to save, Q to skip\n")

    saved = 0
    for slug, mic in sorted(mics_to_do.items()):
        if guide_mic(slug, mic):
            saved += 1

    print(f"\nDone. {saved} guides saved to {paths.DATASHEET_GUIDES}/")
    if saved:
        print("Run 'python3 tools/curves/manage.py build' to digitize with guides.")


if __name__ == "__main__":
    main()
