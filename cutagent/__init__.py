"""CutAgent — Agent-first video cutting library.

Public API:
    probe, keyframes, detect_scenes, find_nearest_keyframe  — introspection
    extract_frames, thumbnail, detect_silence, audio_levels — content probes
    summarize                                                — unified content map
    trim, split, concat, reorder, extract_stream, fade, speed — operations
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
    summarize,
)
from cutagent.operations import trim, split, concat, reorder, extract_stream, fade, speed
from cutagent.engine import parse_edl, execute_edl
from cutagent.validation import validate_edl
from cutagent.errors import CutAgentError
from cutagent.models import (
    ProbeResult,
    FrameResult,
    SceneInfo,
    SilenceInterval,
    AudioLevel,
    VideoSummary,
    SpeedOp,
    OperationResult,
    EDL,
)

__version__ = "0.1.1"

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
    "summarize",
    # Operations
    "trim",
    "split",
    "concat",
    "reorder",
    "extract_stream",
    "fade",
    "speed",
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
    "VideoSummary",
    "SpeedOp",
    "OperationResult",
    "EDL",
    "CutAgentError",
]
