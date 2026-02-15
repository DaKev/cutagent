"""Shared test fixtures — generates small test videos using FFmpeg."""

import subprocess
import pytest


@pytest.fixture(scope="session")
def test_video(tmp_path_factory) -> str:
    """Generate a 5-second 640x480 test video with audio at session scope."""
    out = str(tmp_path_factory.mktemp("media") / "test.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        # Video: test pattern with frame counter, 5 seconds
        "-f", "lavfi", "-i", "testsrc=duration=5:size=640x480:rate=30",
        # Audio: sine wave, 5 seconds
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p",
        out,
    ], check=True, capture_output=True)
    return out


@pytest.fixture(scope="session")
def test_video_10s(tmp_path_factory) -> str:
    """Generate a 10-second test video for split/trim testing."""
    out = str(tmp_path_factory.mktemp("media") / "test_10s.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=10:size=640x480:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p",
        out,
    ], check=True, capture_output=True)
    return out


@pytest.fixture(scope="session")
def test_video_with_silence(tmp_path_factory) -> str:
    """Generate a 3-second test video with silence-tone-silence audio."""
    out = str(tmp_path_factory.mktemp("media") / "test_silence.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=640x480:rate=30",
        "-f", "lavfi", "-i",
        "anullsrc=r=44100:cl=mono:d=1[a0];"
        "sine=frequency=440:duration=1[a1];"
        "anullsrc=r=44100:cl=mono:d=1[a2];"
        "[a0][a1][a2]concat=n=3:v=0:a=1",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        out,
    ], check=True, capture_output=True)
    return out


@pytest.fixture
def output_dir(tmp_path) -> str:
    """Provide a temporary output directory for each test."""
    return str(tmp_path)
