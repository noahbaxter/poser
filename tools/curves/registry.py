"""Mic registry — the one file to edit when adding or removing mics.

To add a mic:
  1. Add an entry to MICS below
  2. If using a datasheet: add PNG to data/curves/datasheet/originals/{slug}.png
  3. Run: python3 tools/curves/manage.py prepare
  4. Edit masks if needed (multiple curves)
  5. Run: python3 tools/curves/manage.py build

To remove a mic:
  Delete its entry from MICS.
"""

# slug → mic info
# - name:      Display name shown in the plugin UI
# - groups:    List of UI groups this mic belongs to (can appear in multiple)
# - rh_id:     RecordingHacks ID (optional, legacy fallback)
# - has_atk:   True if ATK lab measurement exists (file is atk/originals/{slug}.csv)
# - tag:       Sub-group tag for visual grouping on the ring
# - datasheet: Config for manufacturer datasheet extraction (see below)
#
# datasheet config:
#   color:         "black" | "blue" | "red" (curve line color)
#   plot_bounds:   [left, top, right, bottom] pixel coords of plot area
#   freq_range:    [freq_lo_hz, freq_hi_hz] at left/right plot edges
#   db_range:      [db_top, db_bottom] at top/bottom plot edges
#   min_thickness: optional, min cluster height in px (default: 2 for black, 1 otherwise)
#   curves:        optional list of {label, line_style} for multi-curve extraction
#
# Datasheet PNG is always at data/curves/datasheet/originals/{slug}.png.
# ATK CSV is always at data/curves/atk/originals/{slug}.csv.
#
# To measure plot_bounds: open the PNG, note pixel coords of the plot area corners.
# Use tools/curves/detect_bounds.py for initial estimates, then verify by eye.
#
# Priority: ATK CSV > datasheet > hand-edited masks > RH source image.

MICS = {
    # --- Shure ---
    "sm57": {
        "name": "SM57", "groups": ["Drum", "Guit"],
        "rh_id": "0006", "has_atk": True,
        "datasheet": {
            "color": "black",
            "plot_bounds": [152, 48, 2204, 962],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [10, -10],
        },
    },
    "sm58": {
        "name": "SM58", "groups": ["Vox"],
        "rh_id": "0253", "has_atk": True,
        "datasheet": {
            "color": "black",
            "plot_bounds": [189, 51, 2013, 985],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [20, -20],
        },
    },
    "sm7b": {
        "name": "SM7B", "groups": ["Vox"],
        "rh_id": "0255", "has_atk": True,
        "datasheet": {
            "color": "black",
            "plot_bounds": [194, 61, 1910, 931],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [20, -20],
            # solid = flat response, dashed = presence boost
            "curves": [
                {"label": "flat", "line_style": "solid"},
                {"label": "presence", "line_style": "dashed"},
            ],
        },
    },
    "sm81": {
        "name": "SM81", "groups": ["Drum", "Inst"],
        "rh_id": "0242",
        "datasheet": {
            "color": "black",
            "plot_bounds": [1051, 41, 2036, 998],  # CHECK — right half of image
            "freq_range": [20, 20000],
            "db_range": [10, -10],  # CHECK
            # Multiple rolloff curves — primary is flat (widest), may need mask editing
        },
    },
    "beta-52a": {
        "name": "52A", "groups": ["Kick"],
        "rh_id": "0219",
        "datasheet": {
            "color": "black",
            "plot_bounds": [212, 58, 2054, 1001],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [20, -20],
            # 4 proximity curves (3mm, 25mm, 51mm, 0.06m) — may need mask editing
        },
    },
    "beta-91a": {
        "name": "91A", "groups": ["Kick"],
        "rh_id": "1094",
        "datasheet": {
            "color": "black",
            "plot_bounds": [117, 55, 1513, 773],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [20, -20],
            "curves": [
                {"label": "flat", "line_style": "solid"},
                {"label": "LF contour", "line_style": "dashed"},
            ],
        },
    },
    # --- Sennheiser ---
    "md421": {
        "name": "MD421", "groups": ["Drum", "Guit"],
        "rh_id": "0552",
        "datasheet": {
            "color": "blue",
            "plot_bounds": [188, 142, 2245, 790],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [-40, -90],  # absolute dBV — normalized automatically
            # Multiple bass control curves — may need mask editing
        },
    },
    "e602": {
        "name": "e602", "groups": ["Kick"],
        "rh_id": "1340",
        "datasheet": {
            "color": "blue",
            "plot_bounds": [142, 91, 1864, 727],  # CHECK
            "freq_range": [50, 20000],
            "db_range": [-40, -90],
            "curves": [
                {"label": "1m", "line_style": "solid"},
                {"label": "5cm", "line_style": "dashed"},
            ],
        },
    },
    "e604": {
        "name": "e604", "groups": ["Drum"],
        "rh_id": "1394",
        "datasheet": {
            "color": "blue",
            "plot_bounds": [181, 102, 2093, 811],  # CHECK
            "freq_range": [50, 20000],
            "db_range": [-40, -90],
            "curves": [
                {"label": "1m", "line_style": "solid"},
                {"label": "5cm", "line_style": "dashed"},
            ],
        },
    },
    "e904": {
        "name": "e904", "groups": ["Drum"],
        "rh_id": "1320",
        "datasheet": {
            "color": "blue",
            "plot_bounds": [165, 104, 1888, 742],  # CHECK
            "freq_range": [50, 20000],
            "db_range": [-40, -90],
        },
    },
    "e906": {
        "name": "e906", "groups": ["Guit"],
        "rh_id": "1184",
        "datasheet": {
            "color": "blue",
            "plot_bounds": [160, 88, 2065, 794],  # CHECK
            "freq_range": [50, 20000],
            "db_range": [-40, -80],
            # Two curves (different polar positions)
            "curves": [
                {"label": "0deg", "line_style": "solid"},
                {"label": "variant", "line_style": "solid"},  # both look solid
            ],
        },
    },
    # --- Beyerdynamic ---
    "m88-tg": {
        "name": "M88", "groups": ["Drum", "Vox", "Kick", "Guit"],
        "rh_id": "1009",
        "datasheet": {
            "color": "black",
            "plot_bounds": [135, 80, 2469, 787],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [20, -30],
            # 3 distance curves (2cm, 10cm, 1m) — may need mask editing to separate
        },
    },
    # --- Electro-Voice ---
    "re20": {
        "name": "RE20", "groups": ["Vox", "Kick", "Guit"],
        "rh_id": "0417",
        "datasheet": {
            "color": "black",
            "plot_bounds": [154, 37, 1937, 983],  # CHECK — includes 0° and 180° sections
            "freq_range": [20, 20000],
            "db_range": [10, -15],  # CHECK — unusual axis, "5 dB" per division
            # 4 curves (0°/180° × solid/dashed) — likely needs mask editing
        },
    },
    # --- AKG ---
    "c12": {
        "name": "C12", "groups": ["Vox", "Inst"],
        "rh_id": "0912",
        # No datasheet available
    },
    "c414": {
        "name": "C414", "groups": ["Vox", "Drum", "Inst"],
        "rh_id": "0307", "has_atk": True,
        "datasheet": {
            "color": "black",
            "plot_bounds": [140, 52, 1255, 452],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [20, -30],
            # Solid = flat, dashed = HPF variants (75Hz, 150Hz)
            "curves": [
                {"label": "flat", "line_style": "solid"},
                {"label": "HPF", "line_style": "dashed"},
            ],
        },
    },
    "c451b": {
        "name": "C451", "groups": ["Drum", "Inst"],
        "rh_id": "0323",
        # No datasheet available
    },
    "d112": {
        "name": "D112", "groups": ["Kick"],
        "rh_id": "0335",
        "datasheet": {
            "color": "red",
            "plot_bounds": [963, 175, 1861, 608],  # CHECK — right half of image
            "freq_range": [20, 20000],
            "db_range": [20, -30],
            "curves": [
                {"label": "far", "line_style": "solid"},
                {"label": "10cm", "line_style": "dashed"},
            ],
        },
    },
    "d12": {
        "name": "D12", "groups": ["Kick"],
        "rh_id": "1550",
        # No datasheet available
    },
    "d2": {
        "name": "D2", "groups": ["Drum"],
        "rh_id": "0479",
        "datasheet": {
            "color": "red",
            "plot_bounds": [63, 99, 1467, 444],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [10, -10],
        },
    },
    "d4": {
        "name": "D4", "groups": ["Drum"],
        "rh_id": "0478", "has_atk": True,
        "datasheet": {
            "color": "red",
            "plot_bounds": [93, 154, 2314, 701],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [10, -10],
        },
    },
    "d6": {
        "name": "D6", "groups": ["Kick"],
        "rh_id": "0567",
        "datasheet": {
            "color": "blue",
            "plot_bounds": [76, 176, 2378, 747],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [10, -10],
        },
    },
    # --- Neumann ---
    "u87": {
        "name": "U87", "groups": ["Vox", "Inst"],
        "rh_id": "0860", "has_atk": True,
        "datasheet": {
            "color": "black",
            "plot_bounds": [180, 55, 2450, 640],  # CHECK — auto-detect failed, estimated
            "freq_range": [20, 20000],
            "db_range": [10, -20],
        },
    },
    "m147": {
        "name": "M147", "groups": ["Vox", "Inst"],
        "rh_id": "1215",
        "datasheet": {
            "color": "black",
            "plot_bounds": [180, 55, 2230, 610],  # CHECK — auto-detect failed, estimated
            "freq_range": [20, 20000],
            "db_range": [10, -20],
            # Multiple lines (solid + dashed tolerance bands)
        },
    },
    "km184": {
        "name": "KM184", "groups": ["Inst"],
        "rh_id": "1091",
        "datasheet": {
            "color": "blue",
            "plot_bounds": [142, 60, 1826, 621],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [10, -20],
        },
    },
    # --- Royer ---
    "r121": {
        "name": "R121", "groups": ["Guit"],
        "rh_id": "0443",
        "datasheet": {
            "color": "black",
            "plot_bounds": [109, 40, 2394, 402],  # CHECK
            "freq_range": [20, 20000],
            "db_range": [10, -10],
        },
    },
    # --- AEA ---
    "r84": {
        "name": "R84", "groups": ["Guit", "Inst"],
        "rh_id": "0429",
        "datasheet": {
            "color": "black",
            "plot_bounds": [160, 33, 2231, 510],  # CHECK — top panel (Front) only
            "freq_range": [20, 20000],
            "db_range": [0, -10],  # CHECK — unusual scale
        },
    },
    # --- Coles ---
    "coles-4038": {
        "name": "4038", "groups": ["Guit", "Inst"],
        "rh_id": "0701",
        "datasheet": {
            "color": "red",
            "plot_bounds": [110, 60, 1900, 830],  # CHECK — colored background, estimated
            "freq_range": [30, 15000],
            "db_range": [20, -20],
        },
    },
}

# Group display order
MIC_GROUPS = ["Kick", "Drum", "Vox", "Guit", "Inst"]
