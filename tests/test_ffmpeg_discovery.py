from typing import Any

"""Tests for cutagent.ffmpeg — binary discovery chain."""

import os

from cutagent.ffmpeg import (
    _try_env_dir,
    _try_env_exact,
    find_ffmpeg,
    find_ffprobe,
    reset_cache,
)


class TestEnvVarDiscovery:
    def test_env_exact_returns_none_when_unset(self) -> None:
        old = os.environ.pop("CUTAGENT_FFMPEG", None)
        try:
            assert _try_env_exact("CUTAGENT_FFMPEG") is None
        finally:
            if old is not None:
                os.environ["CUTAGENT_FFMPEG"] = old

    def test_env_exact_returns_path_when_valid(self, tmp_path: Any) -> None:
        fake_bin = tmp_path / "ffmpeg"
        fake_bin.write_text("#!/bin/sh\n")
        os.environ["CUTAGENT_FFMPEG"] = str(fake_bin)
        try:
            assert _try_env_exact("CUTAGENT_FFMPEG") == str(fake_bin)
        finally:
            del os.environ["CUTAGENT_FFMPEG"]

    def test_env_dir_returns_none_when_unset(self) -> None:
        old = os.environ.pop("CUTAGENT_FFMPEG_DIR", None)
        try:
            assert _try_env_dir("ffmpeg") is None
        finally:
            if old is not None:
                os.environ["CUTAGENT_FFMPEG_DIR"] = old

    def test_env_dir_finds_binary(self, tmp_path: Any) -> None:
        fake_bin = tmp_path / "ffprobe"
        fake_bin.write_text("#!/bin/sh\n")
        os.environ["CUTAGENT_FFMPEG_DIR"] = str(tmp_path)
        try:
            assert _try_env_dir("ffprobe") == str(fake_bin)
        finally:
            del os.environ["CUTAGENT_FFMPEG_DIR"]


class TestCaching:
    def test_cache_returns_same_path(self) -> None:
        reset_cache()
        path1 = find_ffmpeg()
        path2 = find_ffmpeg()
        assert path1 == path2

    def test_reset_cache_clears(self) -> None:
        find_ffmpeg()
        reset_cache()
        # After reset, next call rediscovers (should still find it)
        path = find_ffmpeg()
        assert path


class TestFindBinaries:
    def test_find_ffmpeg_returns_string(self) -> None:
        reset_cache()
        path = find_ffmpeg()
        assert isinstance(path, str)
        assert "ffmpeg" in path.lower()

    def test_find_ffprobe_returns_string(self) -> None:
        reset_cache()
        path = find_ffprobe()
        assert isinstance(path, str)
        assert "ffprobe" in path.lower()
