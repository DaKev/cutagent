"""EDL parser, reference resolver, and execution engine."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from cutagent.animation_ops import animate
from cutagent.audio_ops import adjust_volume, mix_audio, normalize_audio, replace_audio
from cutagent.errors import (
    INVALID_EDL,
    INVALID_REFERENCE,
    MISSING_FIELD,
    CutAgentError,
    recovery_hints,
)
from cutagent.models import (
    EDL,
    AnimateOp,
    ConcatOp,
    ExtractOp,
    FadeOp,
    MixAudioOp,
    NormalizeOp,
    OperationResult,
    ReorderOp,
    ReplaceAudioOp,
    SpeedOp,
    SplitOp,
    TextOp,
    TrimOp,
    VolumeOp,
)
from cutagent.operations import concat, extract_stream, fade, reorder, speed, split, trim
from cutagent.text_ops import add_text
from cutagent.input_hardening import (
    reject_control_chars,
    validate_resource_token,
    validate_safe_output_path,
)

# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------

_REF_PREFIX = "$"
_INPUT_REF_PREFIX = "$input."


def _is_reference(value: str) -> bool:
    """Check if a string is an operation reference like '$0', '$1'."""
    if not value.startswith(_REF_PREFIX):
        return False
    # Check if the part after $ is either a digit or digits.digits
    rest = value[1:]
    if rest.isdigit():
        return True
    if "." in rest:
        parts = rest.split(".", 1)
        return len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
    return False


def _is_input_reference(value: str) -> bool:
    """Check if a string is an input reference like '$input.0', '$input.1'."""
    return value.startswith(_INPUT_REF_PREFIX) and value[len(_INPUT_REF_PREFIX):].isdigit()


def _is_named_reference(value: str) -> bool:
    """Check if a string is a named operation reference like '$clip_a'."""
    if not value.startswith(_REF_PREFIX) or value.startswith(_INPUT_REF_PREFIX):
        return False
    name = value[1:]
    return bool(name) and not name[0].isdigit()


def _resolve_ref(value: str, results: dict[int, str], split_segments: dict[int, list[str]] | None = None) -> str:
    """Resolve a $N reference to the temp file path of that operation's output.

    If the reference has a sub-index like $N.M, it resolves to the Mth segment
    of a split operation.
    """
    if "." in value:
        base, sub_idx_str = value.split(".", 1)
        idx = int(base[1:])
        sub_idx = int(sub_idx_str)
        if split_segments is None or idx not in split_segments:
            raise CutAgentError(
                code=INVALID_REFERENCE,
                message=f"Reference {value} points to segment {sub_idx} of operation {idx}, which has no segments",
                recovery=["Use $N.M only for operations that return multiple segments (e.g. split)"],
                context={"reference": value},
            )
        segments = split_segments[idx]
        if sub_idx < 0 or sub_idx >= len(segments):
            raise CutAgentError(
                code=INVALID_REFERENCE,
                message=f"Reference {value} points to segment {sub_idx}, but operation {idx} only has {len(segments)} segments",
                recovery=[f"Use indices between 0 and {len(segments) - 1}"],
                context={"reference": value, "segments_count": len(segments)},
            )
        return segments[sub_idx]

    idx = int(value[1:])
    if idx not in results:
        raise CutAgentError(
            code=INVALID_REFERENCE,
            message=f"Reference {value} points to operation {idx}, which has no output",
            recovery=recovery_hints(INVALID_REFERENCE),
            context={"reference": value, "available": list(results.keys())},
        )
    return results[idx]


def _resolve_input_ref(value: str, inputs: list[str]) -> str:
    """Resolve a $input.N reference to the corresponding input file path."""
    idx = int(value[len(_INPUT_REF_PREFIX):])
    if idx < 0 or idx >= len(inputs):
        raise CutAgentError(
            code=INVALID_REFERENCE,
            message=f"Reference {value} points to input {idx}, but only {len(inputs)} inputs exist",
            recovery=[
                f"Use $input.0 through $input.{len(inputs) - 1}" if inputs else "Add inputs to the EDL",
            ],
            context={"reference": value, "input_count": len(inputs)},
        )
    return inputs[idx]


def _resolve_named_ref(value: str, named_results: dict[str, str]) -> str:
    """Resolve a $name reference to the output path of the named operation."""
    name = value[1:]
    if name not in named_results:
        raise CutAgentError(
            code=INVALID_REFERENCE,
            message=f"Named reference {value} not found — no prior operation has id={name!r}",
            recovery=[
                f"Available named operations: {list(named_results.keys())}" if named_results
                else "Add 'id' fields to operations to enable named references",
            ],
            context={"reference": value, "available_names": list(named_results.keys())},
        )
    return named_results[name]


def _resolve_source(
    value: str,
    results: dict[int, str],
    inputs: list[str] | None = None,
    named_results: dict[str, str] | None = None,
    split_segments: dict[int, list[str]] | None = None,
) -> str:
    """Resolve a source field — $input.N, $name, $N reference, or file path."""
    validate_resource_token(value, "source")
    if inputs is not None and _is_input_reference(value):
        return _resolve_input_ref(value, inputs)
    if _is_reference(value):
        return _resolve_ref(value, results, split_segments)
    if named_results is not None and _is_named_reference(value):
        return _resolve_named_ref(value, named_results)
    return value


def _resolve_segments(
    segments: list[str],
    results: dict[int, str],
    inputs: list[str] | None = None,
    named_results: dict[str, str] | None = None,
    split_segments: dict[int, list[str]] | None = None,
) -> list[str]:
    """Resolve a list of segments, replacing any $input.N, $name, or $N references."""
    return [_resolve_source(s, results, inputs, named_results, split_segments) for s in segments]


# ---------------------------------------------------------------------------
# EDL parsing
# ---------------------------------------------------------------------------

def parse_edl(raw: str | dict[str, Any]) -> EDL:
    """Parse a JSON string or dict into a validated EDL object.

    Args:
        raw: JSON string or already-parsed dict.

    Returns:
        Validated EDL dataclass.

    Raises:
        CutAgentError: If the EDL is malformed.
    """
    if isinstance(raw, str):
        reject_control_chars(raw, "edl")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CutAgentError(
                code=INVALID_EDL,
                message=f"Invalid JSON: {exc}",
                recovery=["Check JSON syntax — missing commas, brackets, or quotes"],
                context={"parse_error": str(exc)},
            ) from exc
    else:
        data = raw

    for required in ("version", "inputs", "operations", "output"):
        if required not in data:
            raise CutAgentError(
                code=MISSING_FIELD,
                message=f"EDL missing required field: '{required}'",
                recovery=[f"Add '{required}' to the top-level EDL object"],
                context={"missing_field": required},
            )

    return EDL.from_dict(data)


# ---------------------------------------------------------------------------
# EDL execution
# ---------------------------------------------------------------------------

def execute_edl(
    raw: str | dict[str, Any],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> OperationResult:
    """Parse and execute an Edit Decision List.

    Operations are executed sequentially. Each produces a temp file.
    $N references are resolved to the output of operation N.
    The final operation's output is copied to the EDL's output path.

    Args:
        raw: JSON string or dict representing the EDL.
        progress_callback: Optional callable(step, total, op_name, status)
            called before ("running") and after ("done") each operation.

    Returns:
        OperationResult for the full execution.
    """
    edl = parse_edl(raw)
    output_spec = edl.output
    output_path = validate_safe_output_path(output_spec.path, field_name="output.path")
    codec = output_spec.codec

    total_ops = len(edl.operations)

    # Track temp files for cleanup and reference resolution
    temp_dir = tempfile.mkdtemp(prefix="cutagent_")
    results: dict[int, str] = {}  # op_index -> output file path
    named_results: dict[str, str] = {}  # op_id -> output file path
    split_segments: dict[int, list[str]] = {}  # op_index -> list of segment output paths
    all_warnings: list[str] = []

    try:
        for idx, op in enumerate(edl.operations):
            op_name = getattr(op, "op", type(op).__name__)
            if progress_callback:
                progress_callback(idx + 1, total_ops, op_name, "running")

            result = _execute_operation(op, idx, results, temp_dir, codec, edl.inputs, named_results, split_segments)
            results[idx] = result.output_path
            if hasattr(result, "_split_segments"):
                split_segments[idx] = result._split_segments
            if getattr(op, "id", None):
                named_results[op.id] = result.output_path
            all_warnings.extend(result.warnings)

            if progress_callback:
                progress_callback(idx + 1, total_ops, op_name, "done")

        # Copy the last operation's output to the final destination
        if results:
            last_idx = len(edl.operations) - 1
            final_temp = results[last_idx]

            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_temp, output_path)
        else:
            raise CutAgentError(
                code=INVALID_EDL,
                message="EDL has no operations",
                recovery=["Add at least one operation to the EDL"],
            )

        return OperationResult(
            success=True,
            output_path=output_path,
            warnings=all_warnings,
        )

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def _execute_operation(
    op: Any,
    idx: int,
    results: dict[int, str],
    temp_dir: str,
    codec: str,
    inputs: list[str] | None = None,
    named_results: dict[str, str] | None = None,
    split_segments: dict[int, list[str]] | None = None,
) -> OperationResult:
    """Execute a single operation and return its result."""
    ext = ".mp4"  # default output extension
    nr = named_results or {}

    if isinstance(op, TrimOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return trim(source, op.start, op.end, out, codec=codec)

    if isinstance(op, SplitOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        prefix = str(Path(temp_dir) / f"op_{idx:03d}")
        split_results = split(source, op.points, prefix, codec=codec)
        if split_results:
            # We return the first segment as the default result for backward compatibility
            # but we register all segments so they can be referenced via $idx.0, $idx.1, etc.
            # E.g. $2 -> $2.0. If the user wants segment 1, they use $2.1
            res = split_results[0]
            # Monkey-patch an attribute so execute_edl can extract them if it wants,
            # though the cleaner way would be adjusting the resolution logic. Let's do it right.
            # Wait, our resolution logic relies on string keys for named_results or int keys for results.
            # We'll update the results dict after this function returns.
            setattr(res, "_split_segments", [s.output_path for s in split_results])
            return res
        return OperationResult(success=True, output_path=prefix)

    if isinstance(op, ConcatOp):
        segments = _resolve_segments(op.segments, results, inputs, nr, split_segments)
        ext = Path(segments[0]).suffix if segments else ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return concat(
            segments,
            out,
            codec=codec,
            transition=op.transition,
            transition_duration=op.transition_duration or 0.5,
        )

    if isinstance(op, ReorderOp):
        segments = _resolve_segments(op.segments, results, inputs, nr, split_segments)
        ext = Path(segments[0]).suffix if segments else ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return reorder(segments, op.order, out, codec=codec)

    if isinstance(op, ExtractOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = ".aac" if op.stream == "audio" else Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return extract_stream(source, op.stream, out)

    if isinstance(op, FadeOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = op.output or str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return fade(
            source,
            out,
            fade_in=op.fade_in,
            fade_out=op.fade_out,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, SpeedOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return speed(
            source,
            out,
            factor=op.factor,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, MixAudioOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        audio = _resolve_source(op.audio, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return mix_audio(
            source, audio, out,
            mix_level=op.mix_level,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, VolumeOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return adjust_volume(
            source, out,
            gain_db=op.gain_db,
            codec=codec,
        )

    if isinstance(op, ReplaceAudioOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        audio = _resolve_source(op.audio, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return replace_audio(source, audio, out, codec=codec)

    if isinstance(op, NormalizeOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return normalize_audio(
            source, out,
            target_lufs=op.target_lufs,
            true_peak_dbtp=op.true_peak_dbtp,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, TextOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return add_text(
            source, op.entries, out,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, AnimateOp):
        source = _resolve_source(op.source, results, inputs, nr, split_segments)
        for layer in op.layers:
            if layer.type == "image" and layer.path:
                layer.path = _resolve_source(layer.path, results, inputs, nr, split_segments)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return animate(
            source, op.layers, out,
            fps=op.fps,
            codec=codec if codec != "copy" else "libx264",
        )

    raise CutAgentError(
        code=INVALID_EDL,
        message=f"Unsupported operation at index {idx}: {type(op).__name__}",
        recovery=["Use one of: trim, split, concat, reorder, extract, fade, speed, mix_audio, volume, replace_audio, normalize, text, animate"],
    )
