"""Agent-first payload commands."""

from __future__ import annotations

import json
from typing import Optional

import typer

from cutagent.cli.utils import (
    JsonTyperCommand,
    json_error,
    json_out_shaped,
    read_json_arg,
    validate_output_arg,
)
from cutagent.errors import EXIT_VALIDATION, CutAgentError
from cutagent.input_hardening import safe_json_loads
from cutagent.payload_validation import (
    _harden_payload,
    _validate_operation_semantics,
    _validate_payload_against_schema,
)
from cutagent.schema_registry import operation_payload_schema

app = typer.Typer(help="Payload-first commands for AI agents")

@app.command("op", cls=JsonTyperCommand)
def cmd_op(
    name: str = typer.Argument(..., help="Operation name"),
    json_payload: Optional[str] = typer.Option(
        None,
        "--json",
        help="Inline operation payload JSON",
    ),
    params_file: Optional[str] = typer.Option(
        None,
        "--params-file",
        help="Path to operation payload JSON",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate only, do not execute media mutation",
    ),
    sanitize_output: Optional[str] = typer.Option(
        None,
        "--sanitize-output",
        help="Optional output sanitization mode (basic)",
    ),
) -> int:
    """Execute one operation using a raw JSON payload envelope."""
    from cutagent.engine import execute_edl
    from cutagent.validation import validate_edl

    try:
        schema = operation_payload_schema(name)
        raw_payload = read_json_arg(json_payload, params_file, "json", "params_file")
        parsed = safe_json_loads(raw_payload, "json")
        if not isinstance(parsed, dict):
            raise CutAgentError(
                code="INVALID_ARGUMENT",
                message="Operation payload must be a JSON object",
                recovery=["Wrap payload fields in a JSON object"],
            )

        payload = _harden_payload(parsed)
        _validate_payload_against_schema(payload, schema)
        _validate_operation_semantics(name, payload)

        output = payload["output"]
        if not isinstance(output, dict):
            raise CutAgentError(
                code="INVALID_ARGUMENT",
                message="'output' must be a JSON object with at least {\"path\": ...}",
                recovery=['Use output format: {"path": "out.mp4", "codec": "copy"}'],
            )
        if "path" not in output:
            raise CutAgentError(
                code="MISSING_FIELD",
                message="Missing output.path",
                recovery=["Provide output.path in payload"],
            )
        output_path = validate_output_arg(str(output["path"]), "output.path")
        output_codec = str(output.get("codec", "copy"))

        inputs = payload.get("inputs", [])
        if not isinstance(inputs, list) or not all(isinstance(x, str) for x in inputs):
            raise CutAgentError(
                code="INVALID_ARGUMENT",
                message="'inputs' must be an array of file path strings",
                recovery=['Provide inputs like: ["video.mp4", "music.mp3"]'],
            )

        op_data = {k: v for k, v in payload.items() if k not in {"inputs", "output"}}
        op_data["op"] = name

        edl_doc = {
            "version": "1.0",
            "inputs": inputs,
            "operations": [op_data],
            "output": {"path": output_path, "codec": output_codec},
        }
        edl_text = json.dumps(edl_doc)

        if dry_run:
            validation = validate_edl(edl_text)
            code = 0 if validation.valid else EXIT_VALIDATION
            return json_out_shaped(
                {
                    "dry_run": True,
                    "operation": name,
                    "validation": validation.to_dict(),
                    "edl": edl_doc,
                },
                code,
                sanitize_mode=sanitize_output,
            )

        result = execute_edl(edl_text)
        out = result.to_dict()
        out["operation"] = name
        out["dry_run"] = False
        return json_out_shaped(out, sanitize_mode=sanitize_output)
    except CutAgentError as exc:
        return json_error(exc)
