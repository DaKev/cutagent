"""Structured error handling with error codes and recovery suggestions."""

from __future__ import annotations

import sys
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

# Audio operations
INVALID_MIX_LEVEL = "INVALID_MIX_LEVEL"
INVALID_GAIN_VALUE = "INVALID_GAIN_VALUE"
AUDIO_STREAM_MISSING = "AUDIO_STREAM_MISSING"
INVALID_NORMALIZE_TARGET = "INVALID_NORMALIZE_TARGET"

# Text operations
EMPTY_TEXT_ENTRIES = "EMPTY_TEXT_ENTRIES"
INVALID_TEXT_POSITION = "INVALID_TEXT_POSITION"
INVALID_FONT_SIZE = "INVALID_FONT_SIZE"
INVALID_TEXT_TIMING = "INVALID_TEXT_TIMING"

# Animation operations
EMPTY_ANIMATION_LAYERS = "EMPTY_ANIMATION_LAYERS"
INVALID_LAYER_TYPE = "INVALID_LAYER_TYPE"
INVALID_ANIMATION_EASING = "INVALID_ANIMATION_EASING"
INVALID_ANIMATION_PROPERTY = "INVALID_ANIMATION_PROPERTY"
MISSING_LAYER_FIELD = "MISSING_LAYER_FIELD"

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

def _ffmpeg_install_hints() -> list[str]:
    """Return platform-specific FFmpeg install instructions."""
    hints = ["pip install 'cutagent[ffmpeg]'  # bundles ffmpeg+ffprobe automatically"]
    if sys.platform == "darwin":
        hints.append("brew install ffmpeg")
    elif sys.platform == "win32":
        hints.append("winget install ffmpeg  OR  choco install ffmpeg")
    else:
        hints.append("sudo apt install ffmpeg  (Debian/Ubuntu)")
    hints.extend([
        "Or download from https://ffmpeg.org/download.html",
        "Set CUTAGENT_FFMPEG=/path/to/ffmpeg to override discovery",
        "Run 'cutagent doctor' to diagnose setup issues",
    ])
    return hints


_RECOVERY_MAP: dict[str, list[str]] = {
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
    UNKNOWN_OPERATION: [
        "Use one of: trim, split, concat, reorder, extract, fade, speed, mix_audio, volume, replace_audio, normalize, text, animate",
        "Run 'cutagent capabilities' to see all supported operations",
    ],
    INVALID_MIX_LEVEL: [
        "mix_level must be between 0.0 and 1.0 (e.g., 0.15 for subtle background music)",
    ],
    INVALID_GAIN_VALUE: [
        "gain_db must be between -60.0 and 60.0",
    ],
    AUDIO_STREAM_MISSING: [
        "The source file has no audio stream",
        "Run 'cutagent probe <file>' to inspect available streams",
    ],
    INVALID_NORMALIZE_TARGET: [
        "target_lufs must be between -70.0 and -5.0 (standard broadcast is -16 or -23)",
        "true_peak_dbtp must be between -10.0 and 0.0 (standard is -1.5)",
    ],
    EMPTY_TEXT_ENTRIES: [
        "Add at least one entry to the 'entries' list",
        "Each entry needs at minimum a 'text' field",
    ],
    INVALID_TEXT_POSITION: [
        "Use a preset: center, top-center, bottom-center, top-left, top-right, bottom-left, bottom-right",
        "Or use custom coordinates as 'x,y' (e.g. '100,200')",
    ],
    INVALID_FONT_SIZE: [
        "font_size must be a positive integer (e.g. 48 for body text, 72 for titles)",
    ],
    INVALID_TEXT_TIMING: [
        "Ensure start time is before end time",
        "Use HH:MM:SS, MM:SS, or plain seconds for start/end",
    ],
    EMPTY_ANIMATION_LAYERS: [
        "Add at least one layer to the 'layers' list",
        "Each layer needs 'type', 'start', 'end', and 'properties'",
    ],
    INVALID_LAYER_TYPE: [
        "Use 'text' or 'image' as the layer type",
    ],
    INVALID_ANIMATION_EASING: [
        "Use one of: linear, ease-in, ease-out, ease-in-out, spring",
    ],
    INVALID_ANIMATION_PROPERTY: [
        "Text layers support: x, y, opacity, font_size",
        "Image layers support: x, y, opacity, scale",
    ],
    MISSING_LAYER_FIELD: [
        "Text layers require a 'text' field",
        "Image layers require a 'path' field pointing to an image file",
    ],
}


def recovery_hints(code: str, context: dict[str, Any] | None = None) -> list[str]:
    """Return recovery suggestions for a given error code."""
    # Dynamic platform-specific hints for binary-not-found errors
    if code in (FFMPEG_NOT_FOUND, FFPROBE_NOT_FOUND):
        return _ffmpeg_install_hints()

    hints = list(_RECOVERY_MAP.get(code, []))
    context = context or {}

    # Add context-specific hints
    if code == TRIM_BEYOND_DURATION and "duration" in context:
        dur = context["duration"]
        hints.insert(0, f"Source duration is {dur:.3f}s — set end to {dur:.3f} or less")

    if code == INPUT_NOT_FOUND and "path" in context:
        hints.insert(0, f"File not found: {context['path']}")

    return hints
