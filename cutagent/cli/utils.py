"""AI-native CLI using Typer — every command outputs JSON/NDJSON to stdout."""

import json
import sys
from pathlib import Path
from typing import Any

import click
from typer.core import TyperCommand, TyperGroup

from cutagent.errors import EXIT_SUCCESS, CutAgentError, exit_code_for_error
from cutagent.input_hardening import (
    apply_field_mask,
    sanitize_data,
    to_ndjson,
    validate_resource_token,
    validate_safe_output_path,
)

# Ensure we define the same variables as the old cli to avoid import errors
__all__ = [
    "JsonTyperCommand",
    "JsonTyperGroup",
    "json_out",
    "json_error",
    "read_json_arg",
    "review_timestamps_from_entries",
    "text_layer_summary",
    "review_timestamps_from_layers",
    "animate_layer_summary",
]


def _parameter_help(param: click.Parameter) -> dict[str, Any]:
    """Build a JSON-safe description of one CLI parameter."""
    item: dict[str, Any] = {
        "name": param.name,
        "kind": "option" if isinstance(param, click.Option) else "argument",
        "required": param.required,
        "type": param.type.name,
    }
    if isinstance(param, click.Option):
        item["flags"] = [*param.opts, *param.secondary_opts]
        item["help"] = param.help
        if param.default is not None:
            item["default"] = param.default
    elif param.nargs != 1:
        item["nargs"] = param.nargs
    return item


def _command_help(ctx: click.Context) -> dict[str, Any]:
    """Return machine-readable help for the current Click command."""
    command = ctx.command
    command_path = ctx.command_path
    marker = command_path.rfind("cutagent")
    canonical_path = command_path[marker:] if marker >= 0 else command_path
    usage = command.get_usage(ctx).strip().replace(command_path, canonical_path, 1)
    payload: dict[str, Any] = {
        "command": canonical_path,
        "description": command.help or "",
        "usage": usage,
        "parameters": [
            _parameter_help(param)
            for param in command.get_params(ctx)
            if not (isinstance(param, click.Option) and param.name == "help")
        ],
    }
    if isinstance(command, click.Group):
        payload["commands"] = [
            {
                "name": name,
                "description": (subcommand.get_short_help_str() if subcommand else ""),
            }
            for name in command.list_commands(ctx)
            if (subcommand := command.get_command(ctx, name)) is not None
            and not subcommand.hidden
        ]
    payload["discovery"] = {
        "command_schema": "cutagent schema command",
        "analysis_schema": "cutagent schema analysis",
    }
    return payload


class _JsonHelpMixin:
    """Render Click/Typer help as JSON to preserve the CLI output contract."""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Write machine-readable command help."""
        formatter.write(json.dumps(_command_help(ctx), indent=2))
        formatter.write("\n")


class JsonTyperCommand(_JsonHelpMixin, TyperCommand):
    """Typer command whose ``--help`` output is JSON."""


class JsonTyperGroup(_JsonHelpMixin, TyperGroup):
    """Typer group whose ``--help`` output is JSON."""


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
    json_flag = f"--{json_attr.replace('_', '-')}"
    file_flag = f"--{file_attr.replace('_', '-')}"
    if inline is not None and file_path is not None:
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message=f"Cannot use both {json_flag} and {file_flag}",
            recovery=[f"Provide only one of {json_flag} or {file_flag}"],
        )
    if inline is not None:
        return inline
    if file_path is not None:
        validate_resource_token(file_path, file_attr)
        return Path(file_path).read_text()
    raise CutAgentError(
        code="MISSING_FIELD",
        message=f"Either {json_flag} or {file_flag} is required",
        recovery=[f"Provide one of {json_flag} or {file_flag}"],
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
