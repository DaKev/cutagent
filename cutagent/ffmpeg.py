"""Low-level FFmpeg and FFprobe subprocess runners."""

from __future__ import annotations

import json
import os
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


def _ffmpeg_recovery_hints(stderr: str) -> list[str]:
    """Generate context-aware recovery hints from ffmpeg stderr."""
    if "No such filter" in stderr:
        return [
            "A required ffmpeg filter is missing from your build (e.g. drawtext needs libfreetype)",
            "Set CUTAGENT_FFMPEG to a ffmpeg binary with the needed filters",
            "Run 'cutagent doctor' to inspect your ffmpeg capabilities",
        ]
    stderr_lower = stderr.lower()
    if "codec not found" in stderr_lower or "unknown encoder" in stderr_lower:
        return [
            "The required codec is not available in your ffmpeg build",
            "Set CUTAGENT_FFMPEG to a ffmpeg binary with the needed codec, or run 'cutagent doctor'",
        ]
    if "no such file" in stderr_lower or "does not exist" in stderr_lower:
        return [
            "A referenced file could not be found",
            "Verify all input file paths are correct and accessible",
        ]
    if "permission denied" in stderr_lower:
        return [
            "Permission denied when accessing a file",
            "Check file permissions for input and output paths",
        ]
    return ["Check stderr for details", "Verify input file is a valid media file"]

# Module-level cache — discovery runs once per process
_cached_ffmpeg: str | None = None
_cached_ffprobe: str | None = None


def reset_cache() -> None:
    """Clear cached binary paths. Useful for testing."""
    global _cached_ffmpeg, _cached_ffprobe
    _cached_ffmpeg = None
    _cached_ffprobe = None


# ---------------------------------------------------------------------------
# Binary detection helpers
# ---------------------------------------------------------------------------

def _try_env_exact(env_var: str) -> str | None:
    """Check an env var pointing to an exact binary path."""
    value = os.environ.get(env_var)
    if value and Path(value).is_file():
        return value
    return None


def _try_env_dir(binary_name: str) -> str | None:
    """Check CUTAGENT_FFMPEG_DIR for a binary by name."""
    dir_path = os.environ.get("CUTAGENT_FFMPEG_DIR")
    if not dir_path:
        return None
    candidate = Path(dir_path) / binary_name
    if candidate.is_file():
        return str(candidate)
    # Windows: try with .exe suffix
    candidate_exe = Path(dir_path) / f"{binary_name}.exe"
    if candidate_exe.is_file():
        return str(candidate_exe)
    return None


def _try_static_ffmpeg() -> tuple[str | None, str | None]:
    """Try to get paths from the static-ffmpeg package (bundles both)."""
    try:
        from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise
        ffmpeg_path, ffprobe_path = get_or_fetch_platform_executables_else_raise()
        return (ffmpeg_path, ffprobe_path)
    except Exception:
        return (None, None)


def _try_imageio_ffmpeg() -> str | None:
    """Try to get ffmpeg path from imageio-ffmpeg (ffmpeg only, no ffprobe)."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _discover_ffmpeg() -> str:
    """Walk the fallback chain to find ffmpeg."""
    # 1. Exact env var
    path = _try_env_exact("CUTAGENT_FFMPEG")
    if path:
        return path

    # 2. Directory env var
    path = _try_env_dir("ffmpeg")
    if path:
        return path

    # 3. System PATH
    path = shutil.which("ffmpeg")
    if path:
        return path

    # 4. static-ffmpeg package
    ffmpeg_path, _ = _try_static_ffmpeg()
    if ffmpeg_path:
        return ffmpeg_path

    # 5. imageio-ffmpeg package (ffmpeg only)
    path = _try_imageio_ffmpeg()
    if path:
        return path

    return ""


def _discover_ffprobe() -> str:
    """Walk the fallback chain to find ffprobe."""
    # 1. Exact env var
    path = _try_env_exact("CUTAGENT_FFPROBE")
    if path:
        return path

    # 2. Directory env var
    path = _try_env_dir("ffprobe")
    if path:
        return path

    # 3. System PATH
    path = shutil.which("ffprobe")
    if path:
        return path

    # 4. static-ffmpeg package
    _, ffprobe_path = _try_static_ffmpeg()
    if ffprobe_path:
        return ffprobe_path

    return ""


# ---------------------------------------------------------------------------
# Public binary finders (cached)
# ---------------------------------------------------------------------------

def find_ffmpeg() -> str:
    """Return the path to the ffmpeg binary, or raise CutAgentError."""
    global _cached_ffmpeg
    if _cached_ffmpeg is not None:
        return _cached_ffmpeg

    path = _discover_ffmpeg()
    if not path:
        raise CutAgentError(
            code=FFMPEG_NOT_FOUND,
            message="ffmpeg binary not found",
            recovery=recovery_hints(FFMPEG_NOT_FOUND),
        )
    _cached_ffmpeg = path
    return path


def find_ffprobe() -> str:
    """Return the path to the ffprobe binary, or raise CutAgentError."""
    global _cached_ffprobe
    if _cached_ffprobe is not None:
        return _cached_ffprobe

    path = _discover_ffprobe()
    if not path:
        raise CutAgentError(
            code=FFPROBE_NOT_FOUND,
            message="ffprobe binary not found",
            recovery=recovery_hints(FFPROBE_NOT_FOUND),
        )
    _cached_ffprobe = path
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
        stderr_tail = result.stderr[-2000:] if result.stderr else ""
        raise CutAgentError(
            code=FFMPEG_FAILED,
            message=f"ffmpeg exited with code {result.returncode}",
            recovery=_ffmpeg_recovery_hints(stderr_tail),
            context={
                "command": cmd,
                "returncode": result.returncode,
                "stderr": stderr_tail,
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
