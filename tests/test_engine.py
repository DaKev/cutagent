"""Tests for cutagent.engine — EDL parsing and execution."""

import json
import os

import pytest
from cutagent.engine import (
    parse_edl,
    execute_edl,
    _is_input_reference,
    _resolve_input_ref,
)
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

    def test_speed_operation(self, test_video, output_dir):
        out = os.path.join(output_dir, "sped_up.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "speed", "source": test_video, "factor": 2.0},
            ],
            "output": {"path": out, "codec": "libx264"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)

    def test_input_ref_trim(self, test_video, output_dir):
        """Test $input.0 reference in a trim operation."""
        out = os.path.join(output_dir, "input_ref.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)

    def test_input_ref_concat(self, test_video_10s, output_dir):
        """Test $input.0 mixed with $N references in a multi-step EDL."""
        out = os.path.join(output_dir, "mixed_refs.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video_10s],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
                {"op": "trim", "source": "$input.0", "start": "7", "end": "10"},
                {"op": "concat", "segments": ["$0", "$1"]},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)

    def test_input_ref_out_of_range(self, test_video, output_dir):
        """Test $input.5 when only 1 input exists raises INVALID_REFERENCE."""
        out = os.path.join(output_dir, "bad_input_ref.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.5", "start": "0", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        with pytest.raises(CutAgentError) as exc_info:
            execute_edl(edl)
        assert exc_info.value.code == "INVALID_REFERENCE"

    def test_progress_callback(self, test_video, output_dir):
        """Test that progress_callback is called with correct step/total/status."""
        out = os.path.join(output_dir, "progress.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        calls = []
        def cb(step, total, op_name, status):
            calls.append((step, total, op_name, status))

        result = execute_edl(edl, progress_callback=cb)
        assert result.success
        assert len(calls) == 2
        assert calls[0] == (1, 1, "trim", "running")
        assert calls[1] == (1, 1, "trim", "done")

    def test_progress_callback_multi_step(self, test_video_10s, output_dir):
        """Test progress callback with multiple operations."""
        out = os.path.join(output_dir, "progress_multi.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video_10s],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
                {"op": "trim", "source": "$input.0", "start": "7", "end": "10"},
                {"op": "concat", "segments": ["$0", "$1"]},
            ],
            "output": {"path": out, "codec": "copy"},
        }
        calls = []
        def cb(step, total, op_name, status):
            calls.append((step, total, op_name, status))

        result = execute_edl(edl, progress_callback=cb)
        assert result.success
        assert len(calls) == 6  # 3 ops x 2 (running + done)
        assert all(c[1] == 3 for c in calls)  # total is always 3
        assert calls[0] == (1, 3, "trim", "running")
        assert calls[5] == (3, 3, "concat", "done")


class TestInputRefHelpers:
    def test_is_input_reference_valid(self):
        assert _is_input_reference("$input.0") is True
        assert _is_input_reference("$input.12") is True

    def test_is_input_reference_invalid(self):
        assert _is_input_reference("$0") is False
        assert _is_input_reference("$input.") is False
        assert _is_input_reference("$input.abc") is False
        assert _is_input_reference("input.0") is False

    def test_resolve_input_ref(self):
        inputs = ["/path/a.mp4", "/path/b.mp4"]
        assert _resolve_input_ref("$input.0", inputs) == "/path/a.mp4"
        assert _resolve_input_ref("$input.1", inputs) == "/path/b.mp4"

    def test_resolve_input_ref_out_of_range(self):
        with pytest.raises(CutAgentError) as exc_info:
            _resolve_input_ref("$input.5", ["/path/a.mp4"])
        assert exc_info.value.code == "INVALID_REFERENCE"
