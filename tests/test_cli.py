"""Tests for cutagent.cli — argument parsing and command handlers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Optional

import pytest


def _ffmpeg_has_drawtext(ffmpeg_bin: str = "ffmpeg") -> bool:
    """Check if the given FFmpeg binary supports the drawtext filter."""
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-filters"],
            capture_output=True, text=True, timeout=10,
        )
        return "drawtext" in result.stdout
    except Exception:
        return False


def _find_drawtext_ffmpeg() -> str | None:
    """Find an FFmpeg binary with drawtext support."""
    import shutil
    from pathlib import Path
    ffmpeg_dir = os.environ.get("CUTAGENT_FFMPEG_DIR")
    if ffmpeg_dir:
        candidate = str(Path(ffmpeg_dir) / "ffmpeg")
        if _ffmpeg_has_drawtext(candidate):
            return candidate
    system = shutil.which("ffmpeg")
    if system and _ffmpeg_has_drawtext(system):
        return system
    try:
        from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise
        ffmpeg_path, _ = get_or_fetch_platform_executables_else_raise()
        if _ffmpeg_has_drawtext(ffmpeg_path):
            return ffmpeg_path
    except Exception:
        pass
    return None


_drawtext_ffmpeg = _find_drawtext_ffmpeg()

requires_drawtext = pytest.mark.skipif(
    _drawtext_ffmpeg is None,
    reason="FFmpeg with drawtext filter not available",
)


@pytest.fixture(autouse=True)
def _use_drawtext_ffmpeg_cli():
    """Ensure CLI subprocesses use an FFmpeg binary that has the drawtext filter."""
    if _drawtext_ffmpeg is None:
        yield
        return
    old = os.environ.get("CUTAGENT_FFMPEG")
    os.environ["CUTAGENT_FFMPEG"] = _drawtext_ffmpeg
    yield
    if old is None:
        os.environ.pop("CUTAGENT_FFMPEG", None)
    else:
        os.environ["CUTAGENT_FFMPEG"] = old


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


class TestDoctorCommand:
    """Tests for cutagent doctor subcommand."""

    def test_doctor_returns_json(self):
        result = _run_cli("doctor")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "healthy" in data
        assert "checks" in data

    def test_doctor_has_ffmpeg_check(self):
        result = _run_cli("doctor")
        data = json.loads(result.stdout)
        names = [c["name"] for c in data["checks"]]
        assert "ffmpeg" in names
        assert "ffprobe" in names


class TestVersionFlag:
    """Tests for cutagent --version."""

    def test_version_output(self):
        result = _run_cli("--version")
        assert result.returncode == 0
        assert "cutagent" in result.stdout


class TestFramesConvenience:
    """Tests for --count and --interval in cutagent frames."""

    def test_frames_with_count(self, test_video, output_dir):
        result = _run_cli("frames", test_video, "--count", "3", "--output-dir", output_dir)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 3

    def test_frames_with_interval(self, test_video, output_dir):
        result = _run_cli("frames", test_video, "--interval", "2", "--output-dir", output_dir)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] >= 1

    def test_frames_at_still_works(self, test_video, output_dir):
        result = _run_cli("frames", test_video, "--at", "1,2", "--output-dir", output_dir)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 2

    def test_frames_mutually_exclusive(self, test_video, output_dir):
        """Cannot combine --at with --count."""
        result = _run_cli(
            "frames", test_video,
            "--at", "1", "--count", "3",
            "--output-dir", output_dir,
        )
        assert result.returncode != 0


@requires_drawtext
class TestTextReviewTimestamps:
    """Tests for review_timestamps in text command output."""

    def test_text_output_includes_review_timestamps(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_review.mp4")
        entries = json.dumps([
            {"text": "Title", "start": "0", "end": "3"},
            {"text": "Subtitle", "start": "2", "end": "4"},
        ])
        result = _run_cli("text", test_video, "--entries-json", entries, "-o", out)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "review_timestamps" in data
        assert data["review_timestamps"] == [1.5, 3.0]
        assert "text_layers" in data
        assert len(data["text_layers"]) == 2

    def test_animate_output_includes_review_timestamps(self, test_video, output_dir):
        out = os.path.join(output_dir, "animate_review.mp4")
        layers = json.dumps([{
            "type": "text", "text": "Hello", "start": 0.0, "end": 4.0,
            "properties": {},
        }])
        result = _run_cli("animate", test_video, "--layers-json", layers, "-o", out)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "review_timestamps" in data
        assert data["review_timestamps"] == [2.0]
        assert "text_layers" in data


@requires_drawtext
class TestFileFlags:
    """Tests for --entries-file and --layers-file CLI flags."""

    def test_text_entries_file(self, test_video, output_dir, tmp_path):
        out = os.path.join(output_dir, "text_file.mp4")
        entries_file = str(tmp_path / "entries.json")
        with open(entries_file, "w") as f:
            json.dump([{"text": "From File"}], f)
        result = _run_cli("text", test_video, "--entries-file", entries_file, "-o", out)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["success"] is True

    def test_animate_layers_file(self, test_video, output_dir, tmp_path):
        out = os.path.join(output_dir, "animate_file.mp4")
        layers_file = str(tmp_path / "layers.json")
        with open(layers_file, "w") as f:
            json.dump([{
                "type": "text", "text": "From File",
                "start": 0.0, "end": 2.0, "properties": {},
            }], f)
        result = _run_cli("animate", test_video, "--layers-file", layers_file, "-o", out)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["success"] is True

    def test_entries_json_and_file_mutually_exclusive(self, test_video, output_dir, tmp_path):
        out = os.path.join(output_dir, "bad.mp4")
        entries_file = str(tmp_path / "entries.json")
        with open(entries_file, "w") as f:
            json.dump([{"text": "X"}], f)
        result = _run_cli(
            "text", test_video,
            "--entries-json", '[{"text": "Y"}]',
            "--entries-file", entries_file,
            "-o", out,
        )
        assert result.returncode != 0


class TestEdlFieldErrors:
    """Tests for helpful errors when EDL fields are misspelled."""

    def test_missing_segments_in_concat(self, test_video):
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "2"},
                {"op": "trim", "source": "$input.0", "start": "2", "end": "4"},
                {"op": "concat", "sources": ["$0", "$1"]},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        })
        result = _run_cli("validate", "--edl-json", edl)
        assert result.returncode != 0
        data = json.loads(result.stdout)
        # validate wraps parse errors inside its valid/errors structure
        assert data["valid"] is False
        errors = data["errors"]
        assert any(e["code"] == "MISSING_FIELD" for e in errors)
        assert any("segments" in e["message"] for e in errors)

    def test_missing_source_in_trim(self, test_video):
        edl = json.dumps({
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "video": "$input.0", "start": "0", "end": "2"},
            ],
            "output": {"path": "out.mp4", "codec": "copy"},
        })
        result = _run_cli("validate", "--edl-json", edl)
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["valid"] is False
        errors = data["errors"]
        assert any(e["code"] == "MISSING_FIELD" for e in errors)
        assert any("source" in e["message"] for e in errors)
