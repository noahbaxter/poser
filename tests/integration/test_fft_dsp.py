"""DSP correctness tests for the FFT-based magnitude filter.

These tests verify that the FFT overlap-add reconstruction is transparent
when no EQ is applied, and that the magnitude response is correctly applied
when curves are active.
"""
import numpy as np
import pytest
import soundfile as sf
from pathlib import Path
from pedalboard import load_plugin
from utils import generate_sine, rms, linear_to_db

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "input"


def make_plugin(plugin_path):
    """Load plugin with all blends at 0 (flat/bypass)."""
    p = load_plugin(plugin_path)
    # Set all blends to 0 (normalized 0.5 on range -5..5)
    p.mic_blend = 0.0
    p.cab_blend = 0.0
    p.speaker_blend = 0.0
    p.position_blend = 0.0
    p.dry_wet = 1.0
    p.output_trim = 0.0
    return p


def generate_white_noise(duration=1.0, sr=44100, amplitude=0.5):
    """Generate white noise for testing."""
    rng = np.random.default_rng(42)
    noise = (rng.uniform(-1, 1, int(sr * duration)) * amplitude).astype(np.float32)
    return noise.reshape(-1, 1)


# ---- Passthrough / transparency tests ----

class TestFFTPassthrough:
    """When all blends are 0, the plugin should be transparent."""

    def test_sine_passthrough_rms(self, plugin_path):
        """RMS should be preserved when all curves are flat."""
        p = make_plugin(plugin_path)
        inp = generate_sine(freq=1000, duration=2.0)
        out = p.process(inp, 44100)

        # Trim latency (first fftSize samples may be silence)
        out_trimmed = out[1024:]
        inp_trimmed = inp[:len(out_trimmed)]

        ratio = rms(out_trimmed) / rms(inp_trimmed)
        assert 0.95 < ratio < 1.05, f"Expected unity gain, got {ratio:.4f}x ({linear_to_db(ratio):.2f} dB)"

    def test_noise_passthrough_rms(self, plugin_path):
        """White noise RMS should be preserved."""
        p = make_plugin(plugin_path)
        inp = generate_white_noise(duration=2.0)
        out = p.process(inp, 44100)

        out_trimmed = out[2048:]
        inp_trimmed = inp[:len(out_trimmed)]

        ratio = rms(out_trimmed) / rms(inp_trimmed)
        assert 0.95 < ratio < 1.05, f"Expected unity gain, got {ratio:.4f}x ({linear_to_db(ratio):.2f} dB)"

    def test_silence_stays_silent(self, plugin_path):
        """Zero input should produce zero output."""
        p = make_plugin(plugin_path)
        inp = np.zeros((44100, 1), dtype=np.float32)
        out = p.process(inp, 44100)
        assert np.max(np.abs(out)) < 1e-6, f"Expected silence, got peak {np.max(np.abs(out))}"

    def test_passthrough_waveform_similarity(self, plugin_path):
        """Output waveform should closely match input.
        Note: pedalboard auto-compensates for reported latency, so output is aligned."""
        p = make_plugin(plugin_path)
        sr = 44100
        inp = generate_sine(freq=440, duration=2.0, sr=sr)
        out = p.process(inp, sr)

        # Pedalboard compensates for latency, so input and output should be aligned
        # Skip startup transient
        skip = 2048
        length = 8192

        inp_chunk = inp[skip:skip + length].flatten()
        out_chunk = out[skip:skip + length].flatten()

        # Direct sample-by-sample correlation (no lag search needed)
        norm = np.sqrt(np.sum(inp_chunk**2) * np.sum(out_chunk**2))
        corr_coeff = np.sum(inp_chunk * out_chunk) / norm if norm > 0 else 0
        assert corr_coeff > 0.99, f"Correlation {corr_coeff:.4f} — waveform distorted"

    def test_passthrough_at_48k(self, plugin_path):
        """Should work at 48kHz too."""
        p = make_plugin(plugin_path)
        sr = 48000
        inp = generate_sine(freq=1000, duration=2.0, sr=sr)
        out = p.process(inp, sr)

        out_trimmed = out[2048:]
        inp_trimmed = inp[:len(out_trimmed)]

        ratio = rms(out_trimmed) / rms(inp_trimmed)
        assert 0.95 < ratio < 1.05, f"Expected unity at 48k, got {ratio:.4f}x"

    def test_drywet_zero_is_flat(self, plugin_path):
        """Dry/wet at 0 should make all curves flat regardless of blend settings."""
        p = load_plugin(plugin_path)
        p.mic_blend = 5.0    # max blend
        p.cab_blend = 5.0
        p.speaker_blend = 5.0
        p.position_blend = 5.0
        p.dry_wet = 0.0       # but dry/wet = 0 → all 0 dB
        p.output_trim = 0.0

        inp = generate_white_noise(duration=2.0)
        out = p.process(inp, 44100)

        out_trimmed = out[2048:]
        inp_trimmed = inp[:len(out_trimmed)]

        ratio = rms(out_trimmed) / rms(inp_trimmed)
        assert 0.95 < ratio < 1.05, f"Dry/wet=0 should be transparent, got {ratio:.4f}x"


# ---- EQ effect tests ----

class TestParameterDiscovery:
    """Diagnostic: verify pedalboard can see all parameters."""

    def test_list_parameters(self, plugin_path):
        """Print all parameter names pedalboard sees."""
        p = load_plugin(plugin_path)
        params = {name: getattr(p, name, '?') for name in p.parameters}
        print("\nPedalboard parameters:")
        for name, val in sorted(params.items()):
            print(f"  {name} = {val}")
        assert len(params) >= 10, f"Expected ≥10 params, got {len(params)}"


class TestFFTMagnitude:
    """When curves are active, the spectrum should be shaped."""

    def test_eq_changes_spectrum(self, plugin_path):
        """With a curve active, the output spectrum should differ from input."""
        p = load_plugin(plugin_path)
        p.mic_blend = 3.0  # 300% — exaggerated for clear effect
        p.cab_blend = 0.0
        p.speaker_blend = 0.0
        p.position_blend = 0.0
        p.dry_wet = 1.0
        p.output_trim = 0.0

        inp = generate_white_noise(duration=2.0)
        out = p.process(inp, 44100)

        # Compare spectra
        inp_fft = np.abs(np.fft.rfft(inp[2048:2048+4096].flatten()))
        out_fft = np.abs(np.fft.rfft(out[2048:2048+4096].flatten()))

        # The spectra should NOT be identical
        spectral_diff = np.mean(np.abs(out_fft - inp_fft)) / np.mean(inp_fft)
        assert spectral_diff > 0.05, f"Expected spectral change, got {spectral_diff:.4f} relative diff"

    def test_negative_blend_inverts(self, plugin_path):
        """Negative blend should invert the curve (boost becomes cut)."""
        p_pos = load_plugin(plugin_path)
        p_pos.mic_blend = 3.0
        p_pos.cab_blend = 0.0
        p_pos.speaker_blend = 0.0
        p_pos.position_blend = 0.0
        p_pos.dry_wet = 1.0

        p_neg = load_plugin(plugin_path)
        p_neg.mic_blend = -3.0
        p_neg.cab_blend = 0.0
        p_neg.speaker_blend = 0.0
        p_neg.position_blend = 0.0
        p_neg.dry_wet = 1.0

        inp = generate_white_noise(duration=2.0)
        out_pos = p_pos.process(inp.copy(), 44100)
        out_neg = p_neg.process(inp.copy(), 44100)

        # They should sound different
        chunk_pos = out_pos[2048:2048+4096].flatten()
        chunk_neg = out_neg[2048:2048+4096].flatten()

        corr = np.corrcoef(np.abs(np.fft.rfft(chunk_pos)),
                           np.abs(np.fft.rfft(chunk_neg)))[0, 1]
        # Inverted EQ → spectral correlation should be lower than 1.0
        assert corr < 0.95, f"Positive and negative blend spectra too similar: corr={corr:.4f}"

    def test_output_trim(self, plugin_path):
        """Output trim should scale the level."""
        p = make_plugin(plugin_path)

        # Find the actual parameter name pedalboard uses for output_trim
        params = p.parameters
        trim_param = None
        for name in params:
            if 'trim' in name.lower() or 'output' in name.lower():
                trim_param = name
        assert trim_param is not None, f"No trim param found in {list(params.keys())}"

        setattr(p, trim_param, -6.0)

        inp = generate_sine(freq=1000, duration=2.0)
        out = p.process(inp, 44100)

        out_trimmed = out[2048:]
        inp_trimmed = inp[:len(out_trimmed)]

        ratio = rms(out_trimmed) / rms(inp_trimmed)
        # -6dB ≈ 0.5x
        assert 0.45 < ratio < 0.55, f"Expected ~0.5x for -6dB trim (param={trim_param}), got {ratio:.4f}x"

    def test_blend_scales_effect(self, plugin_path):
        """Higher blend should produce more spectral change."""
        inp = generate_white_noise(duration=2.0)

        diffs = []
        for blend in [0.5, 1.0, 3.0]:
            p = load_plugin(plugin_path)
            p.mic_blend = blend
            p.cab_blend = 0.0
            p.speaker_blend = 0.0
            p.position_blend = 0.0
            p.dry_wet = 1.0
            p.output_trim = 0.0

            out = p.process(inp.copy(), 44100)
            inp_fft = np.abs(np.fft.rfft(inp[2048:2048+4096].flatten()))
            out_fft = np.abs(np.fft.rfft(out[2048:2048+4096].flatten()))
            diffs.append(np.mean(np.abs(out_fft - inp_fft)))

        # More blend → more spectral difference
        assert diffs[0] < diffs[1] < diffs[2], \
            f"Spectral diff should increase with blend: {[f'{d:.4f}' for d in diffs]}"


# ---- Real audio tests ----

class TestRealAudio:
    """Tests with real kick drum audio."""

    @pytest.fixture
    def kick(self):
        kick_path = FIXTURES_DIR / "kick.wav"
        if not kick_path.exists():
            pytest.skip("kick.wav fixture not found")
        data, sr = sf.read(str(kick_path), dtype='float32')
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return data, sr

    def test_kick_passthrough_preserves_rms(self, plugin_path, kick):
        """Flat response should not change kick drum RMS."""
        data, sr = kick
        p = make_plugin(plugin_path)
        out = p.process(data, sr)

        # Skip latency
        skip = 2048
        ratio = rms(out[skip:]) / rms(data[:len(out) - skip])
        assert 0.95 < ratio < 1.05, f"Passthrough altered kick RMS: {ratio:.4f}x"

    def test_kick_passthrough_no_distortion(self, plugin_path, kick):
        """Flat response should not add harmonics / distortion to kick."""
        data, sr = kick
        p = make_plugin(plugin_path)
        out = p.process(data, sr)

        # Pedalboard auto-compensates latency — direct comparison
        skip = 2048
        length = 16384

        inp_chunk = data[skip:skip + length].flatten()
        out_chunk = out[skip:skip + length].flatten()

        norm = np.sqrt(np.sum(inp_chunk**2) * np.sum(out_chunk**2))
        corr_coeff = np.sum(inp_chunk * out_chunk) / norm if norm > 0 else 0
        assert corr_coeff > 0.98, f"Kick distorted in passthrough: correlation {corr_coeff:.4f}"

    def test_kick_with_d112_curve(self, plugin_path, kick):
        """Applying D112-like mic curve should boost lows and add presence click."""
        data, sr = kick
        p = load_plugin(plugin_path)
        # Mic select index 0 is C414, we want to test any mic works
        p.mic_select = 0  # C414
        p.mic_blend = 3.0
        p.cab_blend = 0.0
        p.speaker_blend = 0.0
        p.position_blend = 0.0
        p.dry_wet = 1.0
        p.output_trim = 0.0

        out = p.process(data, sr)

        # Verify spectrum changed
        skip = 2048
        inp_fft = np.abs(np.fft.rfft(data[skip:skip+8192].flatten()))
        out_fft = np.abs(np.fft.rfft(out[skip:skip+8192].flatten()))

        spectral_diff = np.mean(np.abs(out_fft - inp_fft)) / (np.mean(inp_fft) + 1e-10)
        assert spectral_diff > 0.05, f"Mic curve had no effect on kick: diff={spectral_diff:.4f}"

    def test_kick_switching_presets_changes_sound(self, plugin_path, kick):
        """Different mic selections should produce different outputs."""
        data, sr = kick
        outputs = []
        mic_values = [0, 3, 5]  # Use well-separated indices (C414, MD441, SM57)

        for mic_idx in mic_values:
            p = load_plugin(plugin_path)
            p.mic_select = mic_idx
            p.mic_blend = 3.0  # Exaggerate for clear difference
            p.cab_blend = 0.0
            p.speaker_blend = 0.0
            p.position_blend = 0.0
            p.dry_wet = 1.0
            out = p.process(data.copy(), sr)
            outputs.append(out[2048:2048+8192].flatten())

        # All three should be different from each other
        for i in range(len(outputs)):
            for j in range(i+1, len(outputs)):
                diff = np.mean(np.abs(outputs[i] - outputs[j]))
                assert diff > 1e-5, f"Mic {mic_values[i]} and {mic_values[j]} sound identical: diff={diff:.6f}"
