"""Video probing and content intelligence utilities."""

from __future__ import annotations

import math
import re
from pathlib import Path

from cutagent.errors import (
    CutAgentError,
    INPUT_NOT_FOUND,
    INPUT_INVALID_FORMAT,
    recovery_hints,
)
from cutagent.ffmpeg import run_ffmpeg, run_ffprobe, run_ffprobe_json
from cutagent.models import (
    AudioLevel,
    FrameResult,
    ProbeResult,
    SceneInfo,
    SilenceInterval,
    StreamInfo,
    VideoSummary,
)


def _check_input(path: str | Path) -> Path:
    """Validate that the input file exists."""
    p = Path(path)
    if not p.exists():
        raise CutAgentError(
            code=INPUT_NOT_FOUND,
            message=f"Input file not found: {p}",
            recovery=recovery_hints(INPUT_NOT_FOUND, {"path": str(p)}),
            context={"path": str(p)},
        )
    return p


def _parse_stream(raw: dict) -> StreamInfo:
    """Parse a single stream dict from ffprobe JSON."""
    codec_type = raw.get("codec_type", "unknown")
    info = StreamInfo(
        index=raw.get("index", 0),
        codec_name=raw.get("codec_name", "unknown"),
        codec_type=codec_type,
    )
    if codec_type == "video":
        info.width = int(raw["width"]) if "width" in raw else None
        info.height = int(raw["height"]) if "height" in raw else None
        # Parse FPS from r_frame_rate (e.g. "30/1" or "30000/1001")
        rfr = raw.get("r_frame_rate", "")
        if "/" in rfr:
            num, den = rfr.split("/")
            if int(den) > 0:
                info.fps = round(int(num) / int(den), 3)
    elif codec_type == "audio":
        info.sample_rate = int(raw["sample_rate"]) if "sample_rate" in raw else None
        info.channels = int(raw["channels"]) if "channels" in raw else None

    return info


def _probe_image_size(path: str | Path) -> tuple[int | None, int | None]:
    """Probe an image file and return (width, height)."""
    data = run_ffprobe_json(path)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            width = int(stream["width"]) if "width" in stream else None
            height = int(stream["height"]) if "height" in stream else None
            return width, height
    return None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def probe(path: str | Path) -> ProbeResult:
    """Probe a media file and return structured metadata.

    Args:
        path: Path to the media file.

    Returns:
        ProbeResult with duration, format, streams, etc.
    """
    p = _check_input(path)
    data = run_ffprobe_json(p)

    fmt = data.get("format", {})
    streams_raw = data.get("streams", [])

    duration = float(fmt.get("duration", 0))
    if duration == 0:
        raise CutAgentError(
            code=INPUT_INVALID_FORMAT,
            message=f"Could not determine duration for: {p}",
            recovery=["Ensure the file is a valid media file with at least one stream"],
            context={"path": str(p)},
        )

    streams = [_parse_stream(s) for s in streams_raw]

    return ProbeResult(
        path=str(p),
        duration=duration,
        format_name=fmt.get("format_name", "unknown"),
        size_bytes=int(fmt.get("size", 0)),
        bit_rate=int(fmt.get("bit_rate", 0)),
        streams=streams,
    )


def keyframes(path: str | Path) -> list[float]:
    """Return a list of keyframe timestamps (in seconds) for a video file.

    Args:
        path: Path to the media file.

    Returns:
        Sorted list of keyframe timestamps as floats.
    """
    p = _check_input(path)

    result = run_ffprobe([
        "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "csv=print_section=0",
        str(p),
    ])

    timestamps: list[float] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and "K" in parts[1]:
            try:
                timestamps.append(float(parts[0]))
            except (ValueError, IndexError):
                continue

    return sorted(timestamps)


def extract_frames(
    path: str | Path,
    timestamps: list[float],
    output_dir: str | Path,
    image_format: str = "jpg",
    prefix: str = "frame",
) -> list[FrameResult]:
    """Extract still frames at requested timestamps.

    Args:
        path: Path to a source video.
        timestamps: Timestamp list in seconds.
        output_dir: Directory where frame files are written.
        image_format: "jpg" or "png".
        prefix: Filename prefix.

    Returns:
        A list of FrameResult objects in input order.
    """
    p = _check_input(path)
    fmt = image_format.lower().lstrip(".")
    if fmt not in ("jpg", "jpeg", "png"):
        raise ValueError("image_format must be one of: jpg, jpeg, png")

    info = probe(p)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[FrameResult] = []
    for idx, raw_ts in enumerate(timestamps):
        ts = max(0.0, min(float(raw_ts), info.duration))
        ext = "jpg" if fmt == "jpeg" else fmt
        safe_ts = f"{ts:.3f}".replace(".", "_")
        out_path = out_dir / f"{prefix}_{idx:03d}_{safe_ts}.{ext}"

        args = ["-ss", f"{ts:.6f}", "-i", str(p), "-frames:v", "1"]
        if ext == "jpg":
            args += ["-q:v", "2"]
        args.append(str(out_path))

        run_ffmpeg(args)
        width, height = _probe_image_size(out_path)
        frames.append(FrameResult(timestamp=ts, path=str(out_path), width=width, height=height))

    return frames


def thumbnail(path: str | Path, timestamp: float, output: str | Path) -> FrameResult:
    """Extract a single thumbnail image at a specific timestamp."""
    p = _check_input(path)
    info = probe(p)
    ts = max(0.0, min(float(timestamp), info.duration))
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)

    ext = out.suffix.lower()
    args = ["-ss", f"{ts:.6f}", "-i", str(p), "-frames:v", "1"]
    if ext in (".jpg", ".jpeg"):
        args += ["-q:v", "2"]
    args.append(str(out))
    run_ffmpeg(args)

    width, height = _probe_image_size(out)
    return FrameResult(timestamp=ts, path=str(out), width=width, height=height)


def detect_scenes(
    path: str | Path,
    threshold: float = 0.3,
    frame_output_dir: str | Path | None = None,
) -> list[SceneInfo]:
    """Detect scene boundaries and return scene intervals.

    Args:
        path: Path to the media file.
        threshold: Scene change threshold (0.0–1.0). Lower = more sensitive.
        frame_output_dir: Optional output directory for per-scene frame previews.

    Returns:
        List of SceneInfo objects.
    """
    p = _check_input(path)
    info = probe(p)

    # Use the select filter to detect scene changes and print timestamps
    result = run_ffmpeg([
        "-i", str(p),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-",
    ], check=False)

    # Scene timestamps appear in stderr from the showinfo filter
    timestamps: list[float] = []
    for line in result.stderr.splitlines():
        if "pts_time:" not in line:
            continue
        # Extract pts_time:VALUE from showinfo output
        for token in line.split():
            if token.startswith("pts_time:"):
                try:
                    ts = float(token.split(":")[1])
                    timestamps.append(ts)
                except (ValueError, IndexError):
                    continue

    starts: list[float] = [0.0]
    for ts in sorted(timestamps):
        if ts <= 0 or ts >= info.duration:
            continue
        if abs(ts - starts[-1]) > 1e-3:
            starts.append(ts)

    scenes: list[SceneInfo] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else info.duration
        if end <= start:
            continue
        scenes.append(SceneInfo(start=start, end=end, duration=end - start))

    if frame_output_dir and scenes:
        # Extract 3 frames per scene at 10%, 50%, 90% offsets for a filmstrip
        timestamps: list[float] = []
        scene_indices: list[int] = []
        for i, scene in enumerate(scenes):
            for pct in (0.1, 0.5, 0.9):
                timestamps.append(scene.start + scene.duration * pct)
                scene_indices.append(i)

        scene_frames = extract_frames(
            p,
            timestamps,
            frame_output_dir,
            image_format="jpg",
            prefix="scene",
        )
        for frame, scene_idx in zip(scene_frames, scene_indices):
            scenes[scene_idx].frames.append(frame.path)

    return scenes


def detect_silence(
    path: str | Path,
    threshold: float = -30.0,
    min_duration: float = 0.5,
) -> list[SilenceInterval]:
    """Detect silence intervals using FFmpeg's silencedetect filter."""
    p = _check_input(path)
    info = probe(p)

    noise = f"{float(threshold)}dB"
    result = run_ffmpeg([
        "-i", str(p),
        "-af", f"silencedetect=noise={noise}:d={float(min_duration)}",
        "-f", "null",
        "-",
    ], check=False)

    start_re = re.compile(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)")
    end_re = re.compile(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)")
    current_start: float | None = None
    intervals: list[SilenceInterval] = []

    for line in result.stderr.splitlines():
        start_match = start_re.search(line)
        if start_match:
            current_start = float(start_match.group(1))
            continue

        end_match = end_re.search(line)
        if end_match and current_start is not None:
            end = float(end_match.group(1))
            start = min(current_start, end)
            duration = max(0.0, end - start)
            intervals.append(SilenceInterval(start=start, end=end, duration=duration))
            current_start = None

    if current_start is not None:
        end = info.duration
        start = min(current_start, end)
        intervals.append(SilenceInterval(start=start, end=end, duration=max(0.0, end - start)))

    return sorted(intervals, key=lambda s: s.start)


def audio_levels(path: str | Path, interval: float = 1.0) -> list[AudioLevel]:
    """Compute audio RMS levels over fixed intervals using FFmpeg astats."""
    if interval <= 0:
        raise ValueError("interval must be > 0")

    p = _check_input(path)
    result = run_ffmpeg([
        "-loglevel", "error",
        "-i", str(p),
        "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null",
        "-",
    ], check=False)

    combined = f"{result.stdout}\n{result.stderr}"
    pts_re = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")
    level_prefix = "lavfi.astats.Overall.RMS_level="

    current_ts: float | None = None
    samples: list[tuple[float, float]] = []

    for line in combined.splitlines():
        pts_match = pts_re.search(line)
        if pts_match:
            current_ts = float(pts_match.group(1))
            continue

        if line.startswith(level_prefix):
            raw_value = line.split("=", 1)[1].strip()
            try:
                value = float(raw_value)
            except ValueError:
                continue
            if current_ts is None:
                continue
            if math.isnan(value) or math.isinf(value):
                continue
            samples.append((current_ts, value))

    buckets: dict[int, list[float]] = {}
    for ts, value in samples:
        idx = int(ts // interval)
        buckets.setdefault(idx, []).append(value)

    levels: list[AudioLevel] = []
    for idx in sorted(buckets):
        vals = buckets[idx]
        if not vals:
            continue
        levels.append(AudioLevel(
            timestamp=round(idx * interval, 3),
            rms_db=round(sum(vals) / len(vals), 3),
            sample_count=len(vals),
        ))

    return levels


def summarize(
    path: str | Path,
    frame_dir: str | Path | None = None,
    scene_threshold: float = 0.3,
    silence_threshold: float = -30.0,
    min_silence_duration: float = 0.5,
    audio_interval: float = 1.0,
    include_audio_levels: bool = False,
) -> VideoSummary:
    """Build a unified content map for a media file.

    Args:
        include_audio_levels: If True, include per-second audio levels in the
            output. Default False — per-scene avg_loudness is always computed.
    """
    info = probe(path)
    scenes = detect_scenes(path, threshold=scene_threshold, frame_output_dir=frame_dir)
    silences = detect_silence(path, threshold=silence_threshold, min_duration=min_silence_duration)
    levels = audio_levels(path, interval=audio_interval)

    for scene in scenes:
        scene_levels = [lv.rms_db for lv in levels if scene.start <= lv.timestamp < scene.end]
        if scene_levels:
            scene.avg_loudness = round(sum(scene_levels) / len(scene_levels), 3)

        silence_overlap = 0.0
        for interval in silences:
            overlap_start = max(scene.start, interval.start)
            overlap_end = min(scene.end, interval.end)
            if overlap_end > overlap_start:
                silence_overlap += overlap_end - overlap_start

        if scene.duration > 0:
            non_silent_ratio = max(0.0, 1.0 - (silence_overlap / scene.duration))
            scene.has_audio = non_silent_ratio > 0.25
        else:
            scene.has_audio = False

    silence_points = sorted({round(s.start, 3) for s in silences})
    scene_starts = {round(scene.start, 3) for scene in scenes}
    silence_bounds = {round(v, 3) for s in silences for v in (s.start, s.end)}
    suggested = sorted(scene_starts.union(silence_bounds))

    resolution: str | None = None
    if info.width and info.height:
        resolution = f"{info.width}x{info.height}"

    return VideoSummary(
        path=info.path,
        duration=info.duration,
        resolution=resolution,
        scenes=scenes,
        silences=silences,
        audio_levels=levels if include_audio_levels else [],
        silence_points=silence_points,
        suggested_cut_points=suggested,
    )


def find_nearest_keyframe(path: str | Path, target: float) -> float:
    """Find the keyframe timestamp closest to a target time.

    Args:
        path: Path to the media file.
        target: Target timestamp in seconds.

    Returns:
        The keyframe timestamp closest to the target.
    """
    kfs = keyframes(path)
    if not kfs:
        return target
    return min(kfs, key=lambda kf: abs(kf - target))
