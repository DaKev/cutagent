"""AI-native CLI using Typer — every command outputs JSON/NDJSON to stdout."""

import json
import sys
from pathlib import Path
from typing import Any

from cutagent.errors import EXIT_EXECUTION, EXIT_SUCCESS, CutAgentError, exit_code_for_error
from cutagent.input_hardening import (
    apply_field_mask,
    sanitize_data,
    to_ndjson,
    validate_resource_token,
    validate_safe_output_path,
)

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
    print(json.dumps(data, indent=2))
    sys.stdout.flush()
    return exit_code

def json_error(exc: CutAgentError, exit_code: int | None = None) -> int:
    """Print a CutAgentError as JSON and return the appropriate exit code."""
    resolved_code = exit_code if exit_code is not None else exit_code_for_error(exc.code)
    return json_out(exc.to_dict(), resolved_code)

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
        validate_resource_token(file_path, file_attr)
        return Path(file_path).read_text()
    raise CutAgentError(
        code="MISSING_FIELD",
        message=f"Either --{json_attr.replace('_', '-')} or --{file_attr.replace('_', '-')} is required",
        recovery=[f"Provide one of --{json_attr.replace('_', '-')} or --{file_attr.replace('_', '-')}"]
    )


def json_out_shaped(
    data: dict[str, Any] | list[Any],
    exit_code: int = EXIT_SUCCESS,
    *,
    fields: str | None = None,
    response_format: str = "json",
    ndjson_key: str | None = None,
    sanitize_mode: str | None = None,
) -> int:
    """Print shaped JSON or NDJSON output and return an exit code."""
    sanitized = sanitize_data(data, sanitize_mode)
    projected = apply_field_mask(sanitized, fields)
    if response_format == "ndjson":
        print(to_ndjson(projected, list_key=ndjson_key))
    else:
        print(json.dumps(projected, indent=2))
    sys.stdout.flush()
    return exit_code


def validate_output_arg(path_value: str, field_name: str = "output") -> str:
    """Validate and normalize CLI output path arguments."""
    return validate_safe_output_path(path_value, field_name=field_name)

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
