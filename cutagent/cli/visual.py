import json as _json
from typing import Optional

import typer

from cutagent.cli.utils import (
    animate_layer_summary,
    json_error,
    json_out,
    read_json_arg,
    review_timestamps_from_entries,
    review_timestamps_from_layers,
    text_layer_summary,
)
from cutagent.errors import EXIT_VALIDATION, CutAgentError

app = typer.Typer(help="Visual polish and effects commands")

@app.command("fade")
def cmd_fade(
    file: str,
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    fade_in: float = typer.Option(0.0, help="Fade-in duration in seconds"),
    fade_out: float = typer.Option(0.0, help="Fade-out duration in seconds"),
    codec: str = typer.Option("libx264", help="Video codec (default: libx264)"),
) -> int:
    """Apply audio/video fade effects."""
    from cutagent.operations import fade
    try:
        result = fade(
            file,
            output,
            fade_in=fade_in,
            fade_out=fade_out,
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
            "recovery": ["Use non-negative fade values and ensure total fade fits clip duration"],
        }, EXIT_VALIDATION)

@app.command("text")
def cmd_text(
    file: str,
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    entries_json: Optional[str] = typer.Option(None, help="JSON array of text entries (or a single entry object)"),
    entries_file: Optional[str] = typer.Option(None, help="Path to a JSON file containing text entries"),
    codec: str = typer.Option("libx264", help="Video codec (default: libx264)"),
) -> int:
    """Burn text overlays onto a video."""
    from cutagent.models import TextEntry
    from cutagent.text_ops import add_text
    try:
        raw_json = read_json_arg(entries_json, entries_file, "entries_json", "entries_file")
        entries_raw = _json.loads(raw_json)
        if isinstance(entries_raw, dict):
            entries_raw = [entries_raw]
        entries = [TextEntry.from_dict(e) for e in entries_raw]
        result = add_text(
            file, entries, output,
            codec=codec,
        )
        out = result.to_dict()
        out["text_layers"] = text_layer_summary(entries)
        out["review_timestamps"] = review_timestamps_from_entries(entries)
        return json_out(out)
    except CutAgentError as exc:
        return json_error(exc)
    except (_json.JSONDecodeError, KeyError, TypeError) as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": f"Invalid --entries-json: {exc}",
            "recovery": [
                "Pass a JSON array of text entry objects",
                "Each entry needs at minimum a 'text' field",
                "Example: '[{\"text\": \"Hello\", \"position\": \"center\"}]'",
            ],
        }, EXIT_VALIDATION)

@app.command("animate")
def cmd_animate(
    file: str,
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    layers_json: Optional[str] = typer.Option(None, help="JSON array of animation layer objects (or a single layer object)"),
    layers_file: Optional[str] = typer.Option(None, help="Path to a JSON file containing animation layers"),
    fps: int = typer.Option(30, help="Output frame rate (default: 30)"),
    codec: str = typer.Option("libx264", help="Video codec (default: libx264)"),
) -> int:
    """Apply keyframe-driven animations onto a video."""
    from cutagent.animation_ops import animate
    from cutagent.models import AnimationLayer
    try:
        raw_json = read_json_arg(layers_json, layers_file, "layers_json", "layers_file")
        layers_raw = _json.loads(raw_json)
        if isinstance(layers_raw, dict):
            layers_raw = [layers_raw]
        layers = [AnimationLayer.from_dict(layer) for layer in layers_raw]
        result = animate(
            file, layers, output,
            fps=fps,
            codec=codec,
        )
        out = result.to_dict()
        out["text_layers"] = animate_layer_summary(layers)
        out["review_timestamps"] = review_timestamps_from_layers(layers)
        return json_out(out)
    except CutAgentError as exc:
        return json_error(exc)
    except (_json.JSONDecodeError, KeyError, TypeError) as exc:
        return json_out({
            "error": True,
            "code": "INVALID_ARGUMENT",
            "message": f"Invalid --layers-json: {exc}",
            "recovery": [
                "Pass a JSON array of animation layer objects",
                "Each layer needs 'type' and 'properties' fields",
                "Example: '[{\"type\": \"text\", \"text\": \"Hello\", \"start\": 0, \"end\": 3, "
                "\"properties\": {\"opacity\": {\"keyframes\": [{\"t\": 0, \"value\": 0}, {\"t\": 1, \"value\": 1}]}}}]'",
            ],
        }, EXIT_VALIDATION)
