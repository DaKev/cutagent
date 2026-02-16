"""Tests for cutagent.doctor — diagnostic checks."""

from cutagent.doctor import run_doctor


class TestDoctor:
    def test_returns_structured_report(self):
        result = run_doctor()
        assert "healthy" in result
        assert "checks" in result
        assert isinstance(result["checks"], list)

    def test_check_names_present(self):
        result = run_doctor()
        names = [c["name"] for c in result["checks"]]
        assert "ffmpeg" in names
        assert "ffprobe" in names
        assert "versions_match" in names
        assert "temp_directory" in names
        assert "env_vars" in names

    def test_each_check_has_ok_and_detail(self):
        result = run_doctor()
        for check in result["checks"]:
            assert "name" in check
            assert "ok" in check
            assert "detail" in check

    def test_temp_directory_is_writable(self):
        result = run_doctor()
        temp_check = next(c for c in result["checks"] if c["name"] == "temp_directory")
        assert temp_check["ok"] is True
        assert temp_check["detail"]["writable"] is True

    def test_healthy_when_ffmpeg_available(self):
        """If ffmpeg and ffprobe are found, healthy should be True."""
        result = run_doctor()
        ffmpeg_ok = next(c for c in result["checks"] if c["name"] == "ffmpeg")["ok"]
        ffprobe_ok = next(c for c in result["checks"] if c["name"] == "ffprobe")["ok"]
        if ffmpeg_ok and ffprobe_ok:
            assert result["healthy"] is True
