"""Low-level FFmpeg and FFprobe subprocess runners."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from cutagent.errors import (
    CutAgentError,
    FFMPEG_NOT_FOUND,
    FFPROBE_NOT_FOUND,
    FFMPEG_TIMEOUT,
    FFMPEG_FAILED,
    recovery_hints,
)

DEFAULT_TIMEOUT = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Binary detection
# ---------------------------------------------------------------------------

def find_ffmpeg() -> str:
    """Return the path to the ffmpeg binary, or raise CutAgentError."""
    path = shutil.which("ffmpeg")
    if path is None:
        raise CutAgentError(
            code=FFMPEG_NOT_FOUND,
            message="ffmpeg binary not found on $PATH",
            recovery=recovery_hints(FFMPEG_NOT_FOUND),
        )
    return path


def find_ffprobe() -> str:
    """Return the path to the ffprobe binary, or raise CutAgentError."""
    path = shutil.which("ffprobe")
    if path is None:
        raise CutAgentError(
            code=FFPROBE_NOT_FOUND,
            message="ffprobe binary not found on $PATH",
            recovery=recovery_hints(FFPROBE_NOT_FOUND),
        )
    return path


# ---------------------------------------------------------------------------
# Subprocess runners
# ---------------------------------------------------------------------------

def run_ffmpeg(
    args: list[str],
    timeout: int = DEFAULT_TIMEOUT,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given arguments.

    Args:
        args: Arguments to pass after 'ffmpeg' (do NOT include 'ffmpeg' itself).
        timeout: Maximum seconds to wait.
        check: If True, raise CutAgentError on non-zero exit.

    Returns:
        The CompletedProcess result.
    """
    ffmpeg = find_ffmpeg()
    cmd = [ffmpeg, "-hide_banner", "-y"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CutAgentError(
            code=FFMPEG_TIMEOUT,
            message=f"ffmpeg timed out after {timeout}s",
            recovery=[f"Increase timeout (current: {timeout}s)", "Check if input file is corrupt"],
            context={"command": cmd, "timeout": timeout},
        ) from exc

    if check and result.returncode != 0:
        raise CutAgentError(
            code=FFMPEG_FAILED,
            message=f"ffmpeg exited with code {result.returncode}",
            recovery=["Check stderr for details", "Verify input file is a valid media file"],
            context={
                "command": cmd,
                "returncode": result.returncode,
                "stderr": result.stderr[-2000:] if result.stderr else "",
            },
        )

    return result


def run_ffprobe(
    args: list[str],
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Run ffprobe with the given arguments.

    Args:
        args: Arguments to pass after 'ffprobe' (do NOT include 'ffprobe' itself).
        timeout: Maximum seconds to wait.

    Returns:
        The CompletedProcess result.
    """
    ffprobe = find_ffprobe()
    cmd = [ffprobe, "-hide_banner"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CutAgentError(
            code=FFMPEG_TIMEOUT,
            message=f"ffprobe timed out after {timeout}s",
            recovery=["Check if input file is corrupt or on a slow filesystem"],
            context={"command": cmd, "timeout": timeout},
        ) from exc

    if result.returncode != 0:
        raise CutAgentError(
            code=FFMPEG_FAILED,
            message=f"ffprobe exited with code {result.returncode}",
            recovery=["Verify the input file exists and is a valid media file"],
            context={
                "command": cmd,
                "returncode": result.returncode,
                "stderr": result.stderr[-2000:] if result.stderr else "",
            },
        )

    return result


def run_ffprobe_json(path: str | Path) -> dict:
    """Run ffprobe and return parsed JSON output for a media file."""
    result = run_ffprobe([
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ])
    return json.loads(result.stdout)
