import typer

from cutagent.cli.utils import json_error, json_out
from cutagent.errors import CutAgentError

app = typer.Typer(help="Audio polish and manipulation commands")

@app.command("mix")
def cmd_mix(
    file: str,
    audio: str = typer.Option(..., help="Path to the audio file to mix in"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    mix_level: float = typer.Option(0.3, help="Volume weight for the mixed audio (0.0–1.0, default 0.3)"),
    codec: str = typer.Option("libx264", help="Video codec (default: libx264)"),
) -> int:
    """Mix an audio track into a video."""
    from cutagent.audio_ops import mix_audio
    try:
        result = mix_audio(
            file, audio, output,
            mix_level=mix_level,
            codec=codec,
        )
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)

@app.command("volume")
def cmd_volume(
    file: str,
    gain_db: float = typer.Option(..., help="Gain in dB (positive = louder, negative = quieter)"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    codec: str = typer.Option("copy", help="Video codec (default: copy)"),
) -> int:
    """Adjust audio volume."""
    from cutagent.audio_ops import adjust_volume
    try:
        result = adjust_volume(
            file, output,
            gain_db=gain_db,
            codec=codec,
        )
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)

@app.command("replace-audio")
def cmd_replace_audio(
    file: str,
    audio: str = typer.Option(..., help="Path to the replacement audio file"),
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    codec: str = typer.Option("copy", help="Video codec (default: copy)"),
) -> int:
    """Replace a video's audio track."""
    from cutagent.audio_ops import replace_audio
    try:
        result = replace_audio(
            file, audio, output,
            codec=codec,
        )
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)

@app.command("normalize")
def cmd_normalize(
    file: str,
    output: str = typer.Option(..., "-o", "--output", help="Output file path"),
    target_lufs: float = typer.Option(-16.0, help="Target integrated loudness in LUFS (default: -16.0)"),
    true_peak_dbtp: float = typer.Option(-1.5, help="Maximum true peak in dBTP (default: -1.5)"),
    codec: str = typer.Option("libx264", help="Video codec (default: libx264)"),
) -> int:
    """Normalize audio loudness (EBU R128)."""
    from cutagent.audio_ops import normalize_audio
    try:
        result = normalize_audio(
            file, output,
            target_lufs=target_lufs,
            true_peak_dbtp=true_peak_dbtp,
            codec=codec,
        )
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc)
