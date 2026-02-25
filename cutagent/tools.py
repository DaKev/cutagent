"""AI tool definitions and JSON Schemas for CutAgent."""

import json
from typing import Any


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
                "description": "Discover all available video editing capabilities, operations, and the exact JSON schema for the Edit Decision List (EDL). Call this first to understand how to use CutAgent.",
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
                "description": "Probe a media file for metadata, including duration, resolution, codecs, and streams.",
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
                "description": "Build a full content summary including scene boundaries, silence gaps, and suggested cut points.",
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
                "description": "Validate an Edit Decision List (EDL) without executing it. Always run this before execute to catch errors early.",
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
                "description": "Execute an Edit Decision List (EDL) to perform the actual video editing operations.",
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
    }

    if tool_name not in schemas:
        raise ValueError(f"Unknown tool: {tool_name}")

    return schemas[tool_name]

def dump_all_schemas() -> str:
    """Return a JSON array of all tool definitions for easy ingestion by AI agents."""
    return json.dumps([
        get_tool_schema("cutagent_capabilities"),
        get_tool_schema("cutagent_probe"),
        get_tool_schema("cutagent_summarize"),
        get_tool_schema("cutagent_validate"),
        get_tool_schema("cutagent_execute"),
    ], indent=2)
