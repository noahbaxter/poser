import pytest
import numpy as np
from pedalboard import load_plugin


# =============================================================================
# NaN/Inf Defense Tests
# =============================================================================

def test_nan_input_produces_finite_output(plugin_path):
    """Plugin should handle NaN input gracefully."""
    plugin = load_plugin(plugin_path)
    plugin.gain_db = 0.0

    input_audio = np.array([[np.nan, 0.5, np.nan, -0.5, np.nan]], dtype=np.float32)
    output = plugin.process(input_audio, 44100)

    assert np.all(np.isfinite(output)), "Output contains NaN or Inf values"


def test_inf_input_produces_finite_output(plugin_path):
    """Plugin should handle Inf input gracefully."""
    plugin = load_plugin(plugin_path)
    plugin.gain_db = 0.0

    input_audio = np.array([[np.inf, 0.5, -np.inf, -0.5, np.inf]], dtype=np.float32)
    output = plugin.process(input_audio, 44100)

    assert np.all(np.isfinite(output)), "Output contains NaN or Inf values"


def test_mixed_bad_values_produce_finite_output(plugin_path):
    """Plugin should handle mixed NaN/Inf input gracefully."""
    plugin = load_plugin(plugin_path)
    plugin.gain_db = 6.0

    input_audio = np.array([[np.nan, np.inf, -np.inf, 0.5, np.nan]], dtype=np.float32)
    output = plugin.process(input_audio, 44100)

    assert np.all(np.isfinite(output)), "Output contains NaN or Inf values"


# =============================================================================
# Silence / Noise Floor Tests
# =============================================================================

def test_silence_in_silence_out(plugin_path):
    """Plugin should not add noise to silent input."""
    plugin = load_plugin(plugin_path)
    plugin.gain_db = 0.0

    # 1 second of silence
    input_audio = np.zeros((1, 44100), dtype=np.float32)
    output = plugin.process(input_audio, 44100)

    # Output should be silent (or very close to it)
    max_output = np.max(np.abs(output))
    assert max_output < 1e-6, f"Plugin added noise to silence: max amplitude = {max_output}"


def test_silence_with_gain_stays_silent(plugin_path):
    """Applying gain to silence should still produce silence."""
    plugin = load_plugin(plugin_path)
    plugin.gain_db = 12.0  # +12dB

    input_audio = np.zeros((1, 44100), dtype=np.float32)
    output = plugin.process(input_audio, 44100)

    max_output = np.max(np.abs(output))
    assert max_output < 1e-6, f"Gain on silence produced noise: max amplitude = {max_output}"


# =============================================================================
# Parameter Sweep Tests (crash/stability)
# =============================================================================

def test_parameter_sweep_no_crash(plugin_path):
    """Sweeping parameters through full range should not crash."""
    plugin = load_plugin(plugin_path)

    # Generate test signal
    t = np.linspace(0, 0.1, 4410, dtype=np.float32)
    input_audio = np.sin(2 * np.pi * 440 * t).reshape(1, -1)

    # Sweep gain from min to max
    gain_values = np.linspace(-60.0, 12.0, 20)
    for gain in gain_values:
        plugin.gain_db = float(gain)
        output = plugin.process(input_audio.copy(), 44100)
        assert output is not None, f"Plugin returned None at gain={gain}"
        assert np.all(np.isfinite(output)), f"Plugin produced non-finite output at gain={gain}"


def test_extreme_parameter_values(plugin_path):
    """Plugin should handle extreme parameter values without crashing."""
    plugin = load_plugin(plugin_path)

    t = np.linspace(0, 0.1, 4410, dtype=np.float32)
    input_audio = np.sin(2 * np.pi * 440 * t).reshape(1, -1)

    # Test at parameter limits
    plugin.gain_db = -60.0  # Minimum
    output_min = plugin.process(input_audio.copy(), 44100)
    assert np.all(np.isfinite(output_min))

    plugin = load_plugin(plugin_path)  # Fresh instance
    plugin.gain_db = 12.0  # Maximum
    output_max = plugin.process(input_audio.copy(), 44100)
    assert np.all(np.isfinite(output_max))


# =============================================================================
# Edge Case Tests
# =============================================================================

def test_single_sample_processing(plugin_path):
    """Plugin should handle single-sample buffers."""
    plugin = load_plugin(plugin_path)
    plugin.gain_db = 0.0

    input_audio = np.array([[0.5]], dtype=np.float32)
    output = plugin.process(input_audio, 44100, buffer_size=1)

    assert output.shape == input_audio.shape
    assert np.isfinite(output[0, 0])


def test_stereo_processing(plugin_path):
    """Plugin should handle stereo input correctly."""
    plugin = load_plugin(plugin_path)
    plugin.gain_db = -6.0

    # Stereo: left = sine, right = different sine
    t = np.linspace(0, 0.1, 4410, dtype=np.float32)
    left = np.sin(2 * np.pi * 440 * t)
    right = np.sin(2 * np.pi * 880 * t)
    input_audio = np.stack([left, right]).astype(np.float32)

    output = plugin.process(input_audio, 44100)

    assert output.shape == input_audio.shape, "Stereo shape mismatch"
    assert np.all(np.isfinite(output)), "Stereo output contains non-finite values"
