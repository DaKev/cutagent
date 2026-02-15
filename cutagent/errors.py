"""Structured error handling with error codes and recovery suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

# System
FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"
FFPROBE_NOT_FOUND = "FFPROBE_NOT_FOUND"
FFMPEG_TIMEOUT = "FFMPEG_TIMEOUT"
FFMPEG_FAILED = "FFMPEG_FAILED"

# Input
INPUT_NOT_FOUND = "INPUT_NOT_FOUND"
INPUT_NOT_READABLE = "INPUT_NOT_READABLE"
INPUT_INVALID_FORMAT = "INPUT_INVALID_FORMAT"

# Validation
INVALID_EDL = "INVALID_EDL"
UNKNOWN_OPERATION = "UNKNOWN_OPERATION"
MISSING_FIELD = "MISSING_FIELD"
INVALID_TIME_FORMAT = "INVALID_TIME_FORMAT"
TRIM_BEYOND_DURATION = "TRIM_BEYOND_DURATION"
TRIM_START_AFTER_END = "TRIM_START_AFTER_END"
INVALID_REFERENCE = "INVALID_REFERENCE"
SPLIT_POINT_BEYOND_DURATION = "SPLIT_POINT_BEYOND_DURATION"
REORDER_INDEX_OUT_OF_RANGE = "REORDER_INDEX_OUT_OF_RANGE"
INVALID_STREAM_TYPE = "INVALID_STREAM_TYPE"
CODEC_INCOMPATIBLE = "CODEC_INCOMPATIBLE"

# Output
OUTPUT_DIR_NOT_FOUND = "OUTPUT_DIR_NOT_FOUND"
OUTPUT_ALREADY_EXISTS = "OUTPUT_ALREADY_EXISTS"

# Exit codes for CLI
EXIT_SUCCESS = 0
EXIT_VALIDATION = 1
EXIT_EXECUTION = 2
EXIT_SYSTEM = 3


# ---------------------------------------------------------------------------
# CutAgentError exception
# ---------------------------------------------------------------------------

@dataclass
class CutAgentError(Exception):
    """Structured error with code, message, recovery hints, and context."""
    code: str
    message: str
    recovery: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "recovery": self.recovery,
            "context": self.context,
        }


# ---------------------------------------------------------------------------
# Recovery hint factory
# ---------------------------------------------------------------------------

_RECOVERY_MAP: dict[str, list[str]] = {
    FFMPEG_NOT_FOUND: [
        "Install FFmpeg: https://ffmpeg.org/download.html",
        "Ensure 'ffmpeg' is on your $PATH",
    ],
    FFPROBE_NOT_FOUND: [
        "Install FFmpeg (includes ffprobe): https://ffmpeg.org/download.html",
        "Ensure 'ffprobe' is on your $PATH",
    ],
    INPUT_NOT_FOUND: [
        "Check the file path for typos",
        "Use an absolute path to avoid working-directory issues",
    ],
    TRIM_BEYOND_DURATION: [
        "Run 'cutagent probe <file>' to check the actual duration",
        "Set end time to the source duration or earlier",
    ],
    TRIM_START_AFTER_END: [
        "Swap start and end times",
    ],
    INVALID_REFERENCE: [
        "References use $N where N is a 0-based operation index",
        "Ensure the referenced operation exists earlier in the operations list",
    ],
    INVALID_TIME_FORMAT: [
        "Use HH:MM:SS, HH:MM:SS.mmm, MM:SS, or plain seconds",
    ],
}


def recovery_hints(code: str, context: dict[str, Any] | None = None) -> list[str]:
    """Return recovery suggestions for a given error code."""
    hints = list(_RECOVERY_MAP.get(code, []))
    context = context or {}

    # Add context-specific hints
    if code == TRIM_BEYOND_DURATION and "duration" in context:
        dur = context["duration"]
        hints.insert(0, f"Source duration is {dur:.3f}s — set end to {dur:.3f} or less")

    if code == INPUT_NOT_FOUND and "path" in context:
        hints.insert(0, f"File not found: {context['path']}")

    return hints
