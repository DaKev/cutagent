"""Tests for cutagent.probe — metadata, keyframes, scene detection."""

import os

import pytest
from cutagent.probe import (
    probe,
    keyframes,
    detect_scenes,
    find_nearest_keyframe,
    extract_frames,
    thumbnail,
    detect_silence,
    audio_levels,
    summarize,
)
from cutagent.errors import CutAgentError


class TestProbe:
    def test_basic_metadata(self, test_video):
        result = probe(test_video)
        assert result.duration == pytest.approx(5.0, abs=0.5)
        assert result.width == 640
        assert result.height == 480
        assert result.format_name  # e.g. "mov,mp4,m4a,3gp,3g2,mj2"
        assert result.size_bytes > 0
        assert result.bit_rate > 0

    def test_streams(self, test_video):
        result = probe(test_video)
        assert result.video_stream is not None
        assert result.video_stream.codec_name == "h264"
        assert result.audio_stream is not None
        assert result.audio_stream.codec_name == "aac"

    def test_to_dict(self, test_video):
        result = probe(test_video)
        d = result.to_dict()
        assert "duration" in d
        assert "streams" in d
        assert isinstance(d["streams"], list)

    def test_file_not_found(self):
        with pytest.raises(CutAgentError) as exc_info:
            probe("/nonexistent/file.mp4")
        assert exc_info.value.code == "INPUT_NOT_FOUND"


class TestKeyframes:
    def test_returns_list(self, test_video):
        kfs = keyframes(test_video)
        assert isinstance(kfs, list)
        assert len(kfs) > 0
        # First keyframe should be at or near 0
        assert kfs[0] < 1.0

    def test_sorted(self, test_video):
        kfs = keyframes(test_video)
        assert kfs == sorted(kfs)

    def test_file_not_found(self):
        with pytest.raises(CutAgentError):
            keyframes("/nonexistent/file.mp4")


class TestSceneDetection:
    def test_returns_list(self, test_video):
        scenes = detect_scenes(test_video, threshold=0.3)
        assert isinstance(scenes, list)
        assert len(scenes) >= 1
        assert scenes[0].start == 0.0

    def test_scene_frame_output(self, test_video, output_dir):
        scenes = detect_scenes(test_video, threshold=0.3, frame_output_dir=output_dir)
        assert len(scenes) >= 1
        assert scenes[0].frame is not None
        assert os.path.exists(scenes[0].frame)

    def test_file_not_found(self):
        with pytest.raises(CutAgentError):
            detect_scenes("/nonexistent/file.mp4")


class TestFindNearestKeyframe:
    def test_exact_keyframe(self, test_video):
        kfs = keyframes(test_video)
        if kfs:
            result = find_nearest_keyframe(test_video, kfs[0])
            assert result == kfs[0]

    def test_between_keyframes(self, test_video):
        result = find_nearest_keyframe(test_video, 2.5)
        assert isinstance(result, float)


class TestFrameExtraction:
    def test_extract_multiple_frames(self, test_video, output_dir):
        frames = extract_frames(test_video, timestamps=[0.5, 1.0, 2.0], output_dir=output_dir)
        assert len(frames) == 3
        for frame in frames:
            assert os.path.exists(frame.path)
            assert frame.width is not None
            assert frame.height is not None

    def test_thumbnail(self, test_video, output_dir):
        out = os.path.join(output_dir, "thumb.jpg")
        frame = thumbnail(test_video, timestamp=1.25, output=out)
        assert os.path.exists(out)
        assert frame.path == out
        assert frame.width is not None


class TestAudioAnalysis:
    def test_detect_silence(self, test_video_with_silence):
        intervals = detect_silence(test_video_with_silence, threshold=-35.0, min_duration=0.2)
        assert len(intervals) >= 2
        assert intervals[0].start == pytest.approx(0.0, abs=0.2)

    def test_audio_levels(self, test_video):
        levels = audio_levels(test_video, interval=1.0)
        assert len(levels) >= 4
        assert isinstance(levels[0].rms_db, float)


class TestSummary:
    def test_summarize(self, test_video_with_silence, output_dir):
        result = summarize(test_video_with_silence, frame_dir=output_dir)
        assert result.duration > 0
        assert result.resolution == "640x480"
        assert len(result.scenes) >= 1
        assert len(result.silences) >= 1
        assert len(result.suggested_cut_points) >= 1
        assert result.scenes[0].frame is not None
