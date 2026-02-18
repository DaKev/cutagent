"""Core video operations — trim, split, concat, reorder, extract, fade."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cutagent.errors import (
    CutAgentError,
    TRIM_START_AFTER_END,
    TRIM_BEYOND_DURATION,
    SPLIT_POINT_BEYOND_DURATION,
    INVALID_STREAM_TYPE,
    REORDER_INDEX_OUT_OF_RANGE,
    recovery_hints,
)
from cutagent.ffmpeg import run_ffmpeg
from cutagent.models import OperationResult, parse_time, format_time
from cutagent.probe import probe as probe_file, keyframes as get_keyframes


# ---------------------------------------------------------------------------
# Trim
# ---------------------------------------------------------------------------

def trim(
    source: str,
    start: str,
    end: str,
    output: str,
    codec: str = "copy",
) -> OperationResult:
    """Trim a video between start and end timestamps.

    Args:
        source: Path to the source video.
        start: Start time (HH:MM:SS, MM:SS, or seconds).
        end: End time (HH:MM:SS, MM:SS, or seconds).
        output: Path for the output file.
        codec: 'copy' for lossless, or specific codec name.

    Returns:
        OperationResult with output path and warnings.
    """
    start_sec = parse_time(start)
    end_sec = parse_time(end)

    if start_sec >= end_sec:
        raise CutAgentError(
            code=TRIM_START_AFTER_END,
            message=f"Start time ({start}) is at or after end time ({end})",
            recovery=recovery_hints(TRIM_START_AFTER_END),
            context={"start": start, "end": end},
        )

    info = probe_file(source)
    warnings: list[str] = []

    _TRIM_BOUNDARY_TOLERANCE = 0.05
    if end_sec > info.duration:
        if end_sec - info.duration <= _TRIM_BOUNDARY_TOLERANCE:
            warnings.append(
                f"End time {end} ({end_sec:.3f}s) slightly exceeds duration "
                f"({info.duration:.3f}s) — clamped to duration"
            )
            end_sec = info.duration
        else:
            raise CutAgentError(
                code=TRIM_BEYOND_DURATION,
                message=f"End time {end} ({end_sec:.3f}s) exceeds duration ({info.duration:.3f}s)",
                recovery=recovery_hints(TRIM_BEYOND_DURATION, {"duration": info.duration}),
                context={"source": source, "duration": info.duration, "end": end},
            )

    # Warn about non-keyframe cut points when using copy codec
    if codec == "copy":
        kfs = get_keyframes(source)
        if kfs:
            _check_keyframe_alignment(start_sec, kfs, "start", warnings)
            _check_keyframe_alignment(end_sec, kfs, "end", warnings)

    args = ["-ss", str(start_sec), "-to", str(end_sec), "-i", source]
    if codec == "copy":
        args += ["-c", "copy"]
    else:
        args += ["-c:v", codec]
    args.append(output)

    run_ffmpeg(args)

    duration = end_sec - start_sec
    return OperationResult(
        success=True,
        output_path=output,
        duration_seconds=duration,
        warnings=warnings,
    )


def _check_keyframe_alignment(
    time_sec: float,
    keyframes_list: list[float],
    label: str,
    warnings: list[str],
    tolerance: float = 0.1,
) -> None:
    """Add a warning if a cut point doesn't align with a keyframe."""
    nearest = min(keyframes_list, key=lambda kf: abs(kf - time_sec))
    if abs(nearest - time_sec) > tolerance:
        warnings.append(
            f"Cut point {label}={format_time(time_sec)} is not on a keyframe. "
            f"Nearest keyframe: {format_time(nearest)}. "
            f"With codec=copy, the cut may be imprecise."
        )


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split(
    source: str,
    points: list[str],
    output_prefix: str,
    codec: str = "copy",
) -> list[OperationResult]:
    """Split a video at the given time points.

    Args:
        source: Path to the source video.
        points: List of split-point timestamps.
        output_prefix: Prefix for output segment files (e.g. "seg" -> "seg_000.mp4").
        codec: 'copy' for lossless, or specific codec name.

    Returns:
        List of OperationResult, one per segment.
    """
    info = probe_file(source)
    ext = Path(source).suffix

    point_secs = sorted(parse_time(p) for p in points)

    for pt in point_secs:
        if pt > info.duration:
            raise CutAgentError(
                code=SPLIT_POINT_BEYOND_DURATION,
                message=f"Split point {pt:.3f}s exceeds duration {info.duration:.3f}s",
                recovery=["Remove split points beyond the source duration"],
                context={"source": source, "duration": info.duration, "point": pt},
            )

    # Build segment boundaries: [0, p1, p2, ..., duration]
    boundaries = [0.0] + point_secs + [info.duration]
    results: list[OperationResult] = []

    for i in range(len(boundaries) - 1):
        seg_start = boundaries[i]
        seg_end = boundaries[i + 1]
        seg_path = f"{output_prefix}_{i:03d}{ext}"

        args = ["-ss", str(seg_start), "-to", str(seg_end), "-i", source]
        if codec == "copy":
            args += ["-c", "copy"]
        else:
            args += ["-c:v", codec]
        args.append(seg_path)

        run_ffmpeg(args)
        results.append(OperationResult(
            success=True,
            output_path=seg_path,
            duration_seconds=seg_end - seg_start,
        ))

    return results


# ---------------------------------------------------------------------------
# Concat
# ---------------------------------------------------------------------------

def concat(
    segments: list[str],
    output: str,
    codec: str = "copy",
    transition: str | None = None,
    transition_duration: float = 0.5,
) -> OperationResult:
    """Concatenate multiple video files in order.

    Args:
        segments: List of file paths to concatenate.
        output: Path for the output file.
        codec: 'copy' for lossless (demuxer concat), or codec name (filter concat).
        transition: Optional transition type. Supported: "crossfade".
        transition_duration: Transition duration in seconds.

    Returns:
        OperationResult with the merged output.
    """
    if transition is not None:
        if transition != "crossfade":
            raise ValueError("transition must be None or 'crossfade'")
        return _concat_crossfade(segments, output, codec, transition_duration)

    if codec == "copy":
        return _concat_demuxer(segments, output)
    return _concat_filter(segments, output, codec)


def _concat_demuxer(segments: list[str], output: str) -> OperationResult:
    """Concatenate using the concat demuxer (lossless, same-codec segments)."""
    # Write a temporary concat file list
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for seg in segments:
            # Escape single quotes in paths
            safe = str(Path(seg).resolve()).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
        concat_file = f.name

    try:
        args = ["-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output]
        run_ffmpeg(args)
    finally:
        Path(concat_file).unlink(missing_ok=True)

    return OperationResult(success=True, output_path=output)


def _concat_filter(segments: list[str], output: str, codec: str) -> OperationResult:
    """Concatenate using the filter_complex (re-encodes, handles mixed formats)."""
    args: list[str] = []
    for seg in segments:
        args += ["-i", str(seg)]

    n = len(segments)
    filter_parts = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
    filter_str = f"{filter_parts}concat=n={n}:v=1:a=1[outv][outa]"

    args += [
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", codec,
        output,
    ]
    run_ffmpeg(args)
    return OperationResult(success=True, output_path=output)


def _concat_crossfade(
    segments: list[str],
    output: str,
    codec: str,
    transition_duration: float,
) -> OperationResult:
    """Concatenate with xfade/acrossfade transitions.

    Handles video-only inputs (no audio stream) and resolution mismatches
    by auto-normalizing dimensions via scale+pad.
    """
    if len(segments) < 2:
        raise ValueError("crossfade transition requires at least two segments")
    if transition_duration <= 0:
        raise ValueError("transition_duration must be > 0")

    probes = [probe_file(seg) for seg in segments]
    durations = [p.duration for p in probes]
    for i, duration in enumerate(durations):
        if duration <= transition_duration:
            raise ValueError(
                f"Segment {i} duration ({duration:.3f}s) must be greater than "
                f"transition_duration ({transition_duration:.3f}s)"
            )

    has_audio = all(p.audio_stream is not None for p in probes)

    # Detect fps from first segment
    fps = 30
    video_stream = probes[0].video_stream
    if video_stream and video_stream.fps:
        fps = video_stream.fps

    # Detect resolution mismatches and pick a target canvas
    resolutions = [(p.width, p.height) for p in probes]
    needs_scale = len(set(resolutions)) > 1
    target_w = max(r[0] for r in resolutions if r[0] is not None) if needs_scale else None
    target_h = max(r[1] for r in resolutions if r[1] is not None) if needs_scale else None

    args: list[str] = []
    for seg in segments:
        args += ["-i", str(seg)]

    filters: list[str] = []
    for idx in range(len(segments)):
        vfilter = f"[{idx}:v]setpts=PTS-STARTPTS,fps={fps},format=yuv420p"
        if needs_scale and target_w and target_h:
            vfilter += (
                f",scale={target_w}:{target_h}:"
                f"force_original_aspect_ratio=decrease"
                f",pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2"
            )
        vfilter += f"[vsrc{idx}]"
        filters.append(vfilter)

        if has_audio:
            filters.append(f"[{idx}:a]asetpts=PTS-STARTPTS[asrc{idx}]")

    running_duration = durations[0]
    prev_v = "vsrc0"
    prev_a = "asrc0" if has_audio else None
    for idx in range(1, len(segments)):
        offset = max(0.0, running_duration - transition_duration)
        out_v = f"vxf{idx}"
        filters.append(
            f"[{prev_v}][vsrc{idx}]xfade=transition=fade:duration={transition_duration}:"
            f"offset={offset}[{out_v}]"
        )

        if has_audio:
            out_a = f"axf{idx}"
            filters.append(
                f"[{prev_a}][asrc{idx}]acrossfade=d={transition_duration}[{out_a}]"
            )
            prev_a = out_a

        running_duration += durations[idx] - transition_duration
        prev_v = out_v

    final_v = f"[{prev_v}]"

    encode_codec = codec if codec != "copy" else "libx264"
    args += ["-filter_complex", ";".join(filters), "-map", final_v]

    if has_audio:
        final_a = f"[{prev_a}]"
        args += ["-map", final_a, "-c:a", "aac"]

    args += ["-c:v", encode_codec, output]

    run_ffmpeg(args)
    return OperationResult(success=True, output_path=output)


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------

def reorder(
    segments: list[str],
    order: list[int],
    output: str,
    codec: str = "copy",
) -> OperationResult:
    """Reorder segments and concatenate them.

    Args:
        segments: List of file paths.
        order: New order as a list of 0-based indices into segments.
        output: Path for the output file.
        codec: 'copy' for lossless, or codec name.

    Returns:
        OperationResult with the reordered output.
    """
    for idx in order:
        if idx < 0 or idx >= len(segments):
            raise CutAgentError(
                code=REORDER_INDEX_OUT_OF_RANGE,
                message=f"Reorder index {idx} is out of range (0–{len(segments) - 1})",
                recovery=[f"Use indices between 0 and {len(segments) - 1}"],
                context={"segments_count": len(segments), "invalid_index": idx},
            )

    reordered = [segments[i] for i in order]
    return concat(reordered, output, codec=codec)


# ---------------------------------------------------------------------------
# Extract stream
# ---------------------------------------------------------------------------

def extract_stream(
    source: str,
    stream: str,
    output: str,
) -> OperationResult:
    """Extract a single stream (audio or video) from a media file.

    Args:
        source: Path to the source file.
        stream: 'audio' or 'video'.
        output: Path for the output file.

    Returns:
        OperationResult with the extracted stream.
    """
    if stream not in ("audio", "video"):
        raise CutAgentError(
            code=INVALID_STREAM_TYPE,
            message=f"Invalid stream type: {stream!r} — must be 'audio' or 'video'",
            recovery=["Use stream='audio' or stream='video'"],
            context={"stream": stream},
        )

    if stream == "audio":
        args = ["-i", source, "-vn", "-c:a", "copy", output]
    else:
        args = ["-i", source, "-an", "-c:v", "copy", output]

    run_ffmpeg(args)
    return OperationResult(success=True, output_path=output)


# ---------------------------------------------------------------------------
# Fade
# ---------------------------------------------------------------------------

def speed(
    source: str,
    output: str,
    factor: float = 1.0,
    codec: str = "libx264",
) -> OperationResult:
    """Change playback speed. factor=2.0 is 2x faster, 0.5 is half speed.

    Args:
        source: Path to the source video.
        output: Path for the output file.
        factor: Speed multiplier (0.25–100.0). >1 = faster, <1 = slower.
        codec: Video codec (default libx264). Cannot use 'copy'.

    Returns:
        OperationResult with output path.
    """
    if factor <= 0:
        raise ValueError("factor must be > 0")
    if factor < 0.25 or factor > 100.0:
        raise ValueError("factor must be between 0.25 and 100.0")

    info = probe_file(source)

    # Video: setpts=PTS/factor  (faster → smaller PTS → divide by >1)
    video_filter = f"setpts=PTS/{factor}"

    # Audio: atempo supports 0.5–100.0, so chain filters for <0.5
    audio_filters = _build_atempo_chain(factor)

    args = ["-i", source, "-vf", video_filter, "-af", audio_filters]
    args += ["-c:v", codec, "-c:a", "aac", output]

    run_ffmpeg(args)
    new_duration = info.duration / factor
    return OperationResult(success=True, output_path=output, duration_seconds=new_duration)


def _build_atempo_chain(factor: float) -> str:
    """Build chained atempo filters for factors outside the 0.5–2.0 range.

    FFmpeg atempo supports 0.5–100.0 natively. For factors <0.5, we chain
    multiple atempo filters (each at 0.5) to reach the target.
    """
    if factor >= 0.5:
        return f"atempo={factor}"
    # Chain multiple atempo=0.5 filters
    parts: list[str] = []
    remaining = factor
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining}")
    return ",".join(parts)


def fade(
    source: str,
    output: str,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    codec: str = "libx264",
) -> OperationResult:
    """Apply audio/video fade-in and fade-out effects to a clip."""
    if fade_in < 0 or fade_out < 0:
        raise ValueError("fade_in and fade_out must be >= 0")
    if fade_in == 0 and fade_out == 0:
        raise ValueError("at least one of fade_in or fade_out must be > 0")

    info = probe_file(source)
    if fade_in + fade_out > info.duration:
        raise ValueError(
            f"fade durations ({fade_in + fade_out:.3f}s) exceed clip duration ({info.duration:.3f}s)"
        )

    video_filters: list[str] = []
    audio_filters: list[str] = []

    if fade_in > 0:
        video_filters.append(f"fade=t=in:st=0:d={fade_in}")
        audio_filters.append(f"afade=t=in:st=0:d={fade_in}")
    if fade_out > 0:
        start_out = max(0.0, info.duration - fade_out)
        video_filters.append(f"fade=t=out:st={start_out}:d={fade_out}")
        audio_filters.append(f"afade=t=out:st={start_out}:d={fade_out}")

    args = ["-i", source]
    if video_filters:
        args += ["-vf", ",".join(video_filters)]
    if audio_filters:
        args += ["-af", ",".join(audio_filters)]
    args += ["-c:v", codec, "-c:a", "aac", output]

    run_ffmpeg(args)
    return OperationResult(success=True, output_path=output, duration_seconds=info.duration)
