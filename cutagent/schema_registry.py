"""Machine-readable schema registry for agent-first CLI usage."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from cutagent import discovery_schema
from cutagent.models import OPERATION_TYPES

_COMMON_ENVELOPE_PROPERTIES: dict[str, Any] = {
    "inputs": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional explicit input files used with $input.N references",
    },
    "output": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "codec": {"type": "string", "default": "copy"},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}

_TEXT_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "position": {"type": "string"},
        "font_size": {"type": "integer", "exclusiveMinimum": 0},
        "font_color": {"type": "string"},
        "start": {"type": "string"},
        "end": {"type": "string"},
        "bg_color": {"type": "string"},
        "bg_padding": {"type": "integer", "minimum": 0},
        "font": {"type": "string"},
        "shadow_color": {"type": "string"},
        "shadow_offset": {"type": "integer", "minimum": 0},
        "stroke_color": {"type": "string"},
        "stroke_width": {"type": "integer", "minimum": 0},
    },
    "required": ["text"],
    "additionalProperties": False,
}

_ANIMATION_KEYFRAME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "t": {"type": "number"},
        "value": {"type": "number"},
    },
    "required": ["t", "value"],
    "additionalProperties": False,
}

_ANIMATION_PROPERTY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "keyframes": {"type": "array", "items": _ANIMATION_KEYFRAME_SCHEMA},
        "easing": {
            "type": "string",
            "enum": ["linear", "ease-in", "ease-out", "ease-in-out", "spring"],
        },
    },
    "required": ["keyframes"],
    "additionalProperties": False,
}

_ANIMATION_LAYER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["text", "image"]},
        "start": {"type": "number"},
        "end": {"type": "number"},
        "properties": {
            "type": "object",
            "additionalProperties": _ANIMATION_PROPERTY_SCHEMA,
        },
        "text": {"type": "string"},
        "font_size": {"type": "integer", "exclusiveMinimum": 0},
        "font_color": {"type": "string"},
        "font": {"type": "string"},
        "bg_color": {"type": "string"},
        "bg_padding": {"type": "integer", "minimum": 0},
        "shadow_color": {"type": "string"},
        "shadow_offset": {"type": "integer", "minimum": 0},
        "stroke_color": {"type": "string"},
        "stroke_width": {"type": "integer", "minimum": 0},
        "path": {"type": "string"},
    },
    "required": ["type", "properties"],
    "additionalProperties": False,
}


_OPERATION_CORE_SCHEMAS: dict[str, dict[str, Any]] = {
    "trim": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "start": {"type": "string"},
            "end": {"type": "string"},
            "id": {"type": "string"},
        },
        "required": ["source", "start", "end"],
        "additionalProperties": False,
    },
    "split": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "points": {"type": "array", "items": {"type": "string"}},
            "id": {"type": "string"},
        },
        "required": ["source", "points"],
        "additionalProperties": False,
    },
    "concat": {
        "type": "object",
        "properties": {
            "segments": {"type": "array", "items": {"type": "string"}},
            "id": {"type": "string"},
            "transition": {"type": "string", "enum": ["crossfade"]},
            "transition_duration": {"type": "number", "exclusiveMinimum": 0},
        },
        "required": ["segments"],
        "additionalProperties": False,
    },
    "reorder": {
        "type": "object",
        "properties": {
            "segments": {"type": "array", "items": {"type": "string"}},
            "order": {"type": "array", "items": {"type": "integer"}},
            "id": {"type": "string"},
        },
        "required": ["segments", "order"],
        "additionalProperties": False,
    },
    "extract": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "stream": {"type": "string", "enum": ["audio", "video"]},
            "id": {"type": "string"},
        },
        "required": ["source", "stream"],
        "additionalProperties": False,
    },
    "fade": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "fade_in": {"type": "number", "minimum": 0},
            "fade_out": {"type": "number", "minimum": 0},
            "id": {"type": "string"},
        },
        "required": ["source"],
        "additionalProperties": False,
    },
    "speed": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "factor": {"type": "number", "minimum": 0.25, "maximum": 100.0},
            "id": {"type": "string"},
        },
        "required": ["source", "factor"],
        "additionalProperties": False,
    },
    "crop": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "x": {"type": "integer", "minimum": 0},
            "y": {"type": "integer", "minimum": 0},
            "width": {"type": "integer", "exclusiveMinimum": 0},
            "height": {"type": "integer", "exclusiveMinimum": 0},
            "id": {"type": "string"},
        },
        "required": ["source", "x", "y", "width", "height"],
        "additionalProperties": False,
    },
    "resize": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "width": {"type": "integer", "exclusiveMinimum": 0},
            "height": {"type": "integer", "exclusiveMinimum": 0},
            "fit": {"type": "string", "enum": ["contain", "stretch"], "default": "contain"},
            "background_color": {"type": "string", "default": "black"},
            "id": {"type": "string"},
        },
        "required": ["source", "width", "height"],
        "additionalProperties": False,
    },
    "mix_audio": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "audio": {"type": "string"},
            "mix_level": {"type": "number", "minimum": 0, "maximum": 1},
            "id": {"type": "string"},
        },
        "required": ["source", "audio"],
        "additionalProperties": False,
    },
    "volume": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "gain_db": {"type": "number", "minimum": -60, "maximum": 60},
            "id": {"type": "string"},
        },
        "required": ["source", "gain_db"],
        "additionalProperties": False,
    },
    "replace_audio": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "audio": {"type": "string"},
            "id": {"type": "string"},
        },
        "required": ["source", "audio"],
        "additionalProperties": False,
    },
    "normalize": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "target_lufs": {"type": "number", "minimum": -70, "maximum": -5},
            "true_peak_dbtp": {"type": "number", "minimum": -10, "maximum": 0},
            "id": {"type": "string"},
        },
        "required": ["source"],
        "additionalProperties": False,
    },
    "text": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "entries": {"type": "array", "items": _TEXT_ENTRY_SCHEMA},
            "id": {"type": "string"},
        },
        "required": ["source", "entries"],
        "additionalProperties": False,
    },
    "animate": {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "fps": {"type": "integer", "minimum": 1},
            "layers": {"type": "array", "items": _ANIMATION_LAYER_SCHEMA},
            "id": {"type": "string"},
        },
        "required": ["source", "layers"],
        "additionalProperties": False,
    },
}


def operation_names() -> list[str]:
    """Return supported operation names from the typed model registry."""
    return sorted(list(OPERATION_TYPES.keys()))


def operation_payload_schema(op_name: str) -> dict[str, Any]:
    """Return the payload schema for `cutagent op <name> --json`."""
    if op_name not in _OPERATION_CORE_SCHEMAS:
        raise ValueError(f"Unknown operation: {op_name}")
    schema = deepcopy(_OPERATION_CORE_SCHEMAS[op_name])
    schema["properties"] = {**_COMMON_ENVELOPE_PROPERTIES, **schema["properties"]}
    schema["required"] = list(schema["required"]) + ["output"]
    return schema


def edl_schema() -> dict[str, Any]:
    """Return a machine-readable EDL schema summary."""
    output_schema = deepcopy(_COMMON_ENVELOPE_PROPERTIES["output"])
    return discovery_schema._edl_schema(operation_names(), output_schema)


def cli_command_schema() -> dict[str, Any]:
    """Return schema metadata for agent-first top-level commands."""
    return discovery_schema._cli_command_schema()


def analysis_command_schema() -> discovery_schema.AnalysisCommandSchema:
    """Return typed metadata for analysis CLI output shaping."""
    return discovery_schema._analysis_command_schema()


def schema_index() -> dict[str, Any]:
    """Return an index of available schema targets."""
    return discovery_schema._schema_index(operation_names())
