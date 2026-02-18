"""Data models for CutAgent — all JSON-serializable via to_dict / from_dict."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Time parsing helper
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(
    r"^(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.(\d+))?$"
)


def parse_time(value: str) -> float:
    """Parse HH:MM:SS.ms or plain seconds into a float of seconds."""
    try:
        return float(value)
    except ValueError:
        pass
    m = _TIME_RE.match(value)
    if not m:
        raise ValueError(f"Invalid time format: {value!r} — use HH:MM:SS, MM:SS, or seconds")
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    frac = float(f"0.{m.group(4)}") if m.group(4) else 0.0
    return hours * 3600 + minutes * 60 + seconds + frac


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ---------------------------------------------------------------------------
# Probe result
# ---------------------------------------------------------------------------

@dataclass
class StreamInfo:
    """Metadata for a single stream (audio or video)."""
    index: int
    codec_name: str
    codec_type: str  # "video" or "audio"
    # Video-specific
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    # Audio-specific
    sample_rate: Optional[int] = None
    channels: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> StreamInfo:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProbeResult:
    """Full probe output for a media file."""
    path: str
    duration: float
    format_name: str
    size_bytes: int
    bit_rate: int
    streams: list[StreamInfo] = field(default_factory=list)

    @property
    def video_stream(self) -> Optional[StreamInfo]:
        return next((s for s in self.streams if s.codec_type == "video"), None)

    @property
    def audio_stream(self) -> Optional[StreamInfo]:
        return next((s for s in self.streams if s.codec_type == "audio"), None)

    @property
    def width(self) -> Optional[int]:
        v = self.video_stream
        return v.width if v else None

    @property
    def height(self) -> Optional[int]:
        v = self.video_stream
        return v.height if v else None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "duration": self.duration,
            "duration_formatted": format_time(self.duration),
            "format_name": self.format_name,
            "size_bytes": self.size_bytes,
            "bit_rate": self.bit_rate,
            "width": self.width,
            "height": self.height,
            "streams": [s.to_dict() for s in self.streams],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProbeResult:
        streams = [StreamInfo.from_dict(s) for s in data.get("streams", [])]
        return cls(
            path=data["path"],
            duration=data["duration"],
            format_name=data["format_name"],
            size_bytes=data["size_bytes"],
            bit_rate=data["bit_rate"],
            streams=streams,
        )


# ---------------------------------------------------------------------------
# Content intelligence models
# ---------------------------------------------------------------------------

@dataclass
class FrameResult:
    """A single extracted frame from a video."""
    timestamp: float
    path: str
    width: Optional[int] = None
    height: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> FrameResult:
        return cls(
            timestamp=float(data["timestamp"]),
            path=data["path"],
            width=data.get("width"),
            height=data.get("height"),
        )


@dataclass
class SceneInfo:
    """A contiguous scene interval with optional representative frames."""
    start: float
    end: float
    duration: float
    frames: list[str] = field(default_factory=list)
    has_audio: Optional[bool] = None
    avg_loudness: Optional[float] = None

    def to_dict(self) -> dict:
        d: dict = {
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
        }
        if self.frames:
            d["frames"] = self.frames
        if self.has_audio is not None:
            d["has_audio"] = self.has_audio
        if self.avg_loudness is not None:
            d["avg_loudness"] = self.avg_loudness
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SceneInfo:
        return cls(
            start=float(data["start"]),
            end=float(data["end"]),
            duration=float(data["duration"]),
            frames=data.get("frames", []),
            has_audio=data.get("has_audio"),
            avg_loudness=data.get("avg_loudness"),
        )


@dataclass
class SilenceInterval:
    """Detected silence interval in an audio track."""
    start: float
    end: float
    duration: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SilenceInterval:
        return cls(
            start=float(data["start"]),
            end=float(data["end"]),
            duration=float(data["duration"]),
        )


@dataclass
class AudioLevel:
    """Audio level summary for a fixed timeline interval."""
    timestamp: float
    rms_db: float
    sample_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AudioLevel:
        return cls(
            timestamp=float(data["timestamp"]),
            rms_db=float(data["rms_db"]),
            sample_count=int(data.get("sample_count", 0)),
        )


@dataclass
class BeatInfo:
    """A detected musical beat/onset in an audio track."""
    timestamp: float
    strength: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BeatInfo:
        return cls(
            timestamp=float(data["timestamp"]),
            strength=float(data["strength"]),
        )


@dataclass
class VideoSummary:
    """Unified, agent-friendly map of content and suggested cut points."""
    path: str
    duration: float
    resolution: Optional[str]
    scenes: list[SceneInfo] = field(default_factory=list)
    silences: list[SilenceInterval] = field(default_factory=list)
    audio_levels: list[AudioLevel] = field(default_factory=list)
    silence_points: list[float] = field(default_factory=list)
    suggested_cut_points: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "duration": self.duration,
            "duration_formatted": format_time(self.duration),
            "resolution": self.resolution,
            "scenes": [scene.to_dict() for scene in self.scenes],
            "silences": [interval.to_dict() for interval in self.silences],
            "audio_levels": [level.to_dict() for level in self.audio_levels],
            "silence_points": self.silence_points,
            "suggested_cut_points": self.suggested_cut_points,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VideoSummary:
        return cls(
            path=data["path"],
            duration=float(data["duration"]),
            resolution=data.get("resolution"),
            scenes=[SceneInfo.from_dict(s) for s in data.get("scenes", [])],
            silences=[SilenceInterval.from_dict(s) for s in data.get("silences", [])],
            audio_levels=[AudioLevel.from_dict(a) for a in data.get("audio_levels", [])],
            silence_points=[float(v) for v in data.get("silence_points", [])],
            suggested_cut_points=[float(v) for v in data.get("suggested_cut_points", [])],
        )


# ---------------------------------------------------------------------------
# Operation types
# ---------------------------------------------------------------------------

@dataclass
class TrimOp:
    source: str
    start: str
    end: str
    op: str = "trim"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TrimOp:
        return cls(source=data["source"], start=data["start"], end=data["end"])


@dataclass
class SplitOp:
    source: str
    points: list[str]
    op: str = "split"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SplitOp:
        return cls(source=data["source"], points=data["points"])


@dataclass
class ConcatOp:
    segments: list[str]
    transition: Optional[str] = None
    transition_duration: Optional[float] = None
    op: str = "concat"

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> ConcatOp:
        return cls(
            segments=data["segments"],
            transition=data.get("transition"),
            transition_duration=data.get("transition_duration"),
        )


@dataclass
class ReorderOp:
    segments: list[str]
    order: list[int]
    op: str = "reorder"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ReorderOp:
        return cls(segments=data["segments"], order=data["order"])


@dataclass
class ExtractOp:
    source: str
    stream: str  # "audio" or "video"
    op: str = "extract"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ExtractOp:
        return cls(source=data["source"], stream=data["stream"])


@dataclass
class FadeOp:
    source: str
    output: Optional[str] = None
    fade_in: float = 0.0
    fade_out: float = 0.0
    op: str = "fade"

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> FadeOp:
        return cls(
            source=data["source"],
            output=data.get("output"),
            fade_in=float(data.get("fade_in", 0.0)),
            fade_out=float(data.get("fade_out", 0.0)),
        )


@dataclass
class SpeedOp:
    source: str
    factor: float = 1.0
    op: str = "speed"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SpeedOp:
        return cls(
            source=data["source"],
            factor=float(data.get("factor", 1.0)),
        )


@dataclass
class MixAudioOp:
    """Mix an external audio track into a video's existing audio."""
    source: str
    audio: str
    mix_level: float = 0.3
    op: str = "mix_audio"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MixAudioOp:
        return cls(
            source=data["source"],
            audio=data["audio"],
            mix_level=float(data.get("mix_level", 0.3)),
        )


@dataclass
class VolumeOp:
    """Adjust audio volume by a gain value in dB."""
    source: str
    gain_db: float = 0.0
    op: str = "volume"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> VolumeOp:
        return cls(
            source=data["source"],
            gain_db=float(data.get("gain_db", 0.0)),
        )


@dataclass
class ReplaceAudioOp:
    """Replace a video's audio track with an external audio file."""
    source: str
    audio: str
    op: str = "replace_audio"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ReplaceAudioOp:
        return cls(
            source=data["source"],
            audio=data["audio"],
        )


@dataclass
class NormalizeOp:
    """Normalize audio loudness using EBU R128 loudnorm."""
    source: str
    target_lufs: float = -16.0
    true_peak_dbtp: float = -1.5
    op: str = "normalize"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NormalizeOp:
        return cls(
            source=data["source"],
            target_lufs=float(data.get("target_lufs", -16.0)),
            true_peak_dbtp=float(data.get("true_peak_dbtp", -1.5)),
        )


# ---------------------------------------------------------------------------
# Text overlay
# ---------------------------------------------------------------------------

# Valid position presets for text placement
TEXT_POSITIONS = {
    "center", "top-center", "bottom-center",
    "top-left", "top-right", "bottom-left", "bottom-right",
}


@dataclass
class TextEntry:
    """A single text overlay entry with position, timing, and styling."""
    text: str
    position: str = "center"
    font_size: int = 48
    font_color: str = "white"
    start: Optional[str] = None
    end: Optional[str] = None
    bg_color: Optional[str] = None
    bg_padding: int = 10
    font: Optional[str] = None
    shadow_color: Optional[str] = None
    shadow_offset: int = 0
    stroke_color: Optional[str] = None
    stroke_width: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> TextEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TextOp:
    """Burn one or more text overlays onto a video."""
    source: str
    entries: list[TextEntry] = field(default_factory=list)
    op: str = "text"

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "source": self.source,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict) -> TextOp:
        entries = [TextEntry.from_dict(e) for e in data.get("entries", [])]
        return cls(source=data["source"], entries=entries)


# ---------------------------------------------------------------------------
# Animation types
# ---------------------------------------------------------------------------

ANIMATION_EASINGS = {"linear", "ease-in", "ease-out", "ease-in-out", "spring"}
ANIMATION_LAYER_TYPES = {"text", "image"}
TEXT_ANIMATABLE_PROPS = {"x", "y", "opacity", "font_size"}
IMAGE_ANIMATABLE_PROPS = {"x", "y", "opacity", "scale"}


@dataclass
class AnimationKeyframe:
    """A single keyframe: time + value."""
    t: float
    value: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AnimationKeyframe:
        return cls(t=float(data["t"]), value=float(data["value"]))


@dataclass
class AnimationProperty:
    """An animated property with keyframes and easing."""
    keyframes: list[AnimationKeyframe]
    easing: str = "linear"

    def to_dict(self) -> dict:
        return {
            "keyframes": [kf.to_dict() for kf in self.keyframes],
            "easing": self.easing,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AnimationProperty:
        kfs = [AnimationKeyframe.from_dict(kf) for kf in data["keyframes"]]
        return cls(keyframes=kfs, easing=data.get("easing", "linear"))


@dataclass
class AnimationLayer:
    """A single animation layer (text or image) with animated properties."""
    type: str  # "text" or "image"
    start: float = 0.0
    end: float = 5.0
    properties: dict[str, AnimationProperty] = field(default_factory=dict)
    # Text-specific fields
    text: Optional[str] = None
    font_size: int = 48
    font_color: str = "white"
    font: Optional[str] = None
    bg_color: Optional[str] = None
    bg_padding: int = 10
    shadow_color: Optional[str] = None
    shadow_offset: int = 0
    stroke_color: Optional[str] = None
    stroke_width: int = 0
    # Image-specific fields
    path: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "type": self.type,
            "start": self.start,
            "end": self.end,
            "properties": {k: v.to_dict() for k, v in self.properties.items()},
        }
        if self.type == "text":
            d["text"] = self.text
            d["font_size"] = self.font_size
            d["font_color"] = self.font_color
            if self.font:
                d["font"] = self.font
            if self.bg_color:
                d["bg_color"] = self.bg_color
                d["bg_padding"] = self.bg_padding
            if self.shadow_color:
                d["shadow_color"] = self.shadow_color
                d["shadow_offset"] = self.shadow_offset
            if self.stroke_color:
                d["stroke_color"] = self.stroke_color
                d["stroke_width"] = self.stroke_width
        elif self.type == "image":
            d["path"] = self.path
        return d

    @classmethod
    def from_dict(cls, data: dict) -> AnimationLayer:
        props = {
            k: AnimationProperty.from_dict(v)
            for k, v in data.get("properties", {}).items()
        }
        return cls(
            type=data["type"],
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 5.0)),
            properties=props,
            text=data.get("text"),
            font_size=int(data.get("font_size", 48)),
            font_color=data.get("font_color", "white"),
            font=data.get("font"),
            bg_color=data.get("bg_color"),
            bg_padding=int(data.get("bg_padding", 10)),
            shadow_color=data.get("shadow_color"),
            shadow_offset=int(data.get("shadow_offset", 0)),
            stroke_color=data.get("stroke_color"),
            stroke_width=int(data.get("stroke_width", 0)),
            path=data.get("path"),
        )


@dataclass
class AnimateOp:
    """Apply keyframe-driven animations (text/image layers) onto a video."""
    source: str
    layers: list[AnimationLayer] = field(default_factory=list)
    fps: int = 30
    op: str = "animate"

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "source": self.source,
            "fps": self.fps,
            "layers": [layer.to_dict() for layer in self.layers],
        }

    @classmethod
    def from_dict(cls, data: dict) -> AnimateOp:
        layers = [AnimationLayer.from_dict(l) for l in data.get("layers", [])]
        return cls(
            source=data["source"],
            layers=layers,
            fps=int(data.get("fps", 30)),
        )


# Registry for parsing operation dicts into typed objects
OPERATION_TYPES: dict[str, type] = {
    "trim": TrimOp,
    "split": SplitOp,
    "concat": ConcatOp,
    "reorder": ReorderOp,
    "extract": ExtractOp,
    "fade": FadeOp,
    "speed": SpeedOp,
    "mix_audio": MixAudioOp,
    "volume": VolumeOp,
    "replace_audio": ReplaceAudioOp,
    "normalize": NormalizeOp,
    "text": TextOp,
    "animate": AnimateOp,
}


def parse_operation(data: dict):
    """Parse a raw operation dict into a typed operation dataclass.

    Raises:
        CutAgentError: If the operation type is unknown or required fields are missing.
    """
    from cutagent.errors import CutAgentError, UNKNOWN_OPERATION, MISSING_FIELD, recovery_hints

    op_type = data.get("op")
    if op_type not in OPERATION_TYPES:
        raise CutAgentError(
            code=UNKNOWN_OPERATION,
            message=f"Unknown operation type: {op_type!r}",
            recovery=recovery_hints(UNKNOWN_OPERATION),
            context={"operation": op_type, "supported": list(OPERATION_TYPES.keys())},
        )
    try:
        return OPERATION_TYPES[op_type].from_dict(data)
    except KeyError as exc:
        raise CutAgentError(
            code=MISSING_FIELD,
            message=f"Operation '{op_type}' missing required field: {exc}",
            recovery=[
                f"Check the '{op_type}' operation schema in 'cutagent capabilities'",
                "Run 'cutagent capabilities' to see required fields for each operation",
            ],
            context={"operation": op_type, "missing_field": str(exc).strip("'")},
        ) from exc


# ---------------------------------------------------------------------------
# EDL (Edit Decision List)
# ---------------------------------------------------------------------------

@dataclass
class OutputSpec:
    path: str
    codec: str = "copy"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> OutputSpec:
        return cls(path=data["path"], codec=data.get("codec", "copy"))


@dataclass
class EDL:
    """Edit Decision List — the top-level declarative edit format."""
    version: str
    inputs: list[str]
    operations: list  # list of typed operation dataclasses
    output: OutputSpec

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "inputs": self.inputs,
            "operations": [op.to_dict() for op in self.operations],
            "output": self.output.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> EDL:
        ops = [parse_operation(op) for op in data["operations"]]
        return cls(
            version=data["version"],
            inputs=data["inputs"],
            operations=ops,
            output=OutputSpec.from_dict(data["output"]),
        )


# ---------------------------------------------------------------------------
# Operation result
# ---------------------------------------------------------------------------

@dataclass
class OperationResult:
    """Result of a single operation or full EDL execution."""
    success: bool
    output_path: str
    duration_seconds: Optional[float] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {
            "success": self.success,
            "output_path": self.output_path,
        }
        if self.duration_seconds is not None:
            d["duration_seconds"] = self.duration_seconds
            d["duration_formatted"] = format_time(self.duration_seconds)
        if self.warnings:
            d["warnings"] = self.warnings
        return d
