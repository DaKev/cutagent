"""Integration tests for the screen recording post-processing pipeline.

Simulates a typical screen recording (video with periods of silence) and
validates the full CutAgent pipeline:

    probe → detect_silence → trim content → normalize → verify output

No actual screen capture is performed — a synthetic video is generated with
FFmpeg's lavfi source to replicate a recording that starts and ends with
silence (e.g. pre-/post-session dead air).
"""

from __future__ import annotations

import subprocess

import pytest

from cutagent import (
    detect_silence,
    execute_edl,
    normalize_audio,
    probe,
    trim,
)
from cutagent.models import format_time


@pytest.fixture(scope="module")
def screen_recording(tmp_path_factory) -> str:
    """Generate a synthetic 10-second 1280×720 screen recording.

    Audio pattern: 2s silence → 6s tone (content) → 2s silence.
    This mirrors a recording where the agent started/stopped slightly
    before/after the actual content.
    """
    out = str(tmp_path_factory.mktemp("recordings") / "screen.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=10:size=1280x720:rate=30",
            "-f", "lavfi", "-i",
            (
                "anullsrc=r=44100:cl=stereo:d=2[s0];"
                "sine=frequency=440:duration=6[t0];"
                "anullsrc=r=44100:cl=stereo:d=2[s1];"
                "[s0][t0][s1]concat=n=3:v=0:a=1"
            ),
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out,
        ],
        check=True,
        capture_output=True,
    )
    return out


class TestScreenRecordingPipeline:
    def test_probe_returns_expected_metadata(self, screen_recording):
        """A freshly-recorded file is probed as valid 1280×720 media."""
        info = probe(screen_recording)
        assert info.duration == pytest.approx(10.0, abs=0.5)
        assert info.width == 1280
        assert info.height == 720
        assert info.video_stream is not None
        assert info.audio_stream is not None

    def test_silence_detection_finds_intro_and_outro(self, screen_recording):
        """Silence detection identifies the intro and outro dead-air segments."""
        silences = detect_silence(screen_recording, threshold=-35.0, min_duration=0.5)
        assert len(silences) >= 2
        # Intro silence starts at the very beginning
        assert silences[0].start == pytest.approx(0.0, abs=0.3)
        # Outro silence ends near the recording end
        assert silences[-1].end == pytest.approx(10.0, abs=0.5)

    def test_trim_to_content_is_shorter(self, screen_recording, tmp_path):
        """Trimming out intro/outro silence produces a shorter clip."""
        silences = detect_silence(screen_recording, threshold=-35.0, min_duration=0.5)
        assert len(silences) >= 2

        content_start = format_time(silences[0].end)
        content_end = format_time(silences[-1].start)
        out = str(tmp_path / "content.mp4")

        result = trim(screen_recording, start=content_start, end=content_end, output=out)

        assert result.success
        trimmed = probe(out)
        assert trimmed.duration < probe(screen_recording).duration

    def test_full_edl_trim_and_normalize(self, screen_recording, tmp_path):
        """Full EDL pipeline: trim dead air, then normalize audio loudness."""
        silences = detect_silence(screen_recording, threshold=-35.0, min_duration=0.5)
        assert len(silences) >= 2

        content_start = format_time(silences[0].end)
        content_end = format_time(silences[-1].start)
        out = str(tmp_path / "final.mp4")

        edl = {
            "version": "1.0",
            "inputs": [screen_recording],
            "operations": [
                {
                    "op": "trim",
                    "source": "$input.0",
                    "start": content_start,
                    "end": content_end,
                },
                {
                    "op": "normalize",
                    "source": "$0",
                    "target_lufs": -16.0,
                },
            ],
            "output": {"path": out, "codec": "libx264"},
        }

        result = execute_edl(edl)

        assert result.success
        final = probe(out)
        assert final.duration > 0
        assert final.duration < probe(screen_recording).duration

    def test_normalize_standalone(self, screen_recording, tmp_path):
        """normalize_audio produces a valid output file."""
        out = str(tmp_path / "normalized.mp4")
        result = normalize_audio(screen_recording, output=out, target_lufs=-16.0)
        assert result.success
        assert probe(out).duration == pytest.approx(
            probe(screen_recording).duration, abs=0.5
        )
