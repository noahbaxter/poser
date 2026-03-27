"""Tests for digitized frequency response curve data quality.

Validates the cleaned JSON data in data/curves/digitized/ — the actual
curves we ship. Tests check that the data hasn't been corrupted by
the digitize → cleanup pipeline.

Also includes integration tests that re-run the digitizer on source PNGs
to catch regressions in the extraction code itself.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIGITIZED_DIR = REPO_ROOT / "data" / "curves" / "digitized"
PNG_DIR = Path("/tmp/poser")


# --- Helpers ---

def load_primary_curve(file_id, key="second"):
    """Load the primary (index 0) curve from a digitized JSON file."""
    path = DIGITIZED_DIR / f"{file_id}.json"
    if not path.exists():
        pytest.skip(f"Data file not found: {path}")
    with open(path) as f:
        data = json.load(f)
    assert key in data["curves"], f"No '{key}' in {file_id}"
    curves = data["curves"][key]["curves"]
    assert len(curves) > 0, f"No curves in {file_id}/{key}"
    return curves[0]["data"]


def assert_quality(data, label, min_points=400, max_jump_db=3.0,
                   max_start_hz=None, min_end_hz=None):
    """Assert a curve meets quality thresholds."""
    assert len(data) >= min_points, (
        f"{label}: {len(data)} points (need >= {min_points})"
    )

    freqs = [p["hz"] for p in data]
    dbs = [p["db"] for p in data]

    # Frequency range
    if max_start_hz:
        assert freqs[0] <= max_start_hz, (
            f"{label}: starts at {freqs[0]:.0f}Hz (should be <= {max_start_hz}Hz)"
        )
    if min_end_hz:
        assert freqs[-1] >= min_end_hz, (
            f"{label}: ends at {freqs[-1]:.0f}Hz (should be >= {min_end_hz}Hz)"
        )

    # dB sanity
    assert min(dbs) > -25, f"{label}: min dB {min(dbs):.1f} (> -25 expected)"
    assert max(dbs) < 25, f"{label}: max dB {max(dbs):.1f} (< 25 expected)"

    # Continuity
    for i in range(1, len(data)):
        jump = abs(data[i]["db"] - data[i - 1]["db"])
        assert jump <= max_jump_db, (
            f"{label}: {jump:.1f}dB jump at {data[i]['hz']:.0f}Hz "
            f"(max allowed: {max_jump_db}dB)"
        )


# --- Shipped data quality tests ---
# These test the actual JSON files we ship. No digitizer re-run needed.

ALL_MICS = [
    # (file_id, name, expected properties)
    ("0006-0253", "SM58", {"max_start_hz": 60, "min_end_hz": 12000}),
    ("0006-0255", "SM7B", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-0307", "C414", {"max_start_hz": 200, "min_end_hz": 15000}),  # trimmed below 150Hz
    ("0006-0323", "C451", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-0335", "D112", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-0417", "RE20", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-0429", "R84", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-0552", "MD421", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-0567", "Audix D6", {"max_start_hz": 60, "min_end_hz": 12000}),
    ("0006-0701", "Coles 4038", {"max_start_hz": 60, "min_end_hz": 10000}),
    ("0006-0860", "U87", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-1009", "M88", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-1091", "KM184", {"max_start_hz": 60, "min_end_hz": 15000}),
    ("0006-1184", "e906", {"max_start_hz": 60, "min_end_hz": 12000}),
]


@pytest.mark.parametrize(
    "file_id,name,props",
    ALL_MICS,
    ids=[m[1] for m in ALL_MICS],
)
def test_shipped_curve_quality(file_id, name, props):
    """Each shipped curve should meet basic quality thresholds."""
    data = load_primary_curve(file_id)
    assert_quality(data, name, **props)


@pytest.mark.parametrize(
    "file_id,name,props",
    ALL_MICS,
    ids=[m[1] for m in ALL_MICS],
)
def test_shipped_curve_smoothness(file_id, name, props):
    """Curves should be smooth — average step between consecutive points < 0.5dB."""
    _ = props  # required by parametrize but unused here
    data = load_primary_curve(file_id)
    dbs = [p["db"] for p in data]
    steps = [abs(dbs[i] - dbs[i - 1]) for i in range(1, len(dbs))]
    avg_step = sum(steps) / len(steps)
    assert avg_step < 0.5, (
        f"{name}: avg step {avg_step:.2f}dB (should be < 0.5dB)"
    )


def test_no_duplicate_frequencies():
    """No curve should have duplicate frequency values."""
    for file_id, name, _ in ALL_MICS:
        path = DIGITIZED_DIR / f"{file_id}.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        for key in ("first", "second"):
            if key not in data["curves"]:
                continue
            for curve in data["curves"][key]["curves"]:
                freqs = [p["hz"] for p in curve["data"]]
                assert len(freqs) == len(set(freqs)), (
                    f"{name} ({file_id}/{key}): has duplicate frequency values"
                )


def test_frequencies_monotonically_increasing():
    """Frequencies should always increase left to right."""
    for file_id, name, _ in ALL_MICS:
        path = DIGITIZED_DIR / f"{file_id}.json"
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        for key in ("first", "second"):
            if key not in data["curves"]:
                continue
            for curve in data["curves"][key]["curves"]:
                freqs = [p["hz"] for p in curve["data"]]
                for i in range(1, len(freqs)):
                    assert freqs[i] > freqs[i - 1], (
                        f"{name}: freq[{i}]={freqs[i]} <= freq[{i-1}]={freqs[i-1]}"
                    )


# --- Mic-specific sanity checks ---

def test_sm58_presence_peak():
    """SM58 should have a presence peak between 2-10kHz."""
    data = load_primary_curve("0006-0253")
    peak = max(data, key=lambda p: p["db"])
    assert 2000 <= peak["hz"] <= 10000, (
        f"SM58 peak at {peak['hz']:.0f}Hz (expected 2-10kHz)"
    )


def test_d6_bass_boost():
    """Audix D6 should have significant bass boost below 200Hz."""
    data = load_primary_curve("0006-0567")
    low = [p["db"] for p in data if p["hz"] < 200]
    mid = [p["db"] for p in data if 500 <= p["hz"] <= 2000]
    assert low and mid
    avg_low = sum(low) / len(low)
    avg_mid = sum(mid) / len(mid)
    assert avg_low > avg_mid, (
        f"D6 bass ({avg_low:.1f}dB) should be louder than mids ({avg_mid:.1f}dB)"
    )


def test_r84_ribbon_rolloff():
    """AEA R84 should roll off in the high frequencies (ribbon character)."""
    data = load_primary_curve("0006-0429")
    mid = [p["db"] for p in data if 500 <= p["hz"] <= 2000]
    high = [p["db"] for p in data if p["hz"] > 10000]
    assert mid and high
    avg_mid = sum(mid) / len(mid)
    avg_high = sum(high) / len(high)
    assert avg_high < avg_mid, (
        f"R84 HF ({avg_high:.1f}dB) should be below mids ({avg_mid:.1f}dB)"
    )


def test_c414_trimmed_below_150():
    """C414 data should start at 150Hz (polar pattern overlap trimmed)."""
    data = load_primary_curve("0006-0307")
    assert data[0]["hz"] >= 140, (
        f"C414 starts at {data[0]['hz']:.0f}Hz (should be >= 140Hz, trimmed)"
    )
