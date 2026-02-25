from typing import Optional

import typer

from cutagent.cli.utils import json_error, json_out
from cutagent.errors import EXIT_VALIDATION, CutAgentError

app = typer.Typer(help="Editing and modification commands")

@app.command("trim")
def cmd_trim(
    file: str,
    start: str = typer.Option(..., help="Start time"),
    end: str = typer.Option(..., help="End time"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    codec: str = typer.Option("copy", help="Codec: 'copy' (default) or codec name"),
) -> int:
    """Trim a video segment."""
    from cutagent.operations import trim
    try:
        result = trim(file, start, end, output, codec=codec)
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_TIME_FORMAT",
            "message": str(exc),
            "recovery": ["Use HH:MM:SS, HH:MM:SS.mmm, MM:SS, or plain seconds"],
        }, EXIT_VALIDATION)

@app.command("split")
def cmd_split(
    file: str,
    at: str = typer.Option(..., help="Comma-separated split points (e.g. 00:05:00,00:10:00)"),
    prefix: str = typer.Option(..., help="Output file prefix (e.g. 'segment')"),
    codec: str = typer.Option("copy", help="Codec: 'copy' (default) or codec name"),
) -> int:
    """Split a video at given points."""
    from cutagent.operations import split
    try:
        points = at.split(",")
        results = split(file, points, prefix, codec=codec)
        return json_out({
            "segments": [r.to_dict() for r in results],
            "count": len(results),
        })
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_TIME_FORMAT",
            "message": str(exc),
            "recovery": ["Use HH:MM:SS, HH:MM:SS.mmm, MM:SS, or plain seconds"],
        }, EXIT_VALIDATION)

@app.command("concat")
def cmd_concat(
    files: list[str] = typer.Argument(..., help="Video files to concatenate"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    codec: str = typer.Option("copy", help="Codec: 'copy' (default) or codec name"),
    transition: Optional[str] = typer.Option(None, help="Optional transition type (e.g. crossfade)"),
    transition_duration: float = typer.Option(0.5, help="Transition duration in seconds"),
) -> int:
    """Concatenate video files."""
    from cutagent.operations import concat
    try:
        result = concat(
            files,
            output,
            codec=codec,
            transition=transition,
            transition_duration=transition_duration,
        )
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Check --transition and --transition-duration values"],
        }, EXIT_VALIDATION)

@app.command("extract")
def cmd_extract(
    file: str,
    stream: str = typer.Option(..., help="Stream to extract ('audio' or 'video')"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
) -> int:
    """Extract audio or video stream."""
    from cutagent.operations import extract_stream
    try:
        if stream not in ["audio", "video"]:
            raise ValueError(f"Invalid stream type: {stream}")
        result = extract_stream(file, stream, output)
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use --stream 'audio' or 'video'"],
        }, EXIT_VALIDATION)

@app.command("speed")
def cmd_speed(
    file: str,
    factor: float = typer.Option(..., help="Speed factor (>1 faster, <1 slower)"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    codec: str = typer.Option("libx264", help="Video codec (default: libx264)"),
) -> int:
    """Change playback speed."""
    from cutagent.operations import speed
    try:
        result = speed(
            file,
            output,
            factor=factor,
            codec=codec,
        )
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)
    except ValueError as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": str(exc),
            "recovery": ["Use --factor between 0.25 and 100.0"],
        }, EXIT_VALIDATION)
