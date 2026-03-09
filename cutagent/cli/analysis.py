from typing import Optional

import typer

from cutagent.cli.utils import json_error, json_out, json_out_shaped
from cutagent.errors import EXIT_VALIDATION, CutAgentError

app = typer.Typer(help="Analysis and probing commands")


def _normalize_response_format(response_format: str) -> str:
    value = response_format.lower().strip()
    if value not in {"json", "ndjson"}:
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message="--response-format must be 'json' or 'ndjson'",
            recovery=["Use --response-format json", "Use --response-format ndjson"],
        )
    return value


def _normalize_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if limit < 1:
        raise CutAgentError(
            code="INVALID_ARGUMENT",
            message="--limit must be >= 1",
            recovery=["Use a positive value like --limit 50"],
        )
    return limit

@app.command("probe")
def cmd_probe(
    file: str,
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """Probe a media file for metadata."""
    from cutagent.probe import probe
    try:
        result = probe(file)
        return json_out_shaped(
            result.to_dict(),
            fields=fields,
            response_format=_normalize_response_format(response_format),
        )
    except CutAgentError as exc:
        return json_error(exc)

@app.command("keyframes")
def cmd_keyframes(
    file: str,
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of returned keyframes"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """List keyframe timestamps."""
    from cutagent.probe import keyframes
    try:
        cap = _normalize_limit(limit)
        all_keyframes = keyframes(file)
        selected = all_keyframes[:cap] if cap is not None else all_keyframes

        avg_interval = None
        if len(all_keyframes) > 1:
            intervals = [
                all_keyframes[i + 1] - all_keyframes[i]
                for i in range(len(all_keyframes) - 1)
            ]
            avg_interval = round(sum(intervals) / len(intervals), 3)

        return json_out_shaped(
            {
                "path": file,
                "keyframes": selected,
                "count": len(selected),
                "total_count": len(all_keyframes),
                "truncated": len(selected) < len(all_keyframes),
                "average_interval_seconds": avg_interval,
            },
            fields=fields,
            response_format=_normalize_response_format(response_format),
            ndjson_key="keyframes",
        )
    except CutAgentError as exc:
        return json_error(exc)

@app.command("scenes")
def cmd_scenes(
    file: str,
    threshold: float = typer.Option(0.3, help="Scene detection threshold (0.0–1.0)"),
    output_dir: Optional[str] = typer.Option(None, help="Optional output directory for scene preview frames"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """Detect scene boundaries."""
    from cutagent.probe import detect_scenes
    try:
        scenes = detect_scenes(
            file,
            threshold=threshold,
            frame_output_dir=output_dir,
        )
        return json_out_shaped({
            "path": file,
            "scenes": [scene.to_dict() for scene in scenes],
            "count": len(scenes),
            "threshold": threshold,
            "output_dir": output_dir,
        }, fields=fields, response_format=_normalize_response_format(response_format), ndjson_key="scenes")
    except CutAgentError as exc:
        return json_error(exc)

def _compute_timestamps(file: str, at: str | None, count: int | None, interval: float | None) -> list[float]:
    """Compute frame timestamps from --at, --count, or --interval."""
    from cutagent.models import parse_time
    from cutagent.probe import probe

    if sum(1 for x in (at, count, interval) if x is not None) > 1:
        raise ValueError("Cannot combine --at, --count, and --interval")

    if at:
        return [parse_time(v.strip()) for v in at.split(",") if v.strip()]

    # --count or --interval require probing duration
    info = probe(file)
    duration = info.duration

    if count is not None:
        n = count
        if n < 1:
            raise ValueError("--count must be >= 1")
        if n == 1:
            return [duration / 2.0]
        step = duration / (n + 1)
        return [step * (i + 1) for i in range(n)]

    if interval is not None:
        iv = interval
        if iv <= 0:
            raise ValueError("--interval must be > 0")
        timestamps = []
        t = iv
        while t < duration:
            timestamps.append(t)
            t += iv
        return timestamps

    raise ValueError("Provide --at, --count, or --interval")

@app.command("frames")
def cmd_frames(
    file: str,
    output_dir: str = typer.Option(..., "--output-dir", help="Directory for extracted frames"),
    at: Optional[str] = typer.Option(None, help="Comma-separated timestamps"),
    count: Optional[int] = typer.Option(None, help="Extract N evenly-spaced frames"),
    interval: Optional[float] = typer.Option(None, help="Extract a frame every N seconds"),
    format: str = typer.Option("jpg", help="Image format (jpg, jpeg, png)"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """Extract still frames at specific timestamps."""
    from cutagent.probe import extract_frames
    try:
        timestamps = _compute_timestamps(file, at, count, interval)
        frames = extract_frames(
            file,
            timestamps=timestamps,
            output_dir=output_dir,
            image_format=format,
        )
        return json_out_shaped({
            "path": file,
            "frames": [frame.to_dict() for frame in frames],
            "count": len(frames),
        }, fields=fields, response_format=_normalize_response_format(response_format), ndjson_key="frames")
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Provide --at timestamps, --count N, or --interval seconds"],
        }, EXIT_VALIDATION)

@app.command("thumbnail")
def cmd_thumbnail(
    file: str,
    at: str = typer.Option(..., "--time", "--at", help="Thumbnail timestamp"),
    output: str = typer.Option(..., "-o", "--output", help="Output image path"),
) -> int:
    """Extract a single thumbnail frame."""
    from cutagent.models import parse_time
    from cutagent.probe import thumbnail
    try:
        frame = thumbnail(file, timestamp=parse_time(at), output=output)
        return json_out({"path": file, "thumbnail": frame.to_dict()})
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use a valid timestamp in --at"],
        }, EXIT_VALIDATION)

@app.command("silence")
def cmd_silence(
    file: str,
    threshold: float = typer.Option(-30.0, help="Silence threshold in dB"),
    min_duration: float = typer.Option(0.5, help="Minimum silence duration in seconds"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of returned silence intervals"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """Detect silence intervals."""
    from cutagent.probe import detect_silence
    try:
        cap = _normalize_limit(limit)
        intervals = detect_silence(
            file,
            threshold=threshold,
            min_duration=min_duration,
        )
        silences = [interval.to_dict() for interval in intervals]
        selected = silences[:cap] if cap is not None else silences
        return json_out_shaped(
            {
                "path": file,
                "silences": selected,
                "count": len(selected),
                "total_count": len(silences),
                "truncated": len(selected) < len(silences),
                "threshold_db": threshold,
                "min_duration": min_duration,
            },
            fields=fields,
            response_format=_normalize_response_format(response_format),
            ndjson_key="silences",
        )
    except CutAgentError as exc:
        return json_error(exc)

@app.command("audio-levels")
def cmd_audio_levels(
    file: str,
    interval: float = typer.Option(1.0, help="Aggregation interval in seconds"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """Compute audio levels over time."""
    from cutagent.probe import audio_levels
    try:
        levels = audio_levels(file, interval=interval)
        return json_out_shaped({
            "path": file,
            "interval": interval,
            "audio_levels": [level.to_dict() for level in levels],
            "count": len(levels),
        }, fields=fields, response_format=_normalize_response_format(response_format), ndjson_key="audio_levels")
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use --interval > 0"],
        }, EXIT_VALIDATION)

@app.command("summarize")
def cmd_summarize(
    file: str,
    frame_dir: Optional[str] = typer.Option(None, help="Optional directory to write scene frame previews"),
    scene_threshold: float = typer.Option(0.3, help="Scene detection threshold"),
    silence_threshold: float = typer.Option(-30.0, help="Silence threshold in dB"),
    min_silence_duration: float = typer.Option(0.5, help="Minimum silence duration"),
    audio_interval: float = typer.Option(1.0, help="Audio level interval in seconds"),
    include_audio_levels: bool = typer.Option(False, help="Include per-second audio levels in output (verbose)"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """Generate a unified content map."""
    from cutagent.probe import summarize
    try:
        result = summarize(
            file,
            frame_dir=frame_dir,
            scene_threshold=scene_threshold,
            silence_threshold=silence_threshold,
            min_silence_duration=min_silence_duration,
            audio_interval=audio_interval,
            include_audio_levels=include_audio_levels,
        )
        return json_out_shaped(
            {"summary": result.to_dict()},
            fields=fields,
            response_format=_normalize_response_format(response_format),
        )
    except CutAgentError as exc:
        return json_error(exc)

@app.command("beats")
def cmd_beats(
    file: str,
    min_interval: float = typer.Option(0.15, help="Minimum seconds between beats (default: 0.15)"),
    energy_threshold: float = typer.Option(1.4, help="Energy spike threshold multiplier (default: 1.4)"),
    min_strength: float = typer.Option(
        0.0,
        "--min-strength",
        help="Only include beats with at least this strength (0.0-3.0)",
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of returned beats"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Comma-separated field mask"),
    response_format: str = typer.Option("json", "--response-format", help="json or ndjson"),
) -> int:
    """Detect musical beats/onsets in audio."""
    from cutagent.probe import detect_beats
    try:
        cap = _normalize_limit(limit)
        if min_strength < 0.0 or min_strength > 3.0:
            raise CutAgentError(
                code="INVALID_ARGUMENT",
                message="--min-strength must be between 0.0 and 3.0",
                recovery=["Use a value like --min-strength 1.2"],
            )
        result = detect_beats(
            file,
            min_interval=min_interval,
            energy_threshold=energy_threshold,
        )
        all_beats = [b.to_dict() for b in result["beats"]]
        filtered = [beat for beat in all_beats if beat["strength"] >= min_strength]
        selected = filtered[:cap] if cap is not None else filtered
        return json_out_shaped(
            {
                "path": file,
                "beats": selected,
                "count": len(selected),
                "total_count": len(all_beats),
                "filtered_count": len(filtered),
                "truncated": len(selected) < len(filtered),
                "bpm": result["bpm"],
                "min_strength": min_strength,
            },
            fields=fields,
            response_format=_normalize_response_format(response_format),
            ndjson_key="beats",
        )
    except CutAgentError as exc:
        return json_error(exc)
