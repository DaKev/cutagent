"""Input hardening and output-shaping helpers for agent-facing CLI paths."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cutagent.errors import CutAgentError

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+previous\s+instructions|ignore\s+all\s+instructions|system\s+prompt|developer\s+message)",
    flags=re.IGNORECASE,
)


def reject_control_chars(value: str, field_name: str) -> None:
    """Reject strings containing non-printable control characters."""
    if _CONTROL_CHAR_RE.search(value):
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message=f"{field_name} contains control characters",
            recovery=[
                "Remove non-printable characters from the input",
                "Ensure values are plain UTF-8 text",
            ],
            context={"field": field_name},
        )


def validate_resource_token(value: str, field_name: str) -> None:
    """Reject control characters while preserving valid filesystem names."""
    reject_control_chars(value, field_name)


def validate_safe_output_path(path_value: str, field_name: str = "output") -> str:
    """Validate and normalize output paths for CLI writes."""
    validate_resource_token(path_value, field_name)
    return str(Path(path_value).expanduser())


def safe_json_loads(raw: str, field_name: str) -> Any:
    """Strict JSON parsing with structured error output."""
    reject_control_chars(raw, field_name)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CutAgentError(
            code="INVALID_EDL" if field_name == "edl_json" else "INVALID_ARGUMENT",
            message=f"Invalid JSON in {field_name}: {exc}",
            recovery=[
                "Validate JSON syntax (quotes, commas, braces)",
                "Use a JSON file and pass it with --*-file for complex payloads",
            ],
            context={"field": field_name, "parse_error": str(exc)},
        ) from exc


def sanitize_text_value(value: str, mode: str | None) -> str:
    """Sanitize text fields when requested by the caller."""
    if mode != "basic":
        return value
    clean = _CONTROL_CHAR_RE.sub("", value)
    return _PROMPT_INJECTION_RE.sub("[sanitized]", clean)


def sanitize_data(data: Any, mode: str | None) -> Any:
    """Recursively sanitize response data when enabled."""
    if mode != "basic":
        return data
    if isinstance(data, str):
        return sanitize_text_value(data, mode)
    if isinstance(data, list):
        return [sanitize_data(item, mode) for item in data]
    if isinstance(data, dict):
        return {k: sanitize_data(v, mode) for k, v in data.items()}
    return data


def _assign_nested(target: dict[str, Any], keys: list[str], value: Any) -> None:
    cur = target
    for key in keys[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[keys[-1]] = value


def _extract_nested(source: Any, keys: list[str]) -> tuple[bool, Any]:
    cur = source
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return (False, None)
        cur = cur[key]
    return (True, cur)


def apply_field_mask(data: Any, fields: str | None) -> Any:
    """Project a JSON object to selected top-level or dotted fields."""
    if not fields:
        return data
    if not isinstance(data, dict):
        return data

    requested = [raw_field.strip() for raw_field in fields.split(",") if raw_field.strip()]
    if not requested:
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message="--fields must contain at least one field name",
            recovery=["Use a comma-separated field mask such as --fields path,duration"],
            context={"fields": fields},
        )

    projected: dict[str, Any] = {}
    unknown_fields: list[str] = []
    for field in requested:
        parts = [p for p in field.split(".") if p]
        if not parts:
            unknown_fields.append(field)
            continue
        found, value = _extract_nested(data, parts)
        if found:
            _assign_nested(projected, parts, value)
        else:
            unknown_fields.append(field)
    if unknown_fields:
        available_fields = sorted(data)
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message=f"Unknown field mask entries: {', '.join(unknown_fields)}",
            recovery=[
                f"Use available top-level fields: {', '.join(available_fields)}",
                "Run 'cutagent schema analysis' to inspect response-shaping support",
            ],
            context={"unknown_fields": unknown_fields, "available_fields": available_fields},
        )
    return projected


def to_ndjson(data: Any, list_key: str | None = None) -> str:
    """Serialize a result as newline-delimited JSON."""
    if isinstance(data, list):
        return "\n".join(json.dumps(item, separators=(",", ":")) for item in data)
    if isinstance(data, dict) and list_key and isinstance(data.get(list_key), list):
        return "\n".join(json.dumps(item, separators=(",", ":")) for item in data[list_key])
    return json.dumps(data, separators=(",", ":"))
