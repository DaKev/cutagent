"""Tests for cutagent.validation — dry-run EDL checks."""

import os

import pytest
from cutagent.validation import validate_edl


class TestValidateEDL:
    def test_valid_edl(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid
        assert len(result.errors) == 0

    def test_missing_input_file(self):
        edl = {
            "version": "1.0",
            "inputs": ["/nonexistent/video.mp4"],
            "operations": [
                {"op": "trim", "source": "/nonexistent/video.mp4", "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INPUT_NOT_FOUND" in codes

    def test_trim_start_after_end(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "5", "end": "2"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "TRIM_START_AFTER_END" in codes

    def test_trim_beyond_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "999"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "TRIM_BEYOND_DURATION" in codes

    def test_invalid_reference(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "concat", "segments": ["$5"]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_REFERENCE" in codes

    def test_valid_reference(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
                {"op": "trim", "source": test_video, "start": "1", "end": "4"},
                {"op": "concat", "segments": ["$0", "$1"]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid

    def test_invalid_json(self):
        result = validate_edl("{bad json}")
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_EDL" in codes

    def test_invalid_time_format(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "not-a-time", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_TIME_FORMAT" in codes

    def test_output_as_dict(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        d = result.to_dict()
        assert "valid" in d
        assert "errors" in d
        assert "warnings" in d

    def test_invalid_stream_type(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "extract", "source": test_video, "stream": "subtitle"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_STREAM_TYPE" in codes

    def test_reorder_out_of_range(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "reorder", "segments": [test_video], "order": [5]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "REORDER_INDEX_OUT_OF_RANGE" in codes

    def test_split_beyond_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "split", "source": test_video, "points": ["999"]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "SPLIT_POINT_BEYOND_DURATION" in codes

    def test_invalid_concat_transition(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "concat", "segments": [test_video, test_video], "transition": "wipe"},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_TRANSITION" in codes

    def test_invalid_concat_transition_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {
                    "op": "concat",
                    "segments": [test_video, test_video],
                    "transition": "crossfade",
                    "transition_duration": 0.0,
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_TRANSITION_DURATION" in codes

    def test_valid_fade(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "fade", "source": test_video, "fade_in": 0.5, "fade_out": 0.5},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid

    def test_invalid_fade_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "fade", "source": test_video, "fade_in": -1.0, "fade_out": 0.0},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_FADE_DURATION" in codes

    def test_valid_speed(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "speed", "source": test_video, "factor": 2.0},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid

    def test_invalid_speed_factor_zero(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "speed", "source": test_video, "factor": 0.0},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_SPEED_FACTOR" in codes

    def test_invalid_speed_factor_out_of_range(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "speed", "source": test_video, "factor": 0.1},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_SPEED_FACTOR" in codes


class TestInputRefValidation:
    """Tests for $input.N reference validation."""

    def test_valid_input_ref(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid

    def test_invalid_input_ref_out_of_range(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.5", "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_REFERENCE" in codes

    def test_input_ref_in_concat_segments(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "concat", "segments": ["$input.0", "$input.0"]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid

    def test_mixed_input_ref_and_op_ref(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
                {"op": "trim", "source": "$input.0", "start": "1", "end": "4"},
                {"op": "concat", "segments": ["$0", "$1"]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid


class TestEstimatedDuration:
    """Tests for estimated_duration in validation output."""

    def test_trim_estimated_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "1", "end": "4"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid
        assert result.estimated_duration == pytest.approx(3.0, abs=0.01)

    def test_trim_estimated_duration_in_dict(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "2"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        d = result.to_dict()
        assert "estimated_duration" in d
        assert d["estimated_duration"] == pytest.approx(2.0, abs=0.01)
        assert "estimated_duration_formatted" in d

    def test_concat_estimated_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "2"},
                {"op": "trim", "source": test_video, "start": "2", "end": "4"},
                {"op": "concat", "segments": ["$0", "$1"]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid
        assert result.estimated_duration == pytest.approx(4.0, abs=0.01)

    def test_concat_crossfade_estimated_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
                {"op": "trim", "source": test_video, "start": "2", "end": "5"},
                {
                    "op": "concat",
                    "segments": ["$0", "$1"],
                    "transition": "crossfade",
                    "transition_duration": 0.5,
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid
        # 3s + 3s - 0.5s crossfade = 5.5s
        assert result.estimated_duration == pytest.approx(5.5, abs=0.01)

    def test_speed_estimated_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "4"},
                {"op": "speed", "source": "$0", "factor": 2.0},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid
        # 4s / 2x speed = 2s
        assert result.estimated_duration == pytest.approx(2.0, abs=0.01)

    def test_fade_preserves_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
                {"op": "fade", "source": "$0", "fade_in": 0.5, "fade_out": 0.5},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid
        assert result.estimated_duration == pytest.approx(3.0, abs=0.01)

    def test_no_estimated_duration_when_invalid(self):
        """Invalid EDLs should not have estimated_duration in the dict."""
        result = validate_edl("{bad json}")
        d = result.to_dict()
        assert "estimated_duration" not in d

    def test_input_ref_estimated_duration(self, test_video):
        """Estimated duration works with $input.N references too."""
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "2.5"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        result = validate_edl(edl)
        assert result.valid
        assert result.estimated_duration == pytest.approx(2.5, abs=0.01)
