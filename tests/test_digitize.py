"""Tests for digitized frequency response curve data quality.

Validates the curve JSONs across all source directories — the actual
curves we ship. Tests check that the data hasn't been corrupted by
the digitize → cleanup pipeline.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "curves"))
import paths
from registry import MICS

PNG_DIR = Path("/tmp/poser")


# --- Helpers ---

def load_primary_curve(slug):
    """Load the primary (index 0) curve from the best available source."""
    curve_path = paths.find_curve(slug)
    if curve_path is None:
        pytest.skip(f"No curve data found for {slug}")
    with open(curve_path) as f:
        data = json.load(f)
    curves = data.get("curves", {}).get("single", {}).get("curves", [])
    assert len(curves) > 0, f"No curves in {slug}"
    return curves[0]["data"]


def assert_quality(data, label, min_points=100, max_jump_db=3.0,
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
    assert min(dbs) > -50, f"{label}: min dB {min(dbs):.1f} (> -50 expected)"
    assert max(dbs) < 50, f"{label}: max dB {max(dbs):.1f} (< 50 expected)"

    # Continuity
    for i in range(1, len(data)):
        jump = abs(data[i]["db"] - data[i - 1]["db"])
        assert jump <= max_jump_db, (
            f"{label}: {jump:.1f}dB jump at {data[i]['hz']:.0f}Hz "
            f"(max allowed: {max_jump_db}dB)"
        )


# --- Shipped data quality tests ---

ALL_MICS = [
    (slug, info["name"])
    for slug, info in sorted(MICS.items())
]


@pytest.mark.parametrize(
    "slug,name",
    ALL_MICS,
    ids=[m[1] for m in ALL_MICS],
)
def test_shipped_curve_quality(slug, name):
    """Each shipped curve should meet basic quality thresholds."""
    data = load_primary_curve(slug)
    assert_quality(data, name)


@pytest.mark.parametrize(
    "slug,name",
    ALL_MICS,
    ids=[m[1] for m in ALL_MICS],
)
def test_shipped_curve_smoothness(slug, name):
    """Curves should be smooth — average step between consecutive points < 0.5dB."""
    data = load_primary_curve(slug)
    dbs = [p["db"] for p in data]
    steps = [abs(dbs[i] - dbs[i - 1]) for i in range(1, len(dbs))]
    avg_step = sum(steps) / len(steps)
    assert avg_step < 0.5, (
        f"{name}: avg step {avg_step:.2f}dB (should be < 0.5dB)"
    )


def test_no_duplicate_frequencies():
    """No curve should have duplicate frequency values."""
    for slug, name in ALL_MICS:
        curve_path = paths.find_curve(slug)
        if curve_path is None:
            continue
        with open(curve_path) as f:
            data = json.load(f)
        for curve in data.get("curves", {}).get("single", {}).get("curves", []):
            freqs = [p["hz"] for p in curve["data"]]
            assert len(freqs) == len(set(freqs)), (
                f"{name} ({slug}): has duplicate frequency values"
            )


def test_frequencies_monotonically_increasing():
    """Frequencies should always increase left to right."""
    for slug, name in ALL_MICS:
        curve_path = paths.find_curve(slug)
        if curve_path is None:
            continue
        with open(curve_path) as f:
            data = json.load(f)
        for curve in data.get("curves", {}).get("single", {}).get("curves", []):
            freqs = [p["hz"] for p in curve["data"]]
            for i in range(1, len(freqs)):
                assert freqs[i] > freqs[i - 1], (
                    f"{name}: freq[{i}]={freqs[i]} <= freq[{i-1}]={freqs[i-1]}"
                )
