"""Tests for cutagent.audio_ops — mix, volume, replace, normalize."""

import os

import pytest
from cutagent.audio_ops import mix_audio, adjust_volume, replace_audio, normalize_audio
from cutagent.errors import CutAgentError


class TestMixAudio:
    def test_mix_basic(self, test_video, test_audio_file, output_dir):
        out = os.path.join(output_dir, "mixed.mp4")
        result = mix_audio(test_video, test_audio_file, out, mix_level=0.3)
        assert result.success
        assert os.path.exists(out)
        assert result.duration_seconds is not None

    def test_mix_low_level(self, test_video, test_audio_file, output_dir):
        out = os.path.join(output_dir, "mixed_low.mp4")
        result = mix_audio(test_video, test_audio_file, out, mix_level=0.1)
        assert result.success
        assert os.path.exists(out)

    def test_mix_invalid_level_too_high(self, test_video, test_audio_file, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            mix_audio(test_video, test_audio_file, out, mix_level=1.5)
        assert exc_info.value.code == "INVALID_MIX_LEVEL"

    def test_mix_invalid_level_negative(self, test_video, test_audio_file, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            mix_audio(test_video, test_audio_file, out, mix_level=-0.1)
        assert exc_info.value.code == "INVALID_MIX_LEVEL"


class TestAdjustVolume:
    def test_volume_boost(self, test_video, output_dir):
        out = os.path.join(output_dir, "louder.mp4")
        result = adjust_volume(test_video, out, gain_db=6.0)
        assert result.success
        assert os.path.exists(out)

    def test_volume_reduce(self, test_video, output_dir):
        out = os.path.join(output_dir, "quieter.mp4")
        result = adjust_volume(test_video, out, gain_db=-10.0)
        assert result.success
        assert os.path.exists(out)

    def test_volume_invalid_too_high(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            adjust_volume(test_video, out, gain_db=100.0)
        assert exc_info.value.code == "INVALID_GAIN_VALUE"

    def test_volume_invalid_too_low(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            adjust_volume(test_video, out, gain_db=-100.0)
        assert exc_info.value.code == "INVALID_GAIN_VALUE"


class TestReplaceAudio:
    def test_replace_basic(self, test_video, test_audio_file, output_dir):
        out = os.path.join(output_dir, "replaced.mp4")
        result = replace_audio(test_video, test_audio_file, out)
        assert result.success
        assert os.path.exists(out)


class TestNormalizeAudio:
    def test_normalize_default(self, test_video, output_dir):
        out = os.path.join(output_dir, "normalized.mp4")
        result = normalize_audio(test_video, out)
        assert result.success
        assert os.path.exists(out)

    def test_normalize_custom_lufs(self, test_video, output_dir):
        out = os.path.join(output_dir, "normalized_custom.mp4")
        result = normalize_audio(test_video, out, target_lufs=-23.0)
        assert result.success
        assert os.path.exists(out)

    def test_normalize_invalid_lufs_too_high(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            normalize_audio(test_video, out, target_lufs=0.0)
        assert exc_info.value.code == "INVALID_NORMALIZE_TARGET"

    def test_normalize_invalid_lufs_too_low(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            normalize_audio(test_video, out, target_lufs=-80.0)
        assert exc_info.value.code == "INVALID_NORMALIZE_TARGET"

    def test_normalize_invalid_peak(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            normalize_audio(test_video, out, true_peak_dbtp=5.0)
        assert exc_info.value.code == "INVALID_NORMALIZE_TARGET"
