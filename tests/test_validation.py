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
