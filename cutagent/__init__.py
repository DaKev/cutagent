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

from cutagent.probe import (
    probe,
    keyframes,
    detect_scenes,
    find_nearest_keyframe,
    extract_frames,
    thumbnail,
    detect_silence,
    audio_levels,
    detect_beats,
    summarize,
)
from cutagent.operations import trim, split, concat, reorder, extract_stream, fade, speed
from cutagent.audio_ops import mix_audio, adjust_volume, replace_audio, normalize_audio
from cutagent.text_ops import add_text
from cutagent.animation_ops import animate
from cutagent.engine import parse_edl, execute_edl
from cutagent.validation import validate_edl
from cutagent.errors import CutAgentError
from cutagent.models import (
    ProbeResult,
    FrameResult,
    SceneInfo,
    SilenceInterval,
    AudioLevel,
    BeatInfo,
    VideoSummary,
    SpeedOp,
    MixAudioOp,
    VolumeOp,
    ReplaceAudioOp,
    NormalizeOp,
    TextOp,
    TextEntry,
    AnimateOp,
    AnimationLayer,
    AnimationProperty,
    AnimationKeyframe,
    OperationResult,
    EDL,
)

__version__ = "0.2.0"

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
