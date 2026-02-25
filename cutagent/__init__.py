"""CutAgent — Agent-first video cutting library.

Public API:
    probe, keyframes, detect_scenes, find_nearest_keyframe  — introspection
    extract_frames, thumbnail, detect_silence, audio_levels — content probes
    detect_beats                                            — music beat detection
    summarize                                                — unified content map
    trim, split, concat, reorder, extract_stream, fade, speed — video operations
    mix_audio, adjust_volume, replace_audio, normalize_audio  — audio operations
    add_text                                                 — text overlay operations
    animate                                                  — keyframe-driven animations
    parse_edl, execute_edl                                  — EDL engine
    validate_edl                                            — dry-run validation
    CutAgentError                                           — structured errors
"""

from cutagent.animation_ops import animate
from cutagent.audio_ops import adjust_volume, mix_audio, normalize_audio, replace_audio
from cutagent.engine import execute_edl, parse_edl
from cutagent.errors import CutAgentError
from cutagent.models import (
    EDL,
    AnimateOp,
    AnimationKeyframe,
    AnimationLayer,
    AnimationProperty,
    AudioLevel,
    BeatInfo,
    FrameResult,
    MixAudioOp,
    NormalizeOp,
    OperationResult,
    ProbeResult,
    ReplaceAudioOp,
    SceneInfo,
    SilenceInterval,
    SpeedOp,
    TextEntry,
    TextOp,
    VideoSummary,
    VolumeOp,
)
from cutagent.operations import concat, extract_stream, fade, reorder, speed, split, trim
from cutagent.probe import (
    audio_levels,
    detect_beats,
    detect_scenes,
    detect_silence,
    extract_frames,
    find_nearest_keyframe,
    keyframes,
    probe,
    summarize,
    thumbnail,
)
from cutagent.text_ops import add_text
from cutagent.validation import validate_edl

__version__ = "0.3.0"

__all__ = [
    # Introspection
    "probe",
    "keyframes",
    "detect_scenes",
    "find_nearest_keyframe",
    "extract_frames",
    "thumbnail",
    "detect_silence",
    "audio_levels",
    "detect_beats",
    "summarize",
    # Video operations
    "trim",
    "split",
    "concat",
    "reorder",
    "extract_stream",
    "fade",
    "speed",
    # Audio operations
    "mix_audio",
    "adjust_volume",
    "replace_audio",
    "normalize_audio",
    # Text operations
    "add_text",
    # Animation operations
    "animate",
    # EDL engine
    "parse_edl",
    "execute_edl",
    # Validation
    "validate_edl",
    # Types
    "ProbeResult",
    "FrameResult",
    "SceneInfo",
    "SilenceInterval",
    "AudioLevel",
    "BeatInfo",
    "VideoSummary",
    "SpeedOp",
    "MixAudioOp",
    "VolumeOp",
    "ReplaceAudioOp",
    "NormalizeOp",
    "TextOp",
    "TextEntry",
    "AnimateOp",
    "AnimationLayer",
    "AnimationProperty",
    "AnimationKeyframe",
    "OperationResult",
    "EDL",
    "CutAgentError",
]
