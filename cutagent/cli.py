"""AI-native CLI — every command outputs JSON to stdout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cutagent.errors import CutAgentError, EXIT_SUCCESS, EXIT_VALIDATION, EXIT_EXECUTION, EXIT_SYSTEM


def _json_out(data: dict, exit_code: int = EXIT_SUCCESS) -> int:
    """Print JSON to stdout and return exit code."""
    print(json.dumps(data, indent=2))
    return exit_code


def _json_error(exc: CutAgentError, exit_code: int = EXIT_EXECUTION) -> int:
    """Print a CutAgentError as JSON and return the appropriate exit code."""
    return _json_out(exc.to_dict(), exit_code)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_capabilities(_args) -> int:
    """Output machine-readable schema of all operations."""
    caps = {
        "version": "1.0",
        "operations": {
            "trim": {
                "description": "Extract a segment between two timestamps",
                "fields": {"op": "'trim'", "source": "str", "start": "time", "end": "time"},
                "supports_copy_codec": True,
            },
            "split": {
                "description": "Split a video at one or more timestamps",
                "fields": {"op": "'split'", "source": "str", "points": "list[time]"},
                "supports_copy_codec": True,
            },
            "concat": {
                "description": "Concatenate multiple files in order",
                "fields": {
                    "op": "'concat'",
                    "segments": "list[str]",
                    "transition": "None | 'crossfade'",
                    "transition_duration": "float (>0)",
                },
                "supports_copy_codec": True,
            },
            "reorder": {
                "description": "Reorder segments by index and concatenate",
                "fields": {"op": "'reorder'", "segments": "list[str]", "order": "list[int]"},
                "supports_copy_codec": True,
            },
            "extract": {
                "description": "Extract audio or video stream",
                "fields": {"op": "'extract'", "source": "str", "stream": "'audio' | 'video'"},
                "supports_copy_codec": True,
            },
            "fade": {
                "description": "Apply fade-in/fade-out to audio and video",
                "fields": {
                    "op": "'fade'",
                    "source": "str",
                    "fade_in": "float (seconds)",
                    "fade_out": "float (seconds)",
                },
                "supports_copy_codec": False,
            },
            "speed": {
                "description": "Change playback speed (slow-motion or speed-up)",
                "fields": {
                    "op": "'speed'",
                    "source": "str",
                    "factor": "float (0.25–100.0; >1 = faster, <1 = slower)",
                },
                "supports_copy_codec": False,
            },
            "mix_audio": {
                "description": "Overlay background music or audio onto a video's existing audio",
                "fields": {
                    "op": "'mix_audio'",
                    "source": "str (video with original audio)",
                    "audio": "str (audio file to mix in)",
                    "mix_level": "float (0.0–1.0, default 0.3)",
                },
                "supports_copy_codec": False,
            },
            "volume": {
                "description": "Adjust audio volume by a dB gain value",
                "fields": {
                    "op": "'volume'",
                    "source": "str",
                    "gain_db": "float (-60.0 to 60.0; positive = louder)",
                },
                "supports_copy_codec": True,
            },
            "replace_audio": {
                "description": "Replace a video's audio track with a different audio file",
                "fields": {
                    "op": "'replace_audio'",
                    "source": "str (video — keeps video stream)",
                    "audio": "str (replacement audio file)",
                },
                "supports_copy_codec": True,
            },
            "normalize": {
                "description": "Normalize audio loudness using EBU R128 (loudnorm)",
                "fields": {
                    "op": "'normalize'",
                    "source": "str",
                    "target_lufs": "float (default -16.0, range -70 to -5)",
                    "true_peak_dbtp": "float (default -1.5, range -10 to 0)",
                },
                "supports_copy_codec": False,
            },
        },
        "operation_example": {
            "_note": "All fields are top-level in the operation object — there is NO 'params' wrapper",
            "example": {"op": "trim", "source": "$input.0", "start": "00:00:04", "end": "00:00:12"},
        },
        "time_formats": ["HH:MM:SS", "HH:MM:SS.mmm", "MM:SS", "seconds"],
        "edl_format": {
            "version": "1.0",
            "inputs": "list[str] — source file paths",
            "operations": "list[op] — sequential operations",
            "output": {"path": "str", "codec": "'copy' | codec_name"},
            "references": {
                "$input.N": "Reference input file by index (e.g. $input.0 for the first input)",
                "$N": "Reference output of operation N (e.g. $0 for first operation's result)",
            },
            "edl_input_methods": [
                "File path: cutagent execute my_edit.json",
                "Stdin: echo '{...}' | cutagent execute -",
                "Inline: cutagent execute --edl-json '{...}'",
            ],
        },
        "probe_commands": [
            "probe",
            "keyframes",
            "scenes",
            "frames",
            "thumbnail",
            "silence",
            "audio-levels",
            "beats",
            "summarize",
        ],
        "exit_codes": {"0": "success", "1": "validation_error", "2": "execution_error", "3": "system_error"},
        "agent_workflow": [
            "1. Run 'summarize' with --frame-dir to get content map and scene preview frames",
            "2. Review scene frames to understand visual content of each scene",
            "3. Run 'beats' to detect musical beats for rhythm-aligned cuts",
            "4. Use 'suggested_cut_points' and beat timestamps for clean transitions",
            "5. Trim clips at scene boundaries or suggested cut points",
            "6. Use 'normalize' to even out loudness across clips before concatenation",
            "7. Use 'mix_audio' to layer background music at a subtle level (mix_level 0.1–0.2)",
            "8. Use 'crossfade' transition in concat for smooth audio between clips",
            "9. Apply 'fade' (fade_in/fade_out) for polished opening and closing",
            "10. Execute via EDL for multi-step edits with $N references",
        ],
        "progress_output": {
            "description": "During 'execute', progress is emitted as JSONL on stderr",
            "format": {"progress": {"step": "int", "total": "int", "op": "str", "status": "'running' | 'done'"}},
            "suppress": "Use --quiet / -q to suppress progress output",
        },
        "validate_output": {
            "description": "Validation includes estimated output duration when computable",
            "fields": {
                "estimated_duration": "float (seconds) or absent if unknown",
                "estimated_duration_formatted": "HH:MM:SS.mmm or absent if unknown",
            },
        },
        "tips": [
            "crossfade and fade require re-encoding (codec must not be 'copy')",
            "Use 'libx264' codec when transitions or fades are needed",
            "Scene frames at 10/50/90% offsets give a filmstrip of each scene",
            "Operations needing re-encode: fade, crossfade concat, speed, mix_audio, normalize",
            "Use 'speed' with factor <1 for slow-motion, >1 for fast-forward",
            "Use $input.0 in operations to reference the first input file",
            "Use --edl-json to pass EDL inline without writing a temp file",
            "Use 'normalize' (target_lufs=-16) before concat to ensure consistent loudness",
            "Use 'mix_audio' with mix_level 0.1–0.2 for subtle background music",
            "Use 'beats' to detect rhythm — cut on beats for music-driven edits",
            "Use 'volume' to boost quiet clips or reduce loud ones (gain_db in dB)",
        ],
    }
    return _json_out(caps)


def cmd_probe(args) -> int:
    """Probe a media file for metadata."""
    from cutagent.probe import probe
    try:
        result = probe(args.file)
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc, EXIT_VALIDATION)


def cmd_keyframes(args) -> int:
    """List keyframe timestamps."""
    from cutagent.probe import keyframes
    try:
        kfs = keyframes(args.file)
        return _json_out({"path": args.file, "keyframes": kfs, "count": len(kfs)})
    except CutAgentError as exc:
        return _json_error(exc, EXIT_VALIDATION)


def cmd_scenes(args) -> int:
    """Detect scene boundaries."""
    from cutagent.probe import detect_scenes
    try:
        scenes = detect_scenes(
            args.file,
            threshold=args.threshold,
            frame_output_dir=args.output_dir,
        )
        return _json_out({
            "path": args.file,
            "scenes": [scene.to_dict() for scene in scenes],
            "count": len(scenes),
            "threshold": args.threshold,
            "output_dir": args.output_dir,
        })
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)


def cmd_frames(args) -> int:
    """Extract still frames at specific timestamps."""
    from cutagent.models import parse_time
    from cutagent.probe import extract_frames
    try:
        timestamps = [parse_time(v.strip()) for v in args.at.split(",") if v.strip()]
        frames = extract_frames(
            args.file,
            timestamps=timestamps,
            output_dir=args.output_dir,
            image_format=args.format,
        )
        return _json_out({
            "path": args.file,
            "frames": [frame.to_dict() for frame in frames],
            "count": len(frames),
        })
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)
    except ValueError as exc:
        return _json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Check --at timestamps and --format values"],
        }, EXIT_VALIDATION)


def cmd_thumbnail(args) -> int:
    """Extract a single thumbnail image."""
    from cutagent.models import parse_time
    from cutagent.probe import thumbnail
    try:
        frame = thumbnail(args.file, timestamp=parse_time(args.at), output=args.output)
        return _json_out({"path": args.file, "thumbnail": frame.to_dict()})
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)
    except ValueError as exc:
        return _json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use a valid timestamp in --at"],
        }, EXIT_VALIDATION)


def cmd_silence(args) -> int:
    """Detect silence intervals."""
    from cutagent.probe import detect_silence
    try:
        intervals = detect_silence(
            args.file,
            threshold=args.threshold,
            min_duration=args.min_duration,
        )
        return _json_out({
            "path": args.file,
            "silences": [interval.to_dict() for interval in intervals],
            "count": len(intervals),
            "threshold_db": args.threshold,
            "min_duration": args.min_duration,
        })
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)


def cmd_audio_levels(args) -> int:
    """Compute audio levels over time."""
    from cutagent.probe import audio_levels
    try:
        levels = audio_levels(args.file, interval=args.interval)
        return _json_out({
            "path": args.file,
            "interval": args.interval,
            "audio_levels": [level.to_dict() for level in levels],
            "count": len(levels),
        })
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)
    except ValueError as exc:
        return _json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use --interval > 0"],
        }, EXIT_VALIDATION)


def cmd_summarize(args) -> int:
    """Generate a unified content map."""
    from cutagent.probe import summarize
    try:
        result = summarize(
            args.file,
            frame_dir=args.frame_dir,
            scene_threshold=args.scene_threshold,
            silence_threshold=args.silence_threshold,
            min_silence_duration=args.min_silence_duration,
            audio_interval=args.audio_interval,
            include_audio_levels=args.include_audio_levels,
        )
        return _json_out({"summary": result.to_dict()})
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)


def cmd_trim(args) -> int:
    """Trim a video segment."""
    from cutagent.operations import trim
    try:
        result = trim(args.file, args.start, args.end, args.output, codec=args.codec)
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)


def cmd_split(args) -> int:
    """Split a video at given points."""
    from cutagent.operations import split
    try:
        points = args.at.split(",")
        results = split(args.file, points, args.prefix, codec=args.codec)
        return _json_out({
            "segments": [r.to_dict() for r in results],
            "count": len(results),
        })
    except CutAgentError as exc:
        return _json_error(exc)


def cmd_concat(args) -> int:
    """Concatenate video files."""
    from cutagent.operations import concat
    try:
        result = concat(
            args.files,
            args.output,
            codec=args.codec,
            transition=args.transition,
            transition_duration=args.transition_duration,
        )
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)
    except ValueError as exc:
        return _json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Check --transition and --transition-duration values"],
        }, EXIT_VALIDATION)


def cmd_fade(args) -> int:
    """Apply audio/video fade effects."""
    from cutagent.operations import fade
    try:
        result = fade(
            args.file,
            args.output,
            fade_in=args.fade_in,
            fade_out=args.fade_out,
            codec=args.codec,
        )
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)
    except ValueError as exc:
        return _json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use non-negative fade values and ensure total fade fits clip duration"],
        }, EXIT_VALIDATION)


def cmd_speed(args) -> int:
    """Change playback speed of a video."""
    from cutagent.operations import speed
    try:
        result = speed(
            args.file,
            args.output,
            factor=args.factor,
            codec=args.codec,
        )
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)
    except ValueError as exc:
        return _json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use --factor between 0.25 and 100.0"],
        }, EXIT_VALIDATION)


def cmd_extract(args) -> int:
    """Extract audio or video stream."""
    from cutagent.operations import extract_stream
    try:
        result = extract_stream(args.file, args.stream, args.output)
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)


def cmd_mix(args) -> int:
    """Mix an audio track into a video."""
    from cutagent.audio_ops import mix_audio
    try:
        result = mix_audio(
            args.file, args.audio, args.output,
            mix_level=args.mix_level,
            codec=args.codec,
        )
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)


def cmd_volume(args) -> int:
    """Adjust audio volume."""
    from cutagent.audio_ops import adjust_volume
    try:
        result = adjust_volume(
            args.file, args.output,
            gain_db=args.gain_db,
            codec=args.codec,
        )
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)


def cmd_replace_audio(args) -> int:
    """Replace a video's audio track."""
    from cutagent.audio_ops import replace_audio
    try:
        result = replace_audio(
            args.file, args.audio, args.output,
            codec=args.codec,
        )
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)


def cmd_normalize(args) -> int:
    """Normalize audio loudness (EBU R128)."""
    from cutagent.audio_ops import normalize_audio
    try:
        result = normalize_audio(
            args.file, args.output,
            target_lufs=args.target_lufs,
            true_peak_dbtp=args.true_peak_dbtp,
            codec=args.codec,
        )
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc)


def cmd_beats(args) -> int:
    """Detect musical beats/onsets in audio."""
    from cutagent.probe import detect_beats
    try:
        result = detect_beats(
            args.file,
            min_interval=args.min_interval,
            energy_threshold=args.energy_threshold,
        )
        beats_list = [b.to_dict() for b in result["beats"]]
        return _json_out({
            "path": args.file,
            "beats": beats_list,
            "count": result["count"],
            "bpm": result["bpm"],
        })
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)


def _read_edl_input(edl_arg: str | None = None, edl_json: str | None = None) -> str:
    """Read EDL from inline JSON, stdin (if '-'), or from a file path.

    Args:
        edl_arg: Path to EDL file, or '-' for stdin.
        edl_json: Inline EDL JSON string.

    Returns:
        EDL JSON string.
    """
    if edl_json:
        return edl_json
    if edl_arg is None:
        raise CutAgentError(
            code="MISSING_FIELD",
            message="No EDL provided — pass a file path, use '-' for stdin, or use --edl-json",
            recovery=["Provide an EDL file path", "Use '-' to read from stdin", "Use --edl-json '{...}'"],
        )
    if edl_arg == "-":
        return sys.stdin.read()
    try:
        return Path(edl_arg).read_text()
    except FileNotFoundError:
        raise FileNotFoundError(f"EDL file not found: {edl_arg}")


def cmd_validate(args) -> int:
    """Validate an EDL without executing."""
    from cutagent.validation import validate_edl
    try:
        edl_text = _read_edl_input(
            getattr(args, "edl", None),
            getattr(args, "edl_json", None),
        )
        result = validate_edl(edl_text)
        code = EXIT_SUCCESS if result.valid else EXIT_VALIDATION
        return _json_out(result.to_dict(), code)
    except CutAgentError as exc:
        return _json_error(exc, EXIT_VALIDATION)
    except FileNotFoundError:
        return _json_out({
            "error": True, "code": "INPUT_NOT_FOUND",
            "message": f"EDL file not found: {args.edl}",
            "recovery": ["Check the file path, or use '-' to read from stdin, or use --edl-json"],
        }, EXIT_VALIDATION)


def _make_progress_callback(quiet: bool):
    """Return a progress callback that writes JSONL to stderr, or None if quiet."""
    if quiet:
        return None

    def _progress(step: int, total: int, op_name: str, status: str) -> None:
        line = json.dumps({"progress": {"step": step, "total": total, "op": op_name, "status": status}})
        print(line, file=sys.stderr, flush=True)

    return _progress


def cmd_execute(args) -> int:
    """Execute an EDL."""
    from cutagent.engine import execute_edl
    try:
        edl_text = _read_edl_input(
            getattr(args, "edl", None),
            getattr(args, "edl_json", None),
        )
        callback = _make_progress_callback(getattr(args, "quiet", False))
        result = execute_edl(edl_text, progress_callback=callback)
        return _json_out(result.to_dict())
    except CutAgentError as exc:
        return _json_error(exc, EXIT_EXECUTION)
    except FileNotFoundError:
        return _json_out({
            "error": True, "code": "INPUT_NOT_FOUND",
            "message": f"EDL file not found: {getattr(args, 'edl', None)}",
            "recovery": ["Check the file path, or use '-' to read from stdin, or use --edl-json"],
        }, EXIT_VALIDATION)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="cutagent",
        description="Agent-first video cutting — all output is JSON",
    )
    sub = parser.add_subparsers(dest="command")

    # capabilities
    sub.add_parser("capabilities", help="List all operations and their schemas")

    # probe
    p = sub.add_parser("probe", help="Probe a media file for metadata")
    p.add_argument("file", help="Path to the media file")

    # keyframes
    p = sub.add_parser("keyframes", help="List keyframe timestamps")
    p.add_argument("file", help="Path to the media file")

    # scenes
    p = sub.add_parser("scenes", help="Detect scene boundaries")
    p.add_argument("file", help="Path to the media file")
    p.add_argument("--threshold", type=float, default=0.3, help="Scene detection threshold (0.0–1.0)")
    p.add_argument("--output-dir", help="Optional output directory for scene preview frames")

    # frames
    p = sub.add_parser("frames", help="Extract frames at one or more timestamps")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("--at", required=True, help="Comma-separated timestamps")
    p.add_argument("--output-dir", required=True, help="Directory for extracted frames")
    p.add_argument("--format", default="jpg", choices=["jpg", "jpeg", "png"], help="Image format")

    # thumbnail
    p = sub.add_parser("thumbnail", help="Extract a single thumbnail frame")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("--at", required=True, help="Thumbnail timestamp")
    p.add_argument("-o", "--output", required=True, help="Output image path")

    # silence
    p = sub.add_parser("silence", help="Detect silence intervals")
    p.add_argument("file", help="Path to the source media")
    p.add_argument("--threshold", type=float, default=-30.0, help="Silence threshold in dB")
    p.add_argument("--min-duration", type=float, default=0.5, help="Minimum silence duration in seconds")

    # audio-levels
    p = sub.add_parser("audio-levels", help="Compute audio levels over time")
    p.add_argument("file", help="Path to the source media")
    p.add_argument("--interval", type=float, default=1.0, help="Aggregation interval in seconds")

    # summarize
    p = sub.add_parser("summarize", help="Build a full content summary")
    p.add_argument("file", help="Path to the source media")
    p.add_argument("--frame-dir", help="Optional directory to write scene frame previews")
    p.add_argument("--scene-threshold", type=float, default=0.3, help="Scene detection threshold")
    p.add_argument("--silence-threshold", type=float, default=-30.0, help="Silence threshold in dB")
    p.add_argument("--min-silence-duration", type=float, default=0.5, help="Minimum silence duration")
    p.add_argument("--audio-interval", type=float, default=1.0, help="Audio level interval in seconds")
    p.add_argument("--include-audio-levels", action="store_true", default=False,
                   help="Include per-second audio levels in output (verbose)")

    # trim
    p = sub.add_parser("trim", help="Trim a video segment")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("--start", required=True, help="Start time")
    p.add_argument("--end", required=True, help="End time")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--codec", default="copy", help="Codec: 'copy' (default) or codec name")

    # split
    p = sub.add_parser("split", help="Split a video at given points")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("--at", required=True, help="Comma-separated split points (e.g. 00:05:00,00:10:00)")
    p.add_argument("--prefix", required=True, help="Output file prefix (e.g. 'segment')")
    p.add_argument("--codec", default="copy", help="Codec: 'copy' (default) or codec name")

    # concat
    p = sub.add_parser("concat", help="Concatenate video files")
    p.add_argument("files", nargs="+", help="Video files to concatenate")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--codec", default="copy", help="Codec: 'copy' (default) or codec name")
    p.add_argument("--transition", choices=["crossfade"], help="Optional transition type")
    p.add_argument("--transition-duration", type=float, default=0.5, help="Transition duration in seconds")

    # fade
    p = sub.add_parser("fade", help="Apply fade-in/fade-out effects")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--fade-in", type=float, default=0.0, help="Fade-in duration in seconds")
    p.add_argument("--fade-out", type=float, default=0.0, help="Fade-out duration in seconds")
    p.add_argument("--codec", default="libx264", help="Video codec (default: libx264)")

    # speed
    p = sub.add_parser("speed", help="Change playback speed")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--factor", type=float, required=True, help="Speed factor (>1 faster, <1 slower)")
    p.add_argument("--codec", default="libx264", help="Video codec (default: libx264)")

    # extract
    p = sub.add_parser("extract", help="Extract audio or video stream")
    p.add_argument("file", help="Path to the source file")
    p.add_argument("--stream", required=True, choices=["audio", "video"], help="Stream to extract")
    p.add_argument("-o", "--output", required=True, help="Output file path")

    # mix (audio overlay)
    p = sub.add_parser("mix", help="Mix an audio track into a video")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("--audio", required=True, help="Path to the audio file to mix in")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--mix-level", type=float, default=0.3,
                   help="Volume weight for the mixed audio (0.0–1.0, default 0.3)")
    p.add_argument("--codec", default="libx264", help="Video codec (default: libx264)")

    # volume
    p = sub.add_parser("volume", help="Adjust audio volume")
    p.add_argument("file", help="Path to the source file")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--gain-db", type=float, required=True,
                   help="Gain in dB (positive = louder, negative = quieter)")
    p.add_argument("--codec", default="copy", help="Video codec (default: copy)")

    # replace-audio
    p = sub.add_parser("replace-audio", help="Replace a video's audio track")
    p.add_argument("file", help="Path to the source video")
    p.add_argument("--audio", required=True, help="Path to the replacement audio file")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--codec", default="copy", help="Video codec (default: copy)")

    # normalize
    p = sub.add_parser("normalize", help="Normalize audio loudness (EBU R128)")
    p.add_argument("file", help="Path to the source file")
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument("--target-lufs", type=float, default=-16.0,
                   help="Target integrated loudness in LUFS (default: -16.0)")
    p.add_argument("--true-peak-dbtp", type=float, default=-1.5,
                   help="Maximum true peak in dBTP (default: -1.5)")
    p.add_argument("--codec", default="libx264", help="Video codec (default: libx264)")

    # beats
    p = sub.add_parser("beats", help="Detect musical beats/onsets in audio")
    p.add_argument("file", help="Path to the source media")
    p.add_argument("--min-interval", type=float, default=0.15,
                   help="Minimum seconds between beats (default: 0.15)")
    p.add_argument("--energy-threshold", type=float, default=1.4,
                   help="Energy spike threshold multiplier (default: 1.4)")

    # validate
    p = sub.add_parser("validate", help="Validate an EDL (dry-run)")
    p.add_argument("edl", nargs="?", default=None,
                   help="Path to the EDL JSON file (or '-' for stdin)")
    p.add_argument("--edl-json", dest="edl_json", default=None,
                   help="Inline EDL JSON string (alternative to file path)")

    # execute
    p = sub.add_parser("execute", help="Execute an EDL")
    p.add_argument("edl", nargs="?", default=None,
                   help="Path to the EDL JSON file (or '-' for stdin)")
    p.add_argument("--edl-json", dest="edl_json", default=None,
                   help="Inline EDL JSON string (alternative to file path)")
    p.add_argument("-q", "--quiet", action="store_true", default=False,
                   help="Suppress progress output on stderr")

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(EXIT_VALIDATION)

    handlers = {
        "capabilities": cmd_capabilities,
        "probe": cmd_probe,
        "keyframes": cmd_keyframes,
        "scenes": cmd_scenes,
        "frames": cmd_frames,
        "thumbnail": cmd_thumbnail,
        "silence": cmd_silence,
        "audio-levels": cmd_audio_levels,
        "beats": cmd_beats,
        "summarize": cmd_summarize,
        "trim": cmd_trim,
        "split": cmd_split,
        "concat": cmd_concat,
        "fade": cmd_fade,
        "speed": cmd_speed,
        "extract": cmd_extract,
        "mix": cmd_mix,
        "volume": cmd_volume,
        "replace-audio": cmd_replace_audio,
        "normalize": cmd_normalize,
        "validate": cmd_validate,
        "execute": cmd_execute,
    }

    try:
        exit_code = handlers[args.command](args)
    except CutAgentError as exc:
        exit_code = _json_error(exc, EXIT_SYSTEM)
    except Exception as exc:
        exit_code = _json_out({
            "error": True,
            "code": "UNEXPECTED_ERROR",
            "message": str(exc),
            "recovery": ["This is an unexpected error — please report it"],
        }, EXIT_SYSTEM)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
