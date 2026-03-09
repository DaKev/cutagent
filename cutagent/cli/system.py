import typer

from cutagent.cli.utils import json_out
from cutagent.schema_registry import (
    cli_command_schema,
    edl_schema,
    operation_names,
    operation_payload_schema,
    schema_index,
)

app = typer.Typer(help="System and capability commands")

@app.command("capabilities")
def capabilities() -> int:
    """Output machine-readable schema of all operations."""
    return json_out(capabilities_payload())


def capabilities_payload() -> dict:
    """Return machine-readable capability data for agent clients."""
    return {
        "version": "1.0",
        "overview": (
            "CutAgent provides analysis, editing, audio polish, and visual polish. "
            "Professional video results require all four — not just cutting. "
            "Agents should always consider audio normalization, text overlays, "
            "and transitions, even when the user only asks to 'edit' or 'cut' a video."
        ),
        "operation_categories": {
            "analysis": {
                "description": "Understand the source material before making any cuts",
                "commands": [
                    "probe", "summarize", "scenes", "silence", "beats",
                    "keyframes", "audio-levels", "frames", "thumbnail",
                ],
            },
            "editing": {
                "description": "Cut, arrange, and pace the video",
                "operations": ["trim", "split", "concat", "reorder", "extract", "speed"],
            },
            "audio_polish": {
                "description": "Professional audio — always consider these (the #1 difference between amateur and professional edits)",
                "operations": ["normalize", "mix_audio", "volume", "replace_audio"],
            },
            "visual_polish": {
                "description": "Titles, annotations, and motion graphics — give the viewer context",
                "operations": ["text", "animate", "fade"],
            },
        },
        "quality_checklist": [
            "Audio normalized? (normalize) — inconsistent volume is the #1 amateur mistake",
            "Transitions smooth? (fade, concat+crossfade) — hard cuts between unrelated clips feel jarring",
            "Titles/context added? (text, animate) — viewers need to know what they are watching",
            "Background music? (mix_audio at 0.1–0.2) — subtle music fills silence and sets mood",
            "Pacing right? (speed) — slow parts lose viewer attention, consider speeding up",
        ],
        "operations": {
            "trim": {
                "description": "Extract a segment between two timestamps",
                "fields": {"op": "'trim'", "source": "str", "start": "time", "end": "time"},
                "supports_copy_codec": True,
                "edl_compatible": True,
            },
            "split": {
                "description": "Split a video at one or more timestamps",
                "fields": {"op": "'split'", "source": "str", "points": "list[time]"},
                "supports_copy_codec": True,
                "edl_compatible": True,
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
                "edl_compatible": True,
            },
            "reorder": {
                "description": "Reorder segments by index and concatenate",
                "fields": {"op": "'reorder'", "segments": "list[str]", "order": "list[int]"},
                "supports_copy_codec": True,
                "edl_compatible": True,
            },
            "extract": {
                "description": "Extract audio or video stream",
                "fields": {"op": "'extract'", "source": "str", "stream": "'audio' | 'video'"},
                "supports_copy_codec": True,
                "edl_compatible": True,
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
                "edl_compatible": True,
            },
            "speed": {
                "description": "Change playback speed (slow-motion or speed-up)",
                "fields": {
                    "op": "'speed'",
                    "source": "str",
                    "factor": "float (0.25–100.0; >1 = faster, <1 = slower)",
                },
                "supports_copy_codec": False,
                "edl_compatible": True,
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
                "edl_compatible": True,
            },
            "volume": {
                "description": "Adjust audio volume by a dB gain value",
                "fields": {
                    "op": "'volume'",
                    "source": "str",
                    "gain_db": "float (-60.0 to 60.0; positive = louder)",
                },
                "supports_copy_codec": True,
                "edl_compatible": True,
            },
            "replace_audio": {
                "description": "Replace a video's audio track with a different audio file",
                "fields": {
                    "op": "'replace_audio'",
                    "source": "str (video — keeps video stream)",
                    "audio": "str (replacement audio file)",
                },
                "supports_copy_codec": True,
                "edl_compatible": True,
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
                "edl_compatible": True,
            },
            "text": {
                "description": "Burn text overlays, titles, descriptions, or annotations onto a video",
                "fields": {
                    "op": "'text'",
                    "source": "str",
                    "entries": "list[TextEntry]",
                },
                "entry_fields": {
                    "text": "str (required — the text to display)",
                    "position": "str (default 'center'; presets: center, top-center, bottom-center, "
                                "top-left, top-right, bottom-left, bottom-right; or 'x,y')",
                    "font_size": "int (default 48)",
                    "font_color": "str (default 'white'; any FFmpeg color name or hex)",
                    "start": "time (optional — when text appears)",
                    "end": "time (optional — when text disappears)",
                    "bg_color": "str (optional — e.g. 'black@0.5' for semi-transparent background)",
                    "bg_padding": "int (default 10 — padding around text when bg_color is set)",
                    "font": "str (optional — font family name; auto-detects system sans-serif if omitted)",
                    "shadow_color": "str (optional — e.g. 'black' for drop shadow behind text)",
                    "shadow_offset": "int (default 0 — pixel offset for shadow in both x and y)",
                    "stroke_color": "str (optional — e.g. 'black' for text outline/border)",
                    "stroke_width": "int (default 0 — pixel width of text outline)",
                },
                "supports_copy_codec": False,
                "edl_compatible": True,
            },
            "animate": {
                "description": "Apply keyframe-driven animations (text/image layers) onto a video — Remotion-style declarative motion",
                "fields": {
                    "op": "'animate'",
                    "source": "str",
                    "fps": "int (default 30)",
                    "layers": "list[AnimationLayer]",
                },
                "layer_fields": {
                    "type": "str ('text' or 'image')",
                    "start": "float (seconds — when layer appears)",
                    "end": "float (seconds — when layer disappears)",
                    "properties": "dict[str, AnimationProperty] — animated properties",
                    "text": "str (required for text layers)",
                    "font_size": "int (default 48, for text layers)",
                    "font_color": "str (default 'white', for text layers)",
                    "font": "str (optional, for text layers; auto-detects system sans-serif if omitted)",
                    "bg_color": "str (optional — e.g. 'black@0.5' for semi-transparent background box)",
                    "bg_padding": "int (default 10 — padding around text when bg_color is set)",
                    "shadow_color": "str (optional — e.g. 'black' for drop shadow behind text)",
                    "shadow_offset": "int (default 0 — pixel offset for shadow in both x and y)",
                    "stroke_color": "str (optional — e.g. 'black' for text outline/border)",
                    "stroke_width": "int (default 0 — pixel width of text outline)",
                    "path": "str (required for image layers — path to image file)",
                },
                "property_fields": {
                    "keyframes": "list[{t: float, value: float}] — time/value pairs",
                    "easing": "str (default 'linear'; options: linear, ease-in, ease-out, ease-in-out, spring)",
                },
                "keyframe_t_note": "t is absolute timeline time in seconds, not relative to layer start",
                "animatable_properties": {
                    "text": ["x", "y", "opacity", "font_size"],
                    "image": ["x", "y", "opacity", "scale"],
                },
                "supports_copy_codec": False,
                "edl_compatible": True,
            },
        },
        "operation_examples": {
            "_note": "All fields are top-level in the operation object — there is NO 'params' wrapper",
            "trim": {"op": "trim", "source": "$input.0", "start": "00:00:04", "end": "00:00:12"},
            "split": {"op": "split", "source": "$input.0", "points": ["00:05:00", "00:10:00"]},
            "concat": {"op": "concat", "segments": ["$0", "$1"]},
            "concat_crossfade": {
                "op": "concat", "segments": ["$0", "$1"],
                "transition": "crossfade", "transition_duration": 0.5,
            },
            "fade": {"op": "fade", "source": "$0", "fade_in": 1.0, "fade_out": 1.0},
            "speed": {"op": "speed", "source": "$0", "factor": 2.0},
            "extract": {"op": "extract", "source": "$input.0", "stream": "audio"},
            "mix_audio": {"op": "mix_audio", "source": "$0", "audio": "$input.1", "mix_level": 0.2},
            "volume": {"op": "volume", "source": "$0", "gain_db": 6.0},
            "replace_audio": {"op": "replace_audio", "source": "$0", "audio": "$input.1"},
            "normalize": {"op": "normalize", "source": "$0"},
            "text": {
                "op": "text", "source": "$input.0",
                "entries": [
                    {"text": "Interview Title", "position": "center", "font_size": 72,
                     "font_color": "white", "start": "0", "end": "3", "bg_color": "black@0.5"},
                ],
            },
            "text_lower_third": {
                "op": "text", "source": "$0",
                "entries": [
                    {"text": "Jane Doe — CEO", "position": "bottom-left", "font_size": 36,
                     "font_color": "white", "bg_color": "black@0.6", "bg_padding": 12,
                     "start": "00:00:02", "end": "00:00:08"},
                ],
            },
            "animate": {
                "op": "animate", "source": "$input.0", "fps": 30,
                "layers": [
                    {
                        "type": "text", "text": "Hello World",
                        "font_size": 48, "font_color": "white",
                        "bg_color": "black@0.5", "bg_padding": 12,
                        "start": 0.0, "end": 3.0,
                        "properties": {
                            "x": {"keyframes": [{"t": 0.0, "value": -200}, {"t": 1.0, "value": 100}], "easing": "ease-out"},
                            "opacity": {"keyframes": [{"t": 0.0, "value": 0.0}, {"t": 0.5, "value": 1.0}], "easing": "linear"},
                        },
                    },
                ],
            },
        },
        "time_formats": ["HH:MM:SS", "HH:MM:SS.mmm", "MM:SS", "seconds"],
        "edl_format": {
            "required_fields": ["version", "inputs", "operations", "output"],
            "version": "1.0",
            "inputs": "list[str] — source file paths",
            "operations": "list[op] — sequential operations (each op can have optional 'id' for named references)",
            "output": {"path": "str", "codec": "'copy' | codec_name"},
            "references": {
                "$input.N": "Reference input file by index (e.g. $input.0 for the first input)",
                "$N": "Reference output of operation N (e.g. $0 for first operation's result)",
                "$name": "Reference output of a named operation by its 'id' field (e.g. $trimmed)",
            },
            "edl_input_methods": [
                "File path: cutagent execute my_edit.json",
                "Stdin: echo '{...}' | cutagent execute -",
                "Inline: cutagent execute --edl-json '{...}'",
            ],
            "minimal_example": {
                "version": "1.0",
                "inputs": ["/path/to/input.mp4"],
                "operations": [
                    {"op": "trim", "source": "$input.0", "start": "0", "end": "10"},
                ],
                "output": {"path": "output.mp4", "codec": "libx264"},
            },
            "named_reference_example": {
                "version": "1.0",
                "inputs": ["/path/to/input.mp4"],
                "operations": [
                    {"op": "trim", "id": "clip", "source": "$input.0", "start": "0", "end": "10"},
                    {"op": "speed", "source": "$clip", "factor": 2.0},
                ],
                "output": {"path": "output.mp4", "codec": "libx264"},
            },
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
        "agent_workflow": {
            "_note": "Professional editing has 4 phases. Skipping audio or visual polish produces amateur results.",
            "phases": {
                "1_analyze": {
                    "name": "Analyze the source material",
                    "why": "You cannot make good editing decisions without understanding the content",
                    "steps": [
                        "Run 'summarize' with --frame-dir to get content map and scene preview frames",
                        "Review scene frames to understand visual content of each scene",
                        "Run 'beats' if music or rhythm-aligned cuts are relevant",
                        "Use 'suggested_cut_points' and beat timestamps to plan transitions",
                    ],
                },
                "2_edit": {
                    "name": "Cut and arrange",
                    "why": "Select the best content and remove dead air",
                    "steps": [
                        "Trim clips at scene boundaries or suggested cut points",
                        "Reorder or concat segments into the desired narrative",
                        "Adjust speed for pacing (speed up slow sections, slow-mo for emphasis)",
                    ],
                },
                "3_audio_polish": {
                    "name": "Polish the audio",
                    "why": "Bad audio ruins good video — this phase is NOT optional",
                    "steps": [
                        "Use 'normalize' to even out loudness (always do this)",
                        "Use 'mix_audio' to layer background music at a subtle level (mix_level 0.1–0.2)",
                        "Use 'volume' to boost quiet clips or reduce loud ones before concat",
                        "Use 'crossfade' transition in concat for smooth audio between clips",
                    ],
                },
                "4_visual_polish": {
                    "name": "Add titles, transitions, and visual context",
                    "why": "Titles tell the viewer what they are watching; transitions create flow",
                    "steps": [
                        "Apply 'fade' (fade_in/fade_out) for polished opening and closing",
                        "Use 'text' to add titles, lower-thirds, or annotations with timed display",
                        "Use 'animate' for motion graphics (slide-in titles, fade-in captions)",
                        "After text/animate, extract frames at review_timestamps to verify overlays",
                    ],
                },
            },
            "execute": "Combine all operations into a single EDL for multi-step edits with $N references",
        },
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
        "recipes": {
            "_note": "Common editing patterns — each combines multiple operations for professional results",
            "interview_cleanup": {
                "description": "Clean up an interview recording",
                "operations": [
                    {"op": "summarize", "why": "Find silence gaps and scene boundaries"},
                    {"op": "trim", "why": "Remove intro/outro dead air"},
                    {"op": "normalize", "why": "Ensure consistent loudness throughout"},
                    {"op": "text", "why": "Add speaker name as lower-third"},
                    {"op": "fade", "why": "Smooth fade-in opening and fade-out closing"},
                ],
            },
            "highlight_reel": {
                "description": "Create a highlight reel from longer footage",
                "operations": [
                    {"op": "summarize", "why": "Identify scene boundaries and key moments"},
                    {"op": "trim", "why": "Extract the best clips (multiple trims)"},
                    {"op": "normalize", "why": "Even out audio levels across clips"},
                    {"op": "concat+crossfade", "why": "Join clips with smooth crossfade transitions"},
                    {"op": "mix_audio", "why": "Add background music to tie clips together"},
                    {"op": "text", "why": "Add title card at start and section labels"},
                    {"op": "fade", "why": "Fade in at start, fade out at end"},
                ],
            },
            "tutorial_polish": {
                "description": "Polish a screen recording or tutorial",
                "operations": [
                    {"op": "silence", "why": "Find pauses and dead air to cut out"},
                    {"op": "trim", "why": "Remove long pauses and mistakes"},
                    {"op": "speed", "why": "Speed up repetitive sections (2x)"},
                    {"op": "normalize", "why": "Clean up microphone audio levels"},
                    {"op": "text", "why": "Add step labels and annotations"},
                    {"op": "animate", "why": "Animated callouts for key moments"},
                ],
            },
        },
        "tips": [
            "crossfade and fade require re-encoding (codec must not be 'copy')",
            "Use 'libx264' codec when transitions or fades are needed",
            "Scene frames at 10/50/90% offsets give a filmstrip of each scene",
            "Operations needing re-encode: fade, crossfade concat, speed, mix_audio, normalize, text",
            "Use 'speed' with factor <1 for slow-motion, >1 for fast-forward",
            "Use $input.0 in operations to reference the first input file",
            "Use --edl-json to pass EDL inline without writing a temp file",
            "Use 'normalize' (target_lufs=-16) before concat to ensure consistent loudness",
            "Use 'mix_audio' with mix_level 0.1–0.2 for subtle background music",
            "Use 'beats' to detect rhythm — cut on beats for music-driven edits",
            "Use 'volume' to boost quiet clips or reduce loud ones (gain_db in dB)",
            "Use --entries-file / --layers-file to read JSON from a file instead of inline",
            "text and animate output includes review_timestamps — use with 'frames --at' to verify overlays",
            "Use bg_color + shadow_color on animate text layers for readable lower-thirds",
        ],
    }


@app.command("schema")
def schema(
    target: str = typer.Argument("index", help="Schema target: index|edl|operation|command|capabilities"),
    name: str | None = typer.Argument(None, help="Optional item name, e.g. operation name"),
) -> int:
    """Output machine-readable schema for commands, operations, and EDL."""
    if target == "index":
        return json_out(schema_index())
    if target == "edl":
        return json_out({"target": "edl", "schema": edl_schema()})
    if target == "command":
        return json_out({"target": "command", "schema": cli_command_schema()})
    if target == "capabilities":
        return json_out({"target": "capabilities", "schema": capabilities_payload()})
    if target == "operation":
        if not name:
            return json_out({
                "error": True,
                "code": "MISSING_FIELD",
                "message": "schema target 'operation' requires an operation name",
                "recovery": [f"Pass one of: {', '.join(operation_names())}"],
            }, exit_code=1)
        try:
            return json_out({
                "target": "operation",
                "name": name,
                "schema": operation_payload_schema(name),
            })
        except ValueError:
            return json_out({
                "error": True,
                "code": "UNKNOWN_OPERATION",
                "message": f"Unknown operation: {name!r}",
                "recovery": [f"Use one of: {', '.join(operation_names())}"],
            }, exit_code=1)

    return json_out({
        "error": True,
        "code": "INVALID_ARGUMENT",
        "message": f"Unknown schema target: {target!r}",
        "recovery": ["Use one of: index, edl, operation, command, capabilities"],
    }, exit_code=1)

@app.command("doctor")
def doctor() -> int:
    """Run diagnostic checks and report system health."""
    from cutagent.doctor import run_doctor
    return json_out(run_doctor())
