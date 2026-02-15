"""Tests for cutagent.cli — argument parsing and command handlers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Optional

import pytest


def _run_cli(*args: str, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run cutagent CLI as a subprocess and return the result."""
    cmd = [sys.executable, "-m", "cutagent"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=60,
    )


class TestEdlJsonArgument:
    """Tests for the --edl-json inline argument on validate and execute."""

    def test_validate_with_edl_json(self, test_video):
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        })
        result = _run_cli("validate", "--edl-json", edl)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

    def test_execute_with_edl_json(self, test_video, output_dir):
        out = os.path.join(output_dir, "inline_exec.mp4")
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": test_video, "start": "0", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        })
        result = _run_cli("execute", "--edl-json", edl, "-q")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert os.path.exists(out)

    def test_validate_with_edl_json_input_ref(self, test_video):
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        })
        result = _run_cli("validate", "--edl-json", edl)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

    def test_validate_no_edl_provided(self):
        """Calling validate with no file and no --edl-json should fail."""
        result = _run_cli("validate")
        assert result.returncode != 0


class TestProgressOutput:
    """Tests for stderr progress during execute."""

    def test_progress_on_stderr(self, test_video, output_dir):
        out = os.path.join(output_dir, "progress.mp4")
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        })
        result = _run_cli("execute", "--edl-json", edl)
        assert result.returncode == 0

        # stderr should contain JSONL progress lines
        lines = [l for l in result.stderr.strip().splitlines() if l.strip()]
        assert len(lines) >= 2  # at least running + done
        for line in lines:
            data = json.loads(line)
            assert "progress" in data
            assert "step" in data["progress"]
            assert "total" in data["progress"]
            assert "op" in data["progress"]
            assert data["progress"]["status"] in ("running", "done")

    def test_quiet_suppresses_progress(self, test_video, output_dir):
        out = os.path.join(output_dir, "quiet.mp4")
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
            ],
            "output": {"path": out, "codec": "copy"},
        })
        result = _run_cli("execute", "--edl-json", edl, "-q")
        assert result.returncode == 0
        # stderr should be empty (no progress)
        progress_lines = [l for l in result.stderr.strip().splitlines()
                          if l.strip() and '"progress"' in l]
        assert len(progress_lines) == 0


class TestEstimatedDurationInCli:
    """Tests for estimated_duration in validate CLI output."""

    def test_validate_includes_estimated_duration(self, test_video):
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "1", "end": "4"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        })
        result = _run_cli("validate", "--edl-json", edl)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True
        assert "estimated_duration" in data
        assert abs(data["estimated_duration"] - 3.0) < 0.01
        assert "estimated_duration_formatted" in data
