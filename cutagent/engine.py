"""EDL parser, reference resolver, and execution engine."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from cutagent.errors import (
    CutAgentError,
    INVALID_EDL,
    INVALID_REFERENCE,
    MISSING_FIELD,
    recovery_hints,
)
from cutagent.models import (
    EDL,
    TrimOp,
    SplitOp,
    ConcatOp,
    ReorderOp,
    ExtractOp,
    FadeOp,
    SpeedOp,
    MixAudioOp,
    VolumeOp,
    ReplaceAudioOp,
    NormalizeOp,
    TextOp,
    AnimateOp,
    OperationResult,
    OutputSpec,
)
from cutagent.operations import trim, split, concat, reorder, extract_stream, fade, speed
from cutagent.audio_ops import mix_audio, adjust_volume, replace_audio, normalize_audio
from cutagent.text_ops import add_text
from cutagent.animation_ops import animate


# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------

_REF_PREFIX = "$"
_INPUT_REF_PREFIX = "$input."


def _is_reference(value: str) -> bool:
    """Check if a string is an operation reference like '$0', '$1'."""
    return value.startswith(_REF_PREFIX) and value[1:].isdigit()


def _is_input_reference(value: str) -> bool:
    """Check if a string is an input reference like '$input.0', '$input.1'."""
    return value.startswith(_INPUT_REF_PREFIX) and value[len(_INPUT_REF_PREFIX):].isdigit()


def _resolve_ref(value: str, results: dict[int, str]) -> str:
    """Resolve a $N reference to the temp file path of that operation's output."""
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


def _resolve_source(value: str, results: dict[int, str], inputs: list[str] | None = None) -> str:
    """Resolve a source field — $input.N, $N reference, or file path."""
    if inputs is not None and _is_input_reference(value):
        return _resolve_input_ref(value, inputs)
    if _is_reference(value):
        return _resolve_ref(value, results)
    return value


def _resolve_segments(
    segments: list[str], results: dict[int, str], inputs: list[str] | None = None,
) -> list[str]:
    """Resolve a list of segments, replacing any $input.N or $N references."""
    return [_resolve_source(s, results, inputs) for s in segments]


# ---------------------------------------------------------------------------
# EDL parsing
# ---------------------------------------------------------------------------

def parse_edl(raw: str | dict) -> EDL:
    """Parse a JSON string or dict into a validated EDL object.

    Args:
        raw: JSON string or already-parsed dict.

    Returns:
        Validated EDL dataclass.

    Raises:
        CutAgentError: If the EDL is malformed.
    """
    if isinstance(raw, str):
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
    raw: str | dict,
    progress_callback: callable | None = None,
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
    codec = output_spec.codec

    total_ops = len(edl.operations)

    # Track temp files for cleanup and reference resolution
    temp_dir = tempfile.mkdtemp(prefix="cutagent_")
    results: dict[int, str] = {}  # op_index -> output file path
    all_warnings: list[str] = []

    try:
        for idx, op in enumerate(edl.operations):
            op_name = getattr(op, "op", type(op).__name__)
            if progress_callback:
                progress_callback(idx + 1, total_ops, op_name, "running")

            result = _execute_operation(op, idx, results, temp_dir, codec, edl.inputs)
            results[idx] = result.output_path
            all_warnings.extend(result.warnings)

            if progress_callback:
                progress_callback(idx + 1, total_ops, op_name, "done")

        # Copy the last operation's output to the final destination
        if results:
            last_idx = len(edl.operations) - 1
            final_temp = results[last_idx]
            output_path = output_spec.path

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
            output_path=output_spec.path,
            warnings=all_warnings,
        )

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def _execute_operation(
    op,
    idx: int,
    results: dict[int, str],
    temp_dir: str,
    codec: str,
    inputs: list[str] | None = None,
) -> OperationResult:
    """Execute a single operation and return its result."""
    ext = ".mp4"  # default output extension

    if isinstance(op, TrimOp):
        source = _resolve_source(op.source, results, inputs)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return trim(source, op.start, op.end, out, codec=codec)

    if isinstance(op, SplitOp):
        source = _resolve_source(op.source, results, inputs)
        ext = Path(source).suffix or ext
        prefix = str(Path(temp_dir) / f"op_{idx:03d}")
        split_results = split(source, op.points, prefix, codec=codec)
        # For splits, we register the first segment as the "output"
        # and store all paths — the engine caller should reference specific segments
        if split_results:
            return split_results[0]
        return OperationResult(success=True, output_path=prefix)

    if isinstance(op, ConcatOp):
        segments = _resolve_segments(op.segments, results, inputs)
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
        segments = _resolve_segments(op.segments, results, inputs)
        ext = Path(segments[0]).suffix if segments else ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return reorder(segments, op.order, out, codec=codec)

    if isinstance(op, ExtractOp):
        source = _resolve_source(op.source, results, inputs)
        ext = ".aac" if op.stream == "audio" else Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return extract_stream(source, op.stream, out)

    if isinstance(op, FadeOp):
        source = _resolve_source(op.source, results, inputs)
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
        source = _resolve_source(op.source, results, inputs)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return speed(
            source,
            out,
            factor=op.factor,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, MixAudioOp):
        source = _resolve_source(op.source, results, inputs)
        audio = _resolve_source(op.audio, results, inputs)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return mix_audio(
            source, audio, out,
            mix_level=op.mix_level,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, VolumeOp):
        source = _resolve_source(op.source, results, inputs)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return adjust_volume(
            source, out,
            gain_db=op.gain_db,
            codec=codec,
        )

    if isinstance(op, ReplaceAudioOp):
        source = _resolve_source(op.source, results, inputs)
        audio = _resolve_source(op.audio, results, inputs)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return replace_audio(source, audio, out, codec=codec)

    if isinstance(op, NormalizeOp):
        source = _resolve_source(op.source, results, inputs)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return normalize_audio(
            source, out,
            target_lufs=op.target_lufs,
            true_peak_dbtp=op.true_peak_dbtp,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, TextOp):
        source = _resolve_source(op.source, results, inputs)
        ext = Path(source).suffix or ext
        out = str(Path(temp_dir) / f"op_{idx:03d}{ext}")
        return add_text(
            source, op.entries, out,
            codec=codec if codec != "copy" else "libx264",
        )

    if isinstance(op, AnimateOp):
        source = _resolve_source(op.source, results, inputs)
        # Resolve image paths inside layers
        for layer in op.layers:
            if layer.type == "image" and layer.path:
                layer.path = _resolve_source(layer.path, results, inputs)
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
