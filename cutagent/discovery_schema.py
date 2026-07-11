"""Machine-readable schemas for CLI and analysis capability discovery."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisCommandSchema:
    """Typed container for analysis command discovery metadata."""

    commands: dict[str, dict[str, Any]]
    response_format: dict[str, str]
    field_masks: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "commands": deepcopy(self.commands),
            "response_format": dict(self.response_format),
            "field_masks": self.field_masks,
        }


def _edl_schema(operation_names: list[str], output_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "version": {"type": "string", "enum": ["1.0"]},
            "inputs": {"type": "array", "items": {"type": "string"}},
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"op": {"type": "string", "enum": operation_names}},
                    "required": ["op"],
                },
            },
            "output": output_schema,
        },
        "required": ["version", "inputs", "operations", "output"],
        "additionalProperties": False,
        "references": {
            "$input.N": "Reference input file by index",
            "$N": "Reference prior operation output by index",
            "$name": "Reference prior operation output by operation id",
            "$N.M": "Reference segment M from split operation N",
        },
    }


def _cli_command_schema() -> dict[str, Any]:
    return {
        "commands": {
            "capabilities": {"args": [], "output": "json"},
            "schema": {
                "args": ["target", "name?"],
                "targets": ["index", "edl", "operation", "command", "analysis", "capabilities"],
                "output": "json",
            },
            "op": {
                "args": ["name"],
                "options": ["--json", "--params-file", "--dry-run", "--sanitize-output"],
                "output": "json",
            },
            "validate": {"args": ["edl?"], "options": ["--edl-json"], "output": "json"},
            "execute": {
                "args": ["edl?"],
                "options": ["--edl-json", "--dry-run", "--sanitize-output", "--quiet"],
                "output": "json",
            },
        }
    }


def _analysis_command_schema() -> AnalysisCommandSchema:
    shaped = {"fields": True, "response_format": ["json", "ndjson"]}
    commands: dict[str, dict[str, Any]] = {
        "probe": {
            "description": "Probe a media file for metadata",
            "options": ["--fields", "--response-format"],
            "supports": shaped,
            "list_key": None,
        },
        "summarize": {
            "description": "Generate a unified content map",
            "options": [
                "--frame-dir",
                "--scene-threshold",
                "--silence-threshold",
                "--min-silence-duration",
                "--audio-interval",
                "--include-audio-levels",
                "--fields",
                "--response-format",
            ],
            "supports": shaped,
            "list_key": None,
        },
        "scenes": {
            "description": "Detect scene boundaries",
            "options": ["--threshold", "--output-dir", "--fields", "--response-format"],
            "supports": shaped,
            "list_key": "scenes",
        },
        "silence": {
            "description": "Detect silence intervals",
            "options": [
                "--threshold",
                "--min-duration",
                "--limit",
                "--fields",
                "--response-format",
            ],
            "supports": shaped | {"limit": True},
            "list_key": "silences",
        },
        "beats": {
            "description": "Detect musical beats/onsets in audio",
            "options": [
                "--min-interval",
                "--energy-threshold",
                "--min-strength",
                "--limit",
                "--fields",
                "--response-format",
            ],
            "supports": shaped | {"limit": True, "min_strength": True},
            "list_key": "beats",
        },
        "keyframes": {
            "description": "List keyframe timestamps",
            "options": ["--limit", "--fields", "--response-format"],
            "supports": shaped | {"limit": True},
            "list_key": "keyframes",
        },
        "audio-levels": {
            "description": "Compute audio levels over time",
            "options": ["--interval", "--limit", "--fields", "--response-format"],
            "supports": shaped | {"interval": True, "limit": True},
            "list_key": "audio_levels",
        },
        "frames": {
            "description": "Extract still frames at specific timestamps",
            "options": [
                "--output-dir",
                "--at",
                "--count",
                "--interval",
                "--format",
                "--fields",
                "--response-format",
            ],
            "supports": shaped | {"count": True, "interval": True},
            "list_key": "frames",
        },
        "thumbnail": {
            "description": "Extract a single thumbnail frame",
            "options": ["--time", "--at", "--output", "--fields", "--response-format"],
            "supports": shaped,
            "list_key": None,
        },
    }
    return AnalysisCommandSchema(
        commands=commands,
        response_format={
            "json": "Pretty-printed JSON object on stdout",
            "ndjson": "One compact JSON item per line for list-heavy responses",
        },
        field_masks=(
            "Comma-separated top-level or dotted fields, e.g. "
            "path,duration or summary.scenes"
        ),
    )


def _schema_index(operation_names: list[str]) -> dict[str, Any]:
    return {
        "targets": ["index", "edl", "operation", "command", "analysis", "capabilities"],
        "operations": operation_names,
    }
