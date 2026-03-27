#!/usr/bin/env python3
"""Clean up digitized frequency response curves.

Applies per-mic fixes to the raw digitized data:
- Trim unreliable frequency ranges
- Drop junk alternate curves
- Smooth specific noisy regions
- Flag mics that need manual intervention

Run after batch_digitize.py to produce cleaned data.
"""

import json
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO / "data" / "curves" / "digitized"
TMP_DIR = Path("/tmp/poser")

# Per-mic cleanup rules.
# Each entry: (file, curve_key, rules)
# Rules:
#   trim_below_hz: drop points below this frequency
#   trim_above_hz: drop points above this frequency
#   smooth_range: (lo_hz, hi_hz, window) — apply moving average in this range
#   keep_curves: list of curve indices to keep (drop the rest)
#   skip: True = don't touch this mic, it's clean
#   flag: string = needs manual attention, explain why

CLEANUP_RULES = {
    # Clean — no changes needed
    "0006-0253": {"note": "SM58 — clean"},
    "0006-0567": {"note": "Audix D6 — clean"},
    "0006-1091": {"note": "KM184 — clean"},
    "0006-0429": {"note": "AEA R84 — clean"},

    # Minor smoothing
    "0006-0552": {
        "note": "MD421 — small notch around 8-9kHz, extends past 20kHz",
        "smooth_range": (7000, 10000, 7),
        "trim_above_hz": 20000,
    },
    "0006-0701": {
        "note": "Coles 4038 — small glitch around 7-8kHz",
        "smooth_range": (6000, 9000, 7),
    },

    # Drop junk alternate curves
    "0006-1184": {
        "note": "e906 — drop dashed-line fragment, smooth switch-position interference",
        "keep_curves": [0],
        "smooth_range": (5500, 18000, 11),
    },
    "0006-0417": {
        "note": "RE20 — keep primary, drop dotted variant; smooth dotted-line spike",
        "keep_curves": [0],
        "smooth_range": (100, 200, 11),
    },

    # Trim bad regions
    "0006-0307": {
        "note": "C414 — polar patterns overlap below 150Hz, trim",
        "trim_below_hz": 150,
    },
    "0006-0860": {
        "note": "U87 — keep both curves, trim last-point jump",
        "keep_curves": [0, 1],
        "trim_above_hz": 20000,
    },
    "0006-0335": {
        "note": "D112 — primary is main response, #1 is proximity variant",
        "keep_curves": [0, 1],
        "trim_above_hz": 20000,
    },

    # Needs work but usable
    "0006-0255": {
        "note": "SM7B — dashed presence-boost line causes noise 5-10kHz",
        "smooth_range": (4000, 14000, 15),
        "keep_curves": [0],
    },

    # Problematic
    "0006-0219": {
        "note": "Beta 52A — messy below 200Hz from proximity lines",
        "trim_below_hz": 150,
        "smooth_range": (100, 400, 11),
        "keep_curves": [0],
        "flag": "Still noisy — consider sourcing from manufacturer spec sheet",
    },

    # Multi-line mics — keep all valid curves
    "0006-1009": {
        "note": "M88 — 3 proximity curves (2cm, 10cm, 1m), all valid",
    },
    "0006-0323": {
        "note": "C451 — primary + hi-pass filter variants",
        "keep_curves": [0],  # just keep the flat response for now
    },
}


def smooth_region(freqs, dbs, lo_hz, hi_hz, window):
    """Apply moving average smoothing to a specific frequency range."""
    freqs = np.array(freqs)
    dbs = np.array(dbs)
    mask = (freqs >= lo_hz) & (freqs <= hi_hz)

    if not np.any(mask):
        return dbs.tolist()

    indices = np.where(mask)[0]
    half = window // 2
    smoothed = dbs.copy()

    for i in indices:
        lo = max(0, i - half)
        hi = min(len(dbs), i + half + 1)
        smoothed[i] = np.mean(dbs[lo:hi])

    return smoothed.tolist()


def process_mic(file_id, rules):
    """Apply cleanup rules to a single mic's digitized data."""
    json_path = DATA_DIR / f"{file_id}.json"
    if not json_path.exists():
        print(f"  SKIP {file_id}: file not found")
        return

    with open(json_path) as f:
        data = json.load(f)

    modified = False

    for key in ("first", "second"):
        if key not in data["curves"]:
            continue

        info = data["curves"][key]
        curves = info["curves"]

        # Filter curves by index
        if "keep_curves" in rules:
            keep = rules["keep_curves"]
            original_count = len(curves)
            curves = [c for c in curves if c["index"] in keep]
            # Re-index
            for i, c in enumerate(curves):
                c["index"] = i
            if len(curves) != original_count:
                print(f"    Dropped {original_count - len(curves)} alternate curve(s)")
                modified = True

        # Process each curve
        for curve in curves:
            pts = curve["data"]
            freqs = [p["hz"] for p in pts]
            dbs = [p["db"] for p in pts]

            original_len = len(pts)

            # Trim below
            if "trim_below_hz" in rules:
                cutoff = rules["trim_below_hz"]
                mask = [f >= cutoff for f in freqs]
                freqs = [f for f, m in zip(freqs, mask) if m]
                dbs = [d for d, m in zip(dbs, mask) if m]
                if len(freqs) < original_len:
                    print(f"    Trimmed {original_len - len(freqs)} pts below {cutoff}Hz")
                    modified = True

            # Trim above
            if "trim_above_hz" in rules:
                cutoff = rules["trim_above_hz"]
                mask = [f <= cutoff for f in freqs]
                freqs = [f for f, m in zip(freqs, mask) if m]
                dbs = [d for d, m in zip(dbs, mask) if m]

            # Smooth region
            if "smooth_range" in rules:
                lo, hi, window = rules["smooth_range"]
                dbs = smooth_region(freqs, dbs, lo, hi, window)
                print(f"    Smoothed {lo}-{hi}Hz (window={window})")
                modified = True

            # Update curve data
            curve["data"] = [{"hz": round(f, 2), "db": round(d, 2)}
                             for f, d in zip(freqs, dbs)]
            curve["points"] = len(curve["data"])

        info["curves"] = curves
        info["num_curves"] = len(curves)

    if "flag" in rules:
        print(f"    ⚠ FLAG: {rules['flag']}")

    # Write back
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)

    return modified


def main():
    print("Cleaning up digitized curves...\n")

    clean_count = 0
    modified_count = 0
    flagged = []

    for file_id, rules in sorted(CLEANUP_RULES.items()):
        note = rules.get("note", "")
        print(f"{file_id}: {note}")

        if rules.get("skip"):
            print("  (skipped)")
            continue

        # Check if there's anything to do
        has_work = any(k in rules for k in
                       ["trim_below_hz", "trim_above_hz", "smooth_range",
                        "keep_curves", "flag"])

        if not has_work:
            print("  (clean, no changes)")
            clean_count += 1
            continue

        result = process_mic(file_id, rules)
        if result:
            modified_count += 1

        if "flag" in rules:
            flagged.append((file_id, rules["flag"]))

    # Check for files not in our rules
    all_jsons = sorted(DATA_DIR.glob("*.json"))
    known = set(CLEANUP_RULES.keys())
    unknown = [j.stem for j in all_jsons if j.stem not in known]
    if unknown:
        print(f"\nWARNING: {len(unknown)} file(s) not in cleanup rules:")
        for u in unknown:
            print(f"  {u}")

    print(f"\nDone: {clean_count} clean, {modified_count} modified")
    if flagged:
        print(f"\nFlagged for attention:")
        for fid, reason in flagged:
            print(f"  {fid}: {reason}")


if __name__ == "__main__":
    main()
