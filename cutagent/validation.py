"""Dry-run validation for EDLs — checks inputs, timestamps, and references."""

from __future__ import annotations

from pathlib import Path

from cutagent.engine import parse_edl, _is_reference
from cutagent.errors import CutAgentError
from cutagent.models import (
    EDL,
    TrimOp,
    SplitOp,
    ConcatOp,
    ReorderOp,
    ExtractOp,
    FadeOp,
    SpeedOp,
    parse_time,
)
from cutagent.probe import probe


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

class ValidationResult:
    """Collects errors and warnings from a dry-run validation."""

    def __init__(self) -> None:
        self.errors: list[dict] = []
        self.warnings: list[dict] = []

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, code: str, message: str, **context) -> None:
        self.errors.append({"code": code, "message": message, **context})

    def add_warning(self, code: str, message: str, **context) -> None:
        self.warnings.append({"code": code, "message": message, **context})

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_edl(raw: str | dict) -> ValidationResult:
    """Validate an EDL without executing it.

    Checks:
        - EDL JSON is parseable
        - All input files exist
        - Timestamps are valid and within source duration
        - $N references point to existing earlier operations
        - Output directory exists
        - Reorder indices are in range

    Args:
        raw: JSON string or dict representing the EDL.

    Returns:
        ValidationResult with errors and warnings.
    """
    result = ValidationResult()

    # Parse EDL
    try:
        edl = parse_edl(raw)
    except CutAgentError as exc:
        result.add_error(exc.code, exc.message, **exc.context)
        return result

    # Check inputs exist
    file_durations: dict[str, float] = {}
    for input_path in edl.inputs:
        if not Path(input_path).exists():
            result.add_error("INPUT_NOT_FOUND", f"Input file not found: {input_path}", path=input_path)
        else:
            try:
                info = probe(input_path)
                file_durations[input_path] = info.duration
            except CutAgentError as exc:
                result.add_error(exc.code, exc.message)

    # Track which operation indices have been produced
    produced: set[int] = set()

    for idx, op in enumerate(edl.operations):
        _validate_operation(op, idx, produced, file_durations, result)
        produced.add(idx)

    # Check output directory
    output_dir = Path(edl.output.path).parent
    if str(output_dir) != "." and not output_dir.exists():
        result.add_warning(
            "OUTPUT_DIR_NOT_FOUND",
            f"Output directory does not exist: {output_dir} (will be created)",
            path=str(output_dir),
        )

    return result


def _validate_operation(
    op,
    idx: int,
    produced: set[int],
    file_durations: dict[str, float],
    result: ValidationResult,
) -> None:
    """Validate a single operation."""
    if isinstance(op, TrimOp):
        _validate_trim(op, idx, produced, file_durations, result)
    elif isinstance(op, SplitOp):
        _validate_split(op, idx, produced, file_durations, result)
    elif isinstance(op, ConcatOp):
        _validate_concat(op, idx, produced, result)
    elif isinstance(op, ReorderOp):
        _validate_reorder(op, idx, produced, result)
    elif isinstance(op, ExtractOp):
        _validate_extract(op, idx, produced, result)
    elif isinstance(op, FadeOp):
        _validate_fade(op, idx, produced, file_durations, result)
    elif isinstance(op, SpeedOp):
        _validate_speed(op, idx, produced, result)


def _validate_source(source: str, produced: set[int], result: ValidationResult) -> None:
    """Check that a source is either a valid file or a valid $N reference."""
    if _is_reference(source):
        ref_idx = int(source[1:])
        if ref_idx not in produced:
            result.add_error(
                "INVALID_REFERENCE",
                f"Reference {source} points to operation {ref_idx} which hasn't been produced yet",
                reference=source,
            )
    elif not Path(source).exists():
        result.add_error("INPUT_NOT_FOUND", f"Source file not found: {source}", path=source)


def _validate_trim(op: TrimOp, idx: int, produced: set[int], durations: dict, result: ValidationResult) -> None:
    _validate_source(op.source, produced, result)

    try:
        start_sec = parse_time(op.start)
    except ValueError:
        result.add_error("INVALID_TIME_FORMAT", f"Op {idx}: invalid start time: {op.start}")
        return
    try:
        end_sec = parse_time(op.end)
    except ValueError:
        result.add_error("INVALID_TIME_FORMAT", f"Op {idx}: invalid end time: {op.end}")
        return

    if start_sec >= end_sec:
        result.add_error("TRIM_START_AFTER_END", f"Op {idx}: start ({op.start}) >= end ({op.end})")

    dur = durations.get(op.source)
    if dur is not None and end_sec > dur:
        result.add_error(
            "TRIM_BEYOND_DURATION",
            f"Op {idx}: end {op.end} ({end_sec:.3f}s) > duration ({dur:.3f}s)",
        )


def _validate_split(op: SplitOp, idx: int, produced: set[int], durations: dict, result: ValidationResult) -> None:
    _validate_source(op.source, produced, result)
    dur = durations.get(op.source)
    for pt in op.points:
        try:
            pt_sec = parse_time(pt)
        except ValueError:
            result.add_error("INVALID_TIME_FORMAT", f"Op {idx}: invalid split point: {pt}")
            continue
        if dur is not None and pt_sec > dur:
            result.add_error(
                "SPLIT_POINT_BEYOND_DURATION",
                f"Op {idx}: split point {pt} ({pt_sec:.3f}s) > duration ({dur:.3f}s)",
            )


def _validate_concat(op: ConcatOp, idx: int, produced: set[int], result: ValidationResult) -> None:
    for seg in op.segments:
        _validate_source(seg, produced, result)
    if op.transition is not None and op.transition != "crossfade":
        result.add_error(
            "INVALID_TRANSITION",
            f"Op {idx}: transition must be 'crossfade' when set, got {op.transition!r}",
        )
    if op.transition_duration is not None and op.transition_duration <= 0:
        result.add_error(
            "INVALID_TRANSITION_DURATION",
            f"Op {idx}: transition_duration must be > 0, got {op.transition_duration}",
        )


def _validate_reorder(op: ReorderOp, idx: int, produced: set[int], result: ValidationResult) -> None:
    for seg in op.segments:
        _validate_source(seg, produced, result)
    for i in op.order:
        if i < 0 or i >= len(op.segments):
            result.add_error(
                "REORDER_INDEX_OUT_OF_RANGE",
                f"Op {idx}: reorder index {i} out of range (0–{len(op.segments) - 1})",
            )


def _validate_extract(op: ExtractOp, idx: int, produced: set[int], result: ValidationResult) -> None:
    _validate_source(op.source, produced, result)
    if op.stream not in ("audio", "video"):
        result.add_error(
            "INVALID_STREAM_TYPE",
            f"Op {idx}: stream must be 'audio' or 'video', got {op.stream!r}",
        )


def _validate_fade(op: FadeOp, idx: int, produced: set[int], durations: dict, result: ValidationResult) -> None:
    _validate_source(op.source, produced, result)
    if op.fade_in < 0 or op.fade_out < 0:
        result.add_error(
            "INVALID_FADE_DURATION",
            f"Op {idx}: fade_in and fade_out must be >= 0",
        )
    if op.fade_in == 0 and op.fade_out == 0:
        result.add_error(
            "INVALID_FADE_DURATION",
            f"Op {idx}: at least one of fade_in or fade_out must be > 0",
        )

    dur = durations.get(op.source)
    if dur is not None and (op.fade_in + op.fade_out) > dur:
        result.add_error(
            "INVALID_FADE_DURATION",
            (
                f"Op {idx}: fade durations ({op.fade_in + op.fade_out:.3f}s) exceed "
                f"duration ({dur:.3f}s)"
            ),
        )


def _validate_speed(op: SpeedOp, idx: int, produced: set[int], result: ValidationResult) -> None:
    _validate_source(op.source, produced, result)
    if op.factor <= 0:
        result.add_error(
            "INVALID_SPEED_FACTOR",
            f"Op {idx}: speed factor must be > 0, got {op.factor}",
        )
    elif op.factor < 0.25 or op.factor > 100.0:
        result.add_error(
            "INVALID_SPEED_FACTOR",
            f"Op {idx}: speed factor must be between 0.25 and 100.0, got {op.factor}",
        )
