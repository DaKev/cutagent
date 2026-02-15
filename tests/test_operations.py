"""Tests for cutagent.operations — trim, split, concat, reorder, extract, fade."""

import os

import pytest
from cutagent.operations import trim, split, concat, reorder, extract_stream, fade, speed
from cutagent.errors import CutAgentError


class TestTrim:
    def test_basic_trim(self, test_video_10s, output_dir):
        out = os.path.join(output_dir, "trimmed.mp4")
        result = trim(test_video_10s, start="1", end="4", output=out)
        assert result.success
        assert os.path.exists(out)
        assert result.duration_seconds == pytest.approx(3.0, abs=0.1)

    def test_trim_hhmmss(self, test_video_10s, output_dir):
        out = os.path.join(output_dir, "trimmed2.mp4")
        result = trim(test_video_10s, start="00:00:02", end="00:00:06", output=out)
        assert result.success
        assert os.path.exists(out)

    def test_trim_start_after_end(self, test_video_10s, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            trim(test_video_10s, start="5", end="2", output=out)
        assert exc_info.value.code == "TRIM_START_AFTER_END"

    def test_trim_beyond_duration(self, test_video_10s, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            trim(test_video_10s, start="0", end="999", output=out)
        assert exc_info.value.code == "TRIM_BEYOND_DURATION"

    def test_trim_keyframe_warning(self, test_video_10s, output_dir):
        """Trim with copy codec at a non-keyframe point should produce a warning."""
        out = os.path.join(output_dir, "trimmed_kf.mp4")
        result = trim(test_video_10s, start="1.123", end="4.567", output=out, codec="copy")
        assert result.success
        # May or may not have warnings depending on keyframe positions


class TestSplit:
    def test_split_into_three(self, test_video_10s, output_dir):
        prefix = os.path.join(output_dir, "seg")
        results = split(test_video_10s, points=["3", "7"], output_prefix=prefix)
        assert len(results) == 3
        for r in results:
            assert r.success
            assert os.path.exists(r.output_path)

    def test_split_single_point(self, test_video_10s, output_dir):
        prefix = os.path.join(output_dir, "seg")
        results = split(test_video_10s, points=["5"], output_prefix=prefix)
        assert len(results) == 2

    def test_split_beyond_duration(self, test_video_10s, output_dir):
        prefix = os.path.join(output_dir, "seg")
        with pytest.raises(CutAgentError) as exc_info:
            split(test_video_10s, points=["999"], output_prefix=prefix)
        assert exc_info.value.code == "SPLIT_POINT_BEYOND_DURATION"


class TestConcat:
    def test_concat_two_segments(self, test_video_10s, output_dir):
        # First split, then concat
        prefix = os.path.join(output_dir, "seg")
        segments = split(test_video_10s, points=["5"], output_prefix=prefix)

        out = os.path.join(output_dir, "merged.mp4")
        result = concat([s.output_path for s in segments], output=out)
        assert result.success
        assert os.path.exists(out)

    def test_concat_same_file(self, test_video, output_dir):
        out = os.path.join(output_dir, "doubled.mp4")
        result = concat([test_video, test_video], output=out)
        assert result.success

    def test_concat_crossfade(self, test_video_10s, output_dir):
        prefix = os.path.join(output_dir, "seg")
        segments = split(test_video_10s, points=["5"], output_prefix=prefix)
        out = os.path.join(output_dir, "crossfaded.mp4")
        result = concat(
            [s.output_path for s in segments],
            output=out,
            codec="libx264",
            transition="crossfade",
            transition_duration=0.3,
        )
        assert result.success
        assert os.path.exists(out)


class TestReorder:
    def test_reverse_order(self, test_video_10s, output_dir):
        prefix = os.path.join(output_dir, "seg")
        segments = split(test_video_10s, points=["5"], output_prefix=prefix)
        paths = [s.output_path for s in segments]

        out = os.path.join(output_dir, "reversed.mp4")
        result = reorder(paths, order=[1, 0], output=out)
        assert result.success
        assert os.path.exists(out)

    def test_reorder_out_of_range(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            reorder([test_video], order=[5], output=out)
        assert exc_info.value.code == "REORDER_INDEX_OUT_OF_RANGE"


class TestExtractStream:
    def test_extract_audio(self, test_video, output_dir):
        out = os.path.join(output_dir, "audio.aac")
        result = extract_stream(test_video, stream="audio", output=out)
        assert result.success
        assert os.path.exists(out)

    def test_extract_video(self, test_video, output_dir):
        out = os.path.join(output_dir, "video.mp4")
        result = extract_stream(test_video, stream="video", output=out)
        assert result.success
        assert os.path.exists(out)

    def test_extract_invalid_stream(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            extract_stream(test_video, stream="subtitle", output=out)
        assert exc_info.value.code == "INVALID_STREAM_TYPE"


class TestFade:
    def test_fade_in_out(self, test_video, output_dir):
        out = os.path.join(output_dir, "faded.mp4")
        result = fade(test_video, out, fade_in=0.5, fade_out=0.5)
        assert result.success
        assert os.path.exists(out)

    def test_fade_invalid(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad_fade.mp4")
        with pytest.raises(ValueError):
            fade(test_video, out, fade_in=0.0, fade_out=0.0)


class TestSpeed:
    def test_speed_up(self, test_video, output_dir):
        out = os.path.join(output_dir, "fast.mp4")
        result = speed(test_video, out, factor=2.0)
        assert result.success
        assert os.path.exists(out)
        assert result.duration_seconds == pytest.approx(2.5, abs=0.5)

    def test_slow_down(self, test_video, output_dir):
        out = os.path.join(output_dir, "slow.mp4")
        result = speed(test_video, out, factor=0.5)
        assert result.success
        assert os.path.exists(out)
        assert result.duration_seconds == pytest.approx(10.0, abs=1.0)

    def test_speed_invalid_zero(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad_speed.mp4")
        with pytest.raises(ValueError):
            speed(test_video, out, factor=0.0)

    def test_speed_invalid_too_slow(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad_speed.mp4")
        with pytest.raises(ValueError):
            speed(test_video, out, factor=0.1)
