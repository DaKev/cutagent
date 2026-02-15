"""Audio operations — mix, volume, replace, normalize."""

from __future__ import annotations

from cutagent.errors import (
    CutAgentError,
    INVALID_MIX_LEVEL,
    INVALID_GAIN_VALUE,
    AUDIO_STREAM_MISSING,
    INVALID_NORMALIZE_TARGET,
    recovery_hints,
)
from cutagent.ffmpeg import run_ffmpeg
from cutagent.models import OperationResult
from cutagent.probe import probe as probe_file


def _check_audio_stream(source: str) -> None:
    """Raise if the source file has no audio stream."""
    info = probe_file(source)
    if info.audio_stream is None:
        raise CutAgentError(
            code=AUDIO_STREAM_MISSING,
            message=f"Source has no audio stream: {source}",
            recovery=recovery_hints(AUDIO_STREAM_MISSING),
            context={"source": source},
        )


# ---------------------------------------------------------------------------
# Mix audio
# ---------------------------------------------------------------------------

def mix_audio(
    source: str,
    audio: str,
    output: str,
    mix_level: float = 0.3,
    codec: str = "libx264",
) -> OperationResult:
    """Overlay an external audio track onto a video's existing audio.

    Args:
        source: Path to the source video (keeps video + original audio).
        audio: Path to the audio file to mix in (e.g., background music).
        output: Path for the output file.
        mix_level: Volume weight for the external audio (0.0–1.0).
            0.0 = silent overlay, 1.0 = equal volume to original.
        codec: Video codec for the output.

    Returns:
        OperationResult with the mixed output.
    """
    if mix_level < 0.0 or mix_level > 1.0:
        raise CutAgentError(
            code=INVALID_MIX_LEVEL,
            message=f"mix_level must be between 0.0 and 1.0, got {mix_level}",
            recovery=recovery_hints(INVALID_MIX_LEVEL),
            context={"mix_level": mix_level},
        )

    _check_audio_stream(source)
    info = probe_file(source)

    original_weight = 1.0
    args = [
        "-i", source,
        "-i", audio,
        "-filter_complex",
        (
            f"[0:a]volume={original_weight}[a0];"
            f"[1:a]volume={mix_level}[a1];"
            f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        ),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", codec,
        "-c:a", "aac",
        "-shortest",
        output,
    ]

    run_ffmpeg(args)
    return OperationResult(
        success=True, output_path=output, duration_seconds=info.duration,
    )


# ---------------------------------------------------------------------------
# Volume / gain
# ---------------------------------------------------------------------------

def adjust_volume(
    source: str,
    output: str,
    gain_db: float = 0.0,
    codec: str = "copy",
) -> OperationResult:
    """Adjust the audio volume of a media file by a dB value.

    Args:
        source: Path to the source file.
        output: Path for the output file.
        gain_db: Gain in decibels (positive = louder, negative = quieter).
        codec: Video codec. Defaults to 'copy' (video untouched).

    Returns:
        OperationResult with the adjusted output.
    """
    if gain_db < -60.0 or gain_db > 60.0:
        raise CutAgentError(
            code=INVALID_GAIN_VALUE,
            message=f"gain_db must be between -60.0 and 60.0, got {gain_db}",
            recovery=recovery_hints(INVALID_GAIN_VALUE),
            context={"gain_db": gain_db},
        )

    _check_audio_stream(source)
    info = probe_file(source)

    args = [
        "-i", source,
        "-af", f"volume={gain_db}dB",
        "-c:v", codec,
        "-c:a", "aac",
        output,
    ]

    run_ffmpeg(args)
    return OperationResult(
        success=True, output_path=output, duration_seconds=info.duration,
    )


# ---------------------------------------------------------------------------
# Replace audio
# ---------------------------------------------------------------------------

def replace_audio(
    source: str,
    audio: str,
    output: str,
    codec: str = "copy",
) -> OperationResult:
    """Replace a video's audio track with an external audio file.

    Args:
        source: Path to the source video (video stream is kept).
        audio: Path to the replacement audio file.
        output: Path for the output file.
        codec: Video codec. Defaults to 'copy' (video untouched).

    Returns:
        OperationResult with the replaced-audio output.
    """
    info = probe_file(source)

    args = [
        "-i", source,
        "-i", audio,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", codec,
        "-c:a", "aac",
        "-shortest",
        output,
    ]

    run_ffmpeg(args)
    return OperationResult(
        success=True, output_path=output, duration_seconds=info.duration,
    )


# ---------------------------------------------------------------------------
# Normalize audio (EBU R128)
# ---------------------------------------------------------------------------

def normalize_audio(
    source: str,
    output: str,
    target_lufs: float = -16.0,
    true_peak_dbtp: float = -1.5,
    codec: str = "libx264",
) -> OperationResult:
    """Normalize audio loudness using FFmpeg's loudnorm (EBU R128).

    Args:
        source: Path to the source file.
        output: Path for the output file.
        target_lufs: Target integrated loudness in LUFS (e.g., -16 for streaming).
        true_peak_dbtp: Maximum true peak in dBTP.
        codec: Video codec for the output.

    Returns:
        OperationResult with the normalized output.
    """
    if target_lufs < -70.0 or target_lufs > -5.0:
        raise CutAgentError(
            code=INVALID_NORMALIZE_TARGET,
            message=f"target_lufs must be between -70.0 and -5.0, got {target_lufs}",
            recovery=recovery_hints(INVALID_NORMALIZE_TARGET),
            context={"target_lufs": target_lufs},
        )
    if true_peak_dbtp < -10.0 or true_peak_dbtp > 0.0:
        raise CutAgentError(
            code=INVALID_NORMALIZE_TARGET,
            message=f"true_peak_dbtp must be between -10.0 and 0.0, got {true_peak_dbtp}",
            recovery=recovery_hints(INVALID_NORMALIZE_TARGET),
            context={"true_peak_dbtp": true_peak_dbtp},
        )

    _check_audio_stream(source)
    info = probe_file(source)

    loudnorm_filter = (
        f"loudnorm=I={target_lufs}:TP={true_peak_dbtp}:LRA=11"
    )

    args = [
        "-i", source,
        "-af", loudnorm_filter,
        "-c:v", codec,
        "-c:a", "aac",
        output,
    ]

    run_ffmpeg(args)
    return OperationResult(
        success=True, output_path=output, duration_seconds=info.duration,
    )
