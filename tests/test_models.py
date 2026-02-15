"""Tests for cutagent.models — dataclasses and JSON round-tripping."""

import pytest
from cutagent.models import (
    parse_time,
    format_time,
    StreamInfo,
    ProbeResult,
    FrameResult,
    SceneInfo,
    SilenceInterval,
    AudioLevel,
    VideoSummary,
    TrimOp,
    SplitOp,
    ConcatOp,
    ReorderOp,
    ExtractOp,
    FadeOp,
    SpeedOp,
    EDL,
    OutputSpec,
    OperationResult,
    parse_operation,
)


# ---------------------------------------------------------------------------
# parse_time
# ---------------------------------------------------------------------------

class TestParseTime:
    def test_seconds_int(self):
        assert parse_time("90") == 90.0

    def test_seconds_float(self):
        assert parse_time("1.5") == 1.5

    def test_mmss(self):
        assert parse_time("1:30") == 90.0

    def test_hhmmss(self):
        assert parse_time("1:02:03") == 3723.0

    def test_hhmmss_millis(self):
        assert parse_time("0:00:01.500") == 1.5

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time("not-a-time")


class TestFormatTime:
    def test_simple(self):
        assert format_time(90.0) == "00:01:30.000"

    def test_hours(self):
        assert format_time(3723.5) == "01:02:03.500"


# ---------------------------------------------------------------------------
# StreamInfo
# ---------------------------------------------------------------------------

class TestStreamInfo:
    def test_round_trip(self):
        s = StreamInfo(index=0, codec_name="h264", codec_type="video", width=1920, height=1080, fps=30.0)
        d = s.to_dict()
        assert d["width"] == 1920
        s2 = StreamInfo.from_dict(d)
        assert s2.width == 1920

    def test_none_fields_excluded(self):
        s = StreamInfo(index=0, codec_name="aac", codec_type="audio", sample_rate=44100, channels=2)
        d = s.to_dict()
        assert "width" not in d
        assert d["sample_rate"] == 44100


# ---------------------------------------------------------------------------
# ProbeResult
# ---------------------------------------------------------------------------

class TestProbeResult:
    def test_video_stream_property(self):
        vs = StreamInfo(index=0, codec_name="h264", codec_type="video", width=640, height=480)
        aus = StreamInfo(index=1, codec_name="aac", codec_type="audio")
        pr = ProbeResult(path="test.mp4", duration=5.0, format_name="mov,mp4", size_bytes=1000, bit_rate=8000, streams=[vs, aus])
        assert pr.video_stream is vs
        assert pr.audio_stream is aus
        assert pr.width == 640
        assert pr.height == 480

    def test_round_trip(self):
        pr = ProbeResult(path="test.mp4", duration=5.0, format_name="mov,mp4", size_bytes=1000, bit_rate=8000, streams=[])
        d = pr.to_dict()
        pr2 = ProbeResult.from_dict(d)
        assert pr2.duration == 5.0


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

class TestOperations:
    def test_trim_round_trip(self):
        op = TrimOp(source="test.mp4", start="00:01:00", end="00:02:00")
        d = op.to_dict()
        assert d["op"] == "trim"
        op2 = TrimOp.from_dict(d)
        assert op2.start == "00:01:00"

    def test_split_round_trip(self):
        op = SplitOp(source="test.mp4", points=["00:01:00", "00:02:00"])
        d = op.to_dict()
        op2 = SplitOp.from_dict(d)
        assert len(op2.points) == 2

    def test_concat_round_trip(self):
        op = ConcatOp(segments=["a.mp4", "b.mp4"])
        d = op.to_dict()
        op2 = ConcatOp.from_dict(d)
        assert op2.segments == ["a.mp4", "b.mp4"]
        assert op2.transition is None

    def test_concat_with_transition_round_trip(self):
        op = ConcatOp(segments=["a.mp4", "b.mp4"], transition="crossfade", transition_duration=0.5)
        d = op.to_dict()
        op2 = ConcatOp.from_dict(d)
        assert op2.transition == "crossfade"
        assert op2.transition_duration == 0.5

    def test_reorder_round_trip(self):
        op = ReorderOp(segments=["a.mp4", "b.mp4"], order=[1, 0])
        d = op.to_dict()
        op2 = ReorderOp.from_dict(d)
        assert op2.order == [1, 0]

    def test_extract_round_trip(self):
        op = ExtractOp(source="test.mp4", stream="audio")
        d = op.to_dict()
        op2 = ExtractOp.from_dict(d)
        assert op2.stream == "audio"

    def test_fade_round_trip(self):
        op = FadeOp(source="test.mp4", fade_in=0.5, fade_out=0.5)
        d = op.to_dict()
        assert d["op"] == "fade"
        op2 = FadeOp.from_dict(d)
        assert op2.fade_in == 0.5
        assert op2.fade_out == 0.5

    def test_parse_operation(self):
        d = {"op": "trim", "source": "test.mp4", "start": "0", "end": "5"}
        op = parse_operation(d)
        assert isinstance(op, TrimOp)

    def test_speed_round_trip(self):
        op = SpeedOp(source="test.mp4", factor=2.0)
        d = op.to_dict()
        assert d["op"] == "speed"
        op2 = SpeedOp.from_dict(d)
        assert op2.factor == 2.0

    def test_parse_fade_operation(self):
        d = {"op": "fade", "source": "test.mp4", "fade_in": 0.25, "fade_out": 0.25}
        op = parse_operation(d)
        assert isinstance(op, FadeOp)

    def test_parse_speed_operation(self):
        d = {"op": "speed", "source": "test.mp4", "factor": 0.5}
        op = parse_operation(d)
        assert isinstance(op, SpeedOp)
        assert op.factor == 0.5

    def test_parse_unknown_op(self):
        with pytest.raises(ValueError, match="Unknown operation"):
            parse_operation({"op": "warp"})


# ---------------------------------------------------------------------------
# EDL
# ---------------------------------------------------------------------------

class TestEDL:
    def test_round_trip(self):
        data = {
            "version": "1.0",
            "inputs": ["test.mp4"],
            "operations": [{"op": "trim", "source": "test.mp4", "start": "0", "end": "3"}],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        edl = EDL.from_dict(data)
        assert edl.version == "1.0"
        assert isinstance(edl.operations[0], TrimOp)
        d = edl.to_dict()
        assert d["version"] == "1.0"


# ---------------------------------------------------------------------------
# OperationResult
# ---------------------------------------------------------------------------

class TestOperationResult:
    def test_to_dict_minimal(self):
        r = OperationResult(success=True, output_path="out.mp4")
        d = r.to_dict()
        assert d["success"] is True
        assert "warnings" not in d

    def test_to_dict_with_warnings(self):
        r = OperationResult(success=True, output_path="out.mp4", warnings=["some warning"])
        d = r.to_dict()
        assert d["warnings"] == ["some warning"]

    def test_to_dict_with_duration(self):
        r = OperationResult(success=True, output_path="out.mp4", duration_seconds=90.0)
        d = r.to_dict()
        assert d["duration_formatted"] == "00:01:30.000"


class TestContentModels:
    def test_frame_result_round_trip(self):
        frame = FrameResult(timestamp=1.0, path="frame.jpg", width=640, height=480)
        data = frame.to_dict()
        parsed = FrameResult.from_dict(data)
        assert parsed.timestamp == 1.0
        assert parsed.width == 640

    def test_scene_info_round_trip(self):
        scene = SceneInfo(start=0.0, end=2.5, duration=2.5, frames=["a.jpg", "b.jpg"], has_audio=True, avg_loudness=-18.2)
        data = scene.to_dict()
        parsed = SceneInfo.from_dict(data)
        assert parsed.end == 2.5
        assert parsed.has_audio is True
        assert parsed.frames == ["a.jpg", "b.jpg"]

    def test_silence_interval_round_trip(self):
        silence = SilenceInterval(start=1.0, end=1.5, duration=0.5)
        data = silence.to_dict()
        parsed = SilenceInterval.from_dict(data)
        assert parsed.duration == 0.5

    def test_audio_level_round_trip(self):
        level = AudioLevel(timestamp=2.0, rms_db=-24.3, sample_count=10)
        data = level.to_dict()
        parsed = AudioLevel.from_dict(data)
        assert parsed.rms_db == -24.3
        assert parsed.sample_count == 10

    def test_video_summary_round_trip(self):
        summary = VideoSummary(
            path="test.mp4",
            duration=5.0,
            resolution="640x480",
            scenes=[SceneInfo(start=0.0, end=5.0, duration=5.0)],
            silences=[SilenceInterval(start=1.0, end=1.5, duration=0.5)],
            audio_levels=[AudioLevel(timestamp=0.0, rms_db=-20.0, sample_count=5)],
            silence_points=[1.0],
            suggested_cut_points=[0.0, 1.0, 5.0],
        )
        data = summary.to_dict()
        parsed = VideoSummary.from_dict(data)
        assert parsed.duration == 5.0
        assert parsed.scenes[0].duration == 5.0
