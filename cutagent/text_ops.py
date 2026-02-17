"""Text overlay operations — burn text, descriptions, and annotations onto video."""

from __future__ import annotations

import re

from cutagent.errors import (
    CutAgentError,
    EMPTY_TEXT_ENTRIES,
    INVALID_TEXT_POSITION,
    INVALID_FONT_SIZE,
    INVALID_TEXT_TIMING,
    recovery_hints,
)
from cutagent.ffmpeg import run_ffmpeg
from cutagent.models import OperationResult, TextEntry, TEXT_POSITIONS, parse_time
from cutagent.probe import probe as probe_file


# ---------------------------------------------------------------------------
# Position preset → FFmpeg coordinate expressions
# ---------------------------------------------------------------------------

_POSITION_MAP: dict[str, tuple[str, str]] = {
    "center":        ("(w-text_w)/2", "(h-text_h)/2"),
    "top-center":    ("(w-text_w)/2", "20"),
    "bottom-center": ("(w-text_w)/2", "h-text_h-20"),
    "top-left":      ("20", "20"),
    "top-right":     ("w-text_w-20", "20"),
    "bottom-left":   ("20", "h-text_h-20"),
    "bottom-right":  ("w-text_w-20", "h-text_h-20"),
}

_CUSTOM_POS_RE = re.compile(r"^(\d+)\s*,\s*(\d+)$")


def _resolve_position(position: str) -> tuple[str, str]:
    """Convert a position preset or 'x,y' string into FFmpeg x/y expressions."""
    if position in _POSITION_MAP:
        return _POSITION_MAP[position]

    m = _CUSTOM_POS_RE.match(position)
    if m:
        return (m.group(1), m.group(2))

    raise CutAgentError(
        code=INVALID_TEXT_POSITION,
        message=f"Invalid text position: {position!r}",
        recovery=recovery_hints(INVALID_TEXT_POSITION),
        context={"position": position, "valid_presets": sorted(TEXT_POSITIONS)},
    )


# ---------------------------------------------------------------------------
# Drawtext filter builder
# ---------------------------------------------------------------------------

def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter value."""
    # FFmpeg drawtext requires escaping: ' \ : and sometimes ;
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\\\\\''")
    text = text.replace(":", "\\:")
    text = text.replace(";", "\\;")
    return text


def _build_drawtext_filter(entry: TextEntry) -> str:
    """Build a single drawtext=... filter string from a TextEntry."""
    x_expr, y_expr = _resolve_position(entry.position)
    escaped = _escape_drawtext(entry.text)

    parts = [
        f"text='{escaped}'",
        f"fontsize={entry.font_size}",
        f"fontcolor={entry.font_color}",
        f"x={x_expr}",
        f"y={y_expr}",
    ]

    if entry.font:
        parts.append(f"font='{entry.font}'")

    if entry.bg_color:
        parts.append("box=1")
        parts.append(f"boxcolor={entry.bg_color}")
        parts.append(f"boxborderw={entry.bg_padding}")

    # Timed display via enable='between(t,start,end)'
    if entry.start is not None or entry.end is not None:
        start_sec = parse_time(entry.start) if entry.start else 0.0
        end_sec = parse_time(entry.end) if entry.end else 99999.0
        if start_sec >= end_sec:
            raise CutAgentError(
                code=INVALID_TEXT_TIMING,
                message=f"Text start ({entry.start}) is at or after end ({entry.end})",
                recovery=recovery_hints(INVALID_TEXT_TIMING),
                context={"start": entry.start, "end": entry.end},
            )
        parts.append(f"enable='between(t,{start_sec},{end_sec})'")

    return "drawtext=" + ":".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_text(
    source: str,
    entries: list[TextEntry],
    output: str,
    codec: str = "libx264",
) -> OperationResult:
    """Burn one or more text overlays onto a video.

    Args:
        source: Path to the source video.
        entries: List of TextEntry objects describing each text overlay.
        output: Path for the output file.
        codec: Video codec (default libx264). Cannot use 'copy'.

    Returns:
        OperationResult with the output path.
    """
    if not entries:
        raise CutAgentError(
            code=EMPTY_TEXT_ENTRIES,
            message="No text entries provided — at least one is required",
            recovery=recovery_hints(EMPTY_TEXT_ENTRIES),
        )

    for entry in entries:
        if entry.font_size <= 0:
            raise CutAgentError(
                code=INVALID_FONT_SIZE,
                message=f"font_size must be > 0, got {entry.font_size}",
                recovery=recovery_hints(INVALID_FONT_SIZE),
                context={"font_size": entry.font_size},
            )

    info = probe_file(source)

    # Build chained drawtext filters separated by commas
    filters = [_build_drawtext_filter(e) for e in entries]
    vf = ",".join(filters)

    args = ["-i", source, "-vf", vf, "-c:v", codec, "-c:a", "aac", output]
    run_ffmpeg(args)

    return OperationResult(
        success=True,
        output_path=output,
        duration_seconds=info.duration,
    )
