"""Dry-run validation for EDLs — checks inputs, timestamps, and references."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from cutagent.engine import parse_edl, _is_reference, _is_input_reference, _INPUT_REF_PREFIX
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
    MixAudioOp,
    VolumeOp,
    ReplaceAudioOp,
    NormalizeOp,
    parse_time,
    format_time,
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
        self.estimated_duration: Optional[float] = None

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, code: str, message: str, **context) -> None:
        self.errors.append({"code": code, "message": message, **context})

    def add_warning(self, code: str, message: str, **context) -> None:
        self.warnings.append({"code": code, "message": message, **context})

    def to_dict(self) -> dict:
        d = {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }
        if self.estimated_duration is not None:
            d["estimated_duration"] = round(self.estimated_duration, 3)
            d["estimated_duration_formatted"] = format_time(self.estimated_duration)
        return d


# ---------------------------------------------------------------------------
# Duration resolution helper
# ---------------------------------------------------------------------------

def _resolve_source_duration(
    source: str,
    file_durations: dict[str, float],
    op_durations: dict[int, Optional[float]],
    inputs: list[str],
) -> Optional[float]:
    """Look up the estimated duration of a source — input ref, op ref, or file path."""
    if _is_input_reference(source):
        idx = int(source[len(_INPUT_REF_PREFIX):])
        if 0 <= idx < len(inputs):
            return file_durations.get(inputs[idx])
        return None
    if _is_reference(source):
        ref_idx = int(source[1:])
        return op_durations.get(ref_idx)
    return file_durations.get(source)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_edl(raw: str | dict) -> ValidationResult:
    """Validate an EDL without executing it.

    Checks:
        - EDL JSON is parseable
        - All input files exist
        - Timestamps are valid and within source duration
        - $input.N and $N references point to valid targets
        - Output directory exists
        - Reorder indices are in range

    Also computes an estimated output duration when possible.

    Args:
        raw: JSON string or dict representing the EDL.

    Returns:
        ValidationResult with errors, warnings, and estimated_duration.
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

    # Track which operation indices have been produced and their estimated durations
    produced: set[int] = set()
    op_durations: dict[int, Optional[float]] = {}
    input_count = len(edl.inputs)

    for idx, op in enumerate(edl.operations):
        est = _validate_operation(
            op, idx, produced, file_durations, result, input_count,
            op_durations, edl.inputs,
        )
        op_durations[idx] = est
        produced.add(idx)

    # The estimated output duration is the last operation's estimated duration
    if edl.operations:
        last_est = op_durations.get(len(edl.operations) - 1)
        result.estimated_duration = last_est

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
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    """Validate a single operation. Returns estimated duration or None."""
    _op_dur = op_durations or {}
    _inputs = inputs or []

    if isinstance(op, TrimOp):
        return _validate_trim(op, idx, produced, file_durations, result, input_count)
    elif isinstance(op, SplitOp):
        return _validate_split(op, idx, produced, file_durations, result, input_count)
    elif isinstance(op, ConcatOp):
        return _validate_concat(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    elif isinstance(op, ReorderOp):
        return _validate_reorder(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    elif isinstance(op, ExtractOp):
        return _validate_extract(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    elif isinstance(op, FadeOp):
        return _validate_fade(op, idx, produced, file_durations, result, input_count, _op_dur, _inputs)
    elif isinstance(op, SpeedOp):
        return _validate_speed(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    elif isinstance(op, MixAudioOp):
        return _validate_mix_audio(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    elif isinstance(op, VolumeOp):
        return _validate_volume(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    elif isinstance(op, ReplaceAudioOp):
        return _validate_replace_audio(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    elif isinstance(op, NormalizeOp):
        return _validate_normalize(op, idx, produced, result, input_count, _op_dur, file_durations, _inputs)
    else:
        result.add_error(
            "UNKNOWN_OPERATION",
            f"Op {idx}: unknown operation type: {type(op).__name__}",
        )
        return None


def _validate_source(
    source: str, produced: set[int], result: ValidationResult, input_count: int = 0,
) -> None:
    """Check that a source is a valid $input.N, $N reference, or file path."""
    if _is_input_reference(source):
        idx = int(source[len("$input."):])
        if idx < 0 or idx >= input_count:
            result.add_error(
                "INVALID_REFERENCE",
                f"Reference {source} points to input {idx}, but only {input_count} inputs exist",
                reference=source,
            )
    elif _is_reference(source):
        ref_idx = int(source[1:])
        if ref_idx not in produced:
            result.add_error(
                "INVALID_REFERENCE",
                f"Reference {source} points to operation {ref_idx} which hasn't been produced yet",
                reference=source,
            )
    elif not Path(source).exists():
        result.add_error("INPUT_NOT_FOUND", f"Source file not found: {source}", path=source)


def _validate_trim(
    op: TrimOp, idx: int, produced: set[int], durations: dict,
    result: ValidationResult, input_count: int = 0,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)

    try:
        start_sec = parse_time(op.start)
    except ValueError:
        result.add_error("INVALID_TIME_FORMAT", f"Op {idx}: invalid start time: {op.start}")
        return None
    try:
        end_sec = parse_time(op.end)
    except ValueError:
        result.add_error("INVALID_TIME_FORMAT", f"Op {idx}: invalid end time: {op.end}")
        return None

    if start_sec >= end_sec:
        result.add_error("TRIM_START_AFTER_END", f"Op {idx}: start ({op.start}) >= end ({op.end})")

    dur = durations.get(op.source)
    if dur is not None and end_sec > dur:
        result.add_error(
            "TRIM_BEYOND_DURATION",
            f"Op {idx}: end {op.end} ({end_sec:.3f}s) > duration ({dur:.3f}s)",
        )

    return end_sec - start_sec if end_sec > start_sec else None


def _validate_split(
    op: SplitOp, idx: int, produced: set[int], durations: dict,
    result: ValidationResult, input_count: int = 0,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
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
    # Split produces the first segment — estimate as start to first point
    if op.points:
        try:
            first_pt = parse_time(op.points[0])
            return first_pt
        except ValueError:
            pass
    return None


def _validate_concat(
    op: ConcatOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    for seg in op.segments:
        _validate_source(seg, produced, result, input_count)
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

    # Estimate total duration = sum of segments minus crossfade overlaps
    _op_dur = op_durations or {}
    _file_dur = file_durations or {}
    _inputs = inputs or []
    total = 0.0
    all_known = True
    for seg in op.segments:
        seg_dur = _resolve_source_duration(seg, _file_dur, _op_dur, _inputs)
        if seg_dur is not None:
            total += seg_dur
        else:
            all_known = False
    if all_known and op.transition == "crossfade" and op.transition_duration:
        overlaps = max(0, len(op.segments) - 1) * op.transition_duration
        total = max(0.0, total - overlaps)
    return total if all_known else None


def _validate_reorder(
    op: ReorderOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    for seg in op.segments:
        _validate_source(seg, produced, result, input_count)
    for i in op.order:
        if i < 0 or i >= len(op.segments):
            result.add_error(
                "REORDER_INDEX_OUT_OF_RANGE",
                f"Op {idx}: reorder index {i} out of range (0–{len(op.segments) - 1})",
            )

    # Estimate: sum of reordered segment durations
    _op_dur = op_durations or {}
    _file_dur = file_durations or {}
    _inputs = inputs or []
    total = 0.0
    all_known = True
    for i in op.order:
        if 0 <= i < len(op.segments):
            seg_dur = _resolve_source_duration(op.segments[i], _file_dur, _op_dur, _inputs)
            if seg_dur is not None:
                total += seg_dur
            else:
                all_known = False
    return total if all_known else None


def _validate_extract(
    op: ExtractOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
    if op.stream not in ("audio", "video"):
        result.add_error(
            "INVALID_STREAM_TYPE",
            f"Op {idx}: stream must be 'audio' or 'video', got {op.stream!r}",
        )
    # Extract preserves duration
    return _resolve_source_duration(
        op.source, file_durations or {}, op_durations or {}, inputs or [],
    )


def _validate_fade(
    op: FadeOp, idx: int, produced: set[int], durations: dict,
    result: ValidationResult, input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
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

    source_dur = _resolve_source_duration(
        op.source, durations, op_durations or {}, inputs or [],
    )
    if source_dur is not None and (op.fade_in + op.fade_out) > source_dur:
        result.add_error(
            "INVALID_FADE_DURATION",
            (
                f"Op {idx}: fade durations ({op.fade_in + op.fade_out:.3f}s) exceed "
                f"duration ({source_dur:.3f}s)"
            ),
        )
    # Fade preserves duration
    return source_dur


def _validate_speed(
    op: SpeedOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
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

    source_dur = _resolve_source_duration(
        op.source, file_durations or {}, op_durations or {}, inputs or [],
    )
    if source_dur is not None and op.factor > 0:
        return source_dur / op.factor
    return None


def _validate_mix_audio(
    op: MixAudioOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
    _validate_source(op.audio, produced, result, input_count)
    if op.mix_level < 0.0 or op.mix_level > 1.0:
        result.add_error(
            "INVALID_MIX_LEVEL",
            f"Op {idx}: mix_level must be between 0.0 and 1.0, got {op.mix_level}",
        )
    return _resolve_source_duration(
        op.source, file_durations or {}, op_durations or {}, inputs or [],
    )


def _validate_volume(
    op: VolumeOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
    if op.gain_db < -60.0 or op.gain_db > 60.0:
        result.add_error(
            "INVALID_GAIN_VALUE",
            f"Op {idx}: gain_db must be between -60.0 and 60.0, got {op.gain_db}",
        )
    return _resolve_source_duration(
        op.source, file_durations or {}, op_durations or {}, inputs or [],
    )


def _validate_replace_audio(
    op: ReplaceAudioOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
    _validate_source(op.audio, produced, result, input_count)
    return _resolve_source_duration(
        op.source, file_durations or {}, op_durations or {}, inputs or [],
    )


def _validate_normalize(
    op: NormalizeOp, idx: int, produced: set[int], result: ValidationResult,
    input_count: int = 0,
    op_durations: dict[int, Optional[float]] | None = None,
    file_durations: dict[str, float] | None = None,
    inputs: list[str] | None = None,
) -> Optional[float]:
    _validate_source(op.source, produced, result, input_count)
    if op.target_lufs < -70.0 or op.target_lufs > -5.0:
        result.add_error(
            "INVALID_NORMALIZE_TARGET",
            f"Op {idx}: target_lufs must be between -70.0 and -5.0, got {op.target_lufs}",
        )
    if op.true_peak_dbtp < -10.0 or op.true_peak_dbtp > 0.0:
        result.add_error(
            "INVALID_NORMALIZE_TARGET",
            f"Op {idx}: true_peak_dbtp must be between -10.0 and 0.0, got {op.true_peak_dbtp}",
        )
    return _resolve_source_duration(
        op.source, file_durations or {}, op_durations or {}, inputs or [],
    )
