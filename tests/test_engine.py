"""Tests for cutagent.engine — EDL parsing and execution."""

import json
import os

import pytest
from cutagent.engine import parse_edl, execute_edl
from cutagent.errors import CutAgentError


class TestParseEDL:
    def test_parse_valid_json(self, test_video):
        edl_data = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        }
        edl = parse_edl(edl_data)
        assert edl.version == "1.0"
        assert len(edl.operations) == 1

    def test_parse_json_string(self, test_video):
        edl_str = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        })
        edl = parse_edl(edl_str)
        assert edl.version == "1.0"

    def test_invalid_json(self):
        with pytest.raises(CutAgentError) as exc_info:
            parse_edl("{bad json}")
        assert exc_info.value.code == "INVALID_EDL"

    def test_missing_field(self):
        with pytest.raises(CutAgentError) as exc_info:
            parse_edl({"version": "1.0"})  # missing inputs, operations, output
        assert exc_info.value.code == "MISSING_FIELD"


class TestExecuteEDL:
    def test_single_trim(self, test_video, output_dir):
        out = os.path.join(output_dir, "result.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)

    def test_trim_and_concat_with_references(self, test_video_10s, output_dir):
        """Test $N reference resolution: trim twice, then concat the results."""
        out = os.path.join(output_dir, "highlight.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video_10s],
            "operations": [
                {"op": "trim", "source": test_video_10s, "start": "0", "end": "3"},
                {"op": "trim", "source": test_video_10s, "start": "7", "end": "10"},
                {"op": "concat", "segments": ["$0", "$1"]},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)

    def test_extract_audio(self, test_video, output_dir):
        out = os.path.join(output_dir, "audio.aac")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "extract", "source": test_video, "stream": "audio"},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)

    def test_invalid_reference(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "concat", "segments": ["$5"]},  # $5 doesn't exist
            ],
            "output": {"path": out, "codec": "copy"},
        }
        with pytest.raises(CutAgentError) as exc_info:
            execute_edl(edl)
        assert exc_info.value.code == "INVALID_REFERENCE"

    def test_execute_json_string(self, test_video, output_dir):
        out = os.path.join(output_dir, "result.mp4")
        edl_str = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "1", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        })
        result = execute_edl(edl_str)
        assert result.success

    def test_fade_operation(self, test_video, output_dir):
        out = os.path.join(output_dir, "faded.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "fade", "source": test_video, "fade_in": 0.5, "fade_out": 0.5},
            ],
            "output": {"path": out, "codec": "libx264"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)

    def test_concat_with_crossfade(self, test_video_10s, output_dir):
        out = os.path.join(output_dir, "crossfade.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video_10s],
            "operations": [
                {"op": "trim", "source": test_video_10s, "start": "0", "end": "4"},
                {"op": "trim", "source": test_video_10s, "start": "4", "end": "8"},
                {
                    "op": "concat",
                    "segments": ["$0", "$1"],
                    "transition": "crossfade",
                    "transition_duration": 0.3,
                },
            ],
            "output": {"path": out, "codec": "libx264"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)
