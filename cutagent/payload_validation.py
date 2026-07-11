"""Validation and input hardening for payload-first operation requests."""

from __future__ import annotations

from typing import Any

from cutagent.errors import CutAgentError
from cutagent.input_hardening import reject_control_chars, validate_resource_token

_RESOURCE_KEYS = {"id", "source", "audio", "path", "file", "output"}


def _harden_payload(value: Any, key_hint: str | None = None) -> Any:
    """Recursively harden payload values against malformed agent input."""
    if isinstance(value, str):
        field_name = key_hint or "value"
        reject_control_chars(value, field_name)
        if key_hint in _RESOURCE_KEYS:
            validate_resource_token(value, field_name)
        return value
    if isinstance(value, list):
        return [_harden_payload(item, key_hint) for item in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            reject_control_chars(str(key), "key")
            out[key] = _harden_payload(item, key)
        return out
    return value


def _validate_payload_against_schema(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate an operation payload against its runtime JSON schema."""
    required = set(schema.get("required", []))
    missing = [name for name in required if name not in payload]
    if missing:
        raise CutAgentError(
            code="MISSING_FIELD",
            message=f"Missing required payload fields: {', '.join(missing)}",
            recovery=["Inspect schema with: cutagent schema operation <name>"],
            context={"missing_fields": missing},
        )
    _validate_value_against_schema(payload, schema, "")


def _validate_operation_semantics(name: str, payload: dict[str, Any]) -> None:
    """Validate conditional requirements that JSON Schema cannot express concisely."""
    if name != "animate":
        return
    layers = payload.get("layers", [])
    if not isinstance(layers, list):
        return

    missing_fields: list[str] = []
    for idx, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        layer_type = layer.get("type")
        if layer_type == "text" and not layer.get("text"):
            missing_fields.append(f"layers[{idx}].text")
        elif layer_type == "image" and not layer.get("path"):
            missing_fields.append(f"layers[{idx}].path")
    if missing_fields:
        raise CutAgentError(
            code="MISSING_FIELD",
            message=f"Missing required payload fields: {', '.join(missing_fields)}",
            recovery=["Inspect schema with: cutagent schema operation animate"],
            context={"missing_fields": missing_fields},
        )


def _validate_value_against_schema(value: Any, schema: dict[str, Any], field: str) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_json_type(value, expected_type):
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message=f"{field or 'payload'} must be a JSON {expected_type}",
            recovery=["Inspect schema with: cutagent schema operation <name>"],
            context={"field": field or "payload", "expected_type": expected_type},
        )
    if "enum" in schema and value not in schema["enum"]:
        allowed = list(schema["enum"])
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message=f"{field or 'payload'} must be one of: {', '.join(map(str, allowed))}",
            recovery=["Use one of the allowed schema enum values"],
            context={"field": field or "payload", "allowed": allowed, "value": value},
        )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        _validate_numeric_bounds(value, schema, field or "payload")
    if isinstance(value, dict):
        _validate_object_against_schema(value, schema, field)
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                item_field = f"{field}[{idx}]" if field else f"[{idx}]"
                _validate_value_against_schema(item, item_schema, item_field)


def _validate_object_against_schema(
    value: dict[str, Any], schema: dict[str, Any], field: str
) -> None:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    missing = [name for name in required if name not in value]
    if missing:
        prefix = f"{field}." if field else ""
        missing_fields = [f"{prefix}{name}" for name in missing]
        raise CutAgentError(
            code="MISSING_FIELD",
            message=f"Missing required payload fields: {', '.join(missing_fields)}",
            recovery=["Inspect schema with: cutagent schema operation <name>"],
            context={"missing_fields": missing_fields},
        )

    additional_properties = schema.get("additionalProperties", True)
    if additional_properties is False:
        extras = sorted(k for k in value if k not in properties)
        if extras:
            prefix = f"{field}." if field else ""
            unknown_fields = [f"{prefix}{name}" for name in extras]
            raise CutAgentError(
                code="INVALID_ARGUMENT",
                message=f"Unknown payload fields: {', '.join(unknown_fields)}",
                recovery=["Inspect schema with: cutagent schema operation <name>"],
                context={"unknown_fields": unknown_fields},
            )

    for key, item in value.items():
        child_schema = properties.get(key)
        if child_schema is None and isinstance(additional_properties, dict):
            child_schema = additional_properties
        if isinstance(child_schema, dict):
            child_field = f"{field}.{key}" if field else key
            _validate_value_against_schema(item, child_schema, child_field)


def _validate_numeric_bounds(value: int | float, schema: dict[str, Any], field: str) -> None:
    minimum = schema.get("minimum")
    if minimum is not None and value < minimum:
        _raise_bound_error(field, "minimum", minimum, value, ">=")
    exclusive_minimum = schema.get("exclusiveMinimum")
    if exclusive_minimum is not None and value <= exclusive_minimum:
        _raise_bound_error(field, "exclusiveMinimum", exclusive_minimum, value, ">")
    maximum = schema.get("maximum")
    if maximum is not None and value > maximum:
        _raise_bound_error(field, "maximum", maximum, value, "<=")


def _raise_bound_error(
    field: str, keyword: str, bound: int | float, value: int | float, operator: str
) -> None:
    raise CutAgentError(
        code="INVALID_ARGUMENT",
        message=f"{field} must be {operator} {bound}",
        recovery=["Use a value within the schema bounds"],
        context={"field": field, keyword: bound, "value": value},
    )


def _matches_json_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True
