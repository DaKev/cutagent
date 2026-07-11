"""AI tool definitions and JSON Schemas for CutAgent."""

import json
from typing import Any

from cutagent.cli.system import capabilities_payload
from cutagent.schema_registry import operation_names, schema_index


def get_tool_schema(tool_name: str) -> dict[str, Any]:
    """Return the JSON schema tool definition for a given tool.

    Available tools:
    - cutagent_capabilities
    - cutagent_probe
    - cutagent_summarize
    - cutagent_validate
    - cutagent_execute
    """
    schemas = {
        "cutagent_capabilities": {
            "type": "function",
            "function": {
                "name": "cutagent_capabilities",
                "description": (
                    "Discover video editing capabilities, operations, and EDL schemas. "
                    "Call this first."
                ),
                "output_schema": capabilities_payload(),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        "cutagent_probe": {
            "type": "function",
            "function": {
                "name": "cutagent_probe",
                "description": "Probe media metadata: duration, resolution, codecs, and streams.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Path to the media file",
                        },
                    },
                    "required": ["file"],
                },
            },
        },
        "cutagent_summarize": {
            "type": "function",
            "function": {
                "name": "cutagent_summarize",
                "description": (
                    "Build a content summary with scenes, silences, and suggested cuts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Path to the media file",
                        },
                        "scene_threshold": {
                            "type": "number",
                            "description": "Scene detection threshold (default 0.3)",
                            "default": 0.3,
                        },
                    },
                    "required": ["file"],
                },
            },
        },
        "cutagent_validate": {
            "type": "function",
            "function": {
                "name": "cutagent_validate",
                "description": "Validate an EDL without executing it. Run before execute.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "edl_json": {
                            "type": "string",
                            "description": "The full EDL JSON string to validate",
                        },
                    },
                    "required": ["edl_json"],
                },
            },
        },
        "cutagent_execute": {
            "type": "function",
            "function": {
                "name": "cutagent_execute",
                "description": "Execute an Edit Decision List (EDL).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "edl_json": {
                            "type": "string",
                            "description": "The full EDL JSON string to execute",
                        },
                    },
                    "required": ["edl_json"],
                },
            },
        },
        "cutagent_schema": {
            "type": "function",
            "function": {
                "name": "cutagent_schema",
                "description": "Query schema metadata for commands, EDL, and operation payloads.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "enum": schema_index()["targets"],
                            "description": "Schema target to inspect",
                        },
                        "name": {
                            "type": "string",
                            "description": "Optional name, such as an operation name",
                        },
                    },
                    "required": ["target"],
                },
            },
        },
        "cutagent_op": {
            "type": "function",
            "function": {
                "name": "cutagent_op",
                "description": "Execute a single EDL operation via payload-first JSON envelope.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": operation_names(),
                            "description": "Operation name",
                        },
                        "payload": {
                            "type": "object",
                            "description": "Operation payload including output spec",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "default": False,
                            "description": "Validate only without mutating media",
                        },
                    },
                    "required": ["name", "payload"],
                },
            },
        },
    }

    if tool_name not in schemas:
        raise ValueError(f"Unknown tool: {tool_name}")

    return schemas[tool_name]


def dump_all_schemas() -> str:
    """Return a JSON array of all tool definitions for easy ingestion by AI agents."""
    return json.dumps(
        [
            get_tool_schema("cutagent_capabilities"),
            get_tool_schema("cutagent_probe"),
            get_tool_schema("cutagent_summarize"),
            get_tool_schema("cutagent_schema"),
            get_tool_schema("cutagent_op"),
            get_tool_schema("cutagent_validate"),
            get_tool_schema("cutagent_execute"),
        ],
        indent=2,
    )
