"""AI-native CLI using Typer — every command outputs JSON to stdout."""

import json
from pathlib import Path
from typing import Any

from cutagent.errors import EXIT_EXECUTION, EXIT_SUCCESS, CutAgentError

# Ensure we define the same variables as the old cli to avoid import errors
__all__ = [
    "json_out",
    "json_error",
    "read_json_arg",
    "review_timestamps_from_entries",
    "text_layer_summary",
    "review_timestamps_from_layers",
    "animate_layer_summary",
]

def json_out(data: dict[str, Any], exit_code: int = EXIT_SUCCESS) -> int:
    """Print JSON to stdout and return exit code."""
    import sys
    print(json.dumps(data, indent=2))
    sys.stdout.flush()
    return exit_code

def json_error(exc: CutAgentError, exit_code: int = EXIT_EXECUTION) -> int:
    """Print a CutAgentError as JSON and return the appropriate exit code."""
    return json_out(exc.to_dict(), exit_code)

def read_json_arg(inline: str | None, file_path: str | None, json_attr: str, file_attr: str) -> str:
    """Read JSON from either inline or file argument. Mutually exclusive."""
    if inline is not None and file_path is not None:
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message=f"Cannot use both --{json_attr.replace('_', '-')} and --{file_attr.replace('_', '-')}",
            recovery=[f"Provide only one of --{json_attr.replace('_', '-')} or --{file_attr.replace('_', '-')}"],
        )
    if inline is not None:
        return inline
    if file_path is not None:
        return Path(file_path).read_text()
    raise CutAgentError(
        code="MISSING_FIELD",
        message=f"Either --{json_attr.replace('_', '-')} or --{file_attr.replace('_', '-')} is required",
        recovery=[f"Provide one of --{json_attr.replace('_', '-')} or --{file_attr.replace('_', '-')}"]
    )

def review_timestamps_from_entries(entries: list[Any]) -> list[float]:
    """Compute midpoint timestamps for visual review of text entries."""
    from cutagent.models import parse_time
    timestamps = []
    for entry in entries:
        start = parse_time(entry.start) if entry.start else 0.0
        end = parse_time(entry.end) if entry.end else start + 5.0
        timestamps.append(round((start + end) / 2, 3))
    return timestamps

def text_layer_summary(entries: list[Any]) -> list[dict[str, Any]]:
    """Build a concise layer summary from TextEntry objects."""
    from cutagent.models import parse_time
    summary: list[dict[str, Any]] = []
    for entry in entries:
        start = parse_time(entry.start) if entry.start else 0.0
        end = parse_time(entry.end) if entry.end else None
        d: dict[str, Any] = {"text": entry.text, "start": start}
        if end is not None:
            d["end"] = end
        summary.append(d)
    return summary

def review_timestamps_from_layers(layers: list[Any]) -> list[float]:
    """Compute midpoint timestamps for visual review of animation layers."""
    return [round((layer.start + layer.end) / 2, 3) for layer in layers]

def animate_layer_summary(layers: list[Any]) -> list[dict[str, Any]]:
    """Build a concise layer summary from AnimationLayer objects."""
    summary: list[dict[str, Any]] = []
    for layer in layers:
        d: dict[str, Any] = {"type": layer.type, "start": layer.start, "end": layer.end}
        if layer.type == "text" and getattr(layer, "text", None):
            d["text"] = layer.text
        summary.append(d)
    return summary
