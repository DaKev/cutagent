"""Tests for cutagent.probe.detect_beats — musical beat detection."""

from cutagent.probe import detect_beats
from cutagent.models import BeatInfo


class TestDetectBeats:
    def test_beats_returns_dict(self, test_video):
        result = detect_beats(test_video)
        assert isinstance(result, dict)
        assert "beats" in result
        assert "count" in result
        assert "bpm" in result

    def test_beats_from_rhythmic_video(self, test_video_with_beats):
        result = detect_beats(
            test_video_with_beats,
            energy_threshold=1.1,
            window_size=4,
        )
        assert result["count"] > 0
        for beat in result["beats"]:
            assert isinstance(beat, BeatInfo)
            assert beat.timestamp >= 0.0
            assert beat.strength > 0.0

    def test_beats_bpm_estimate(self, test_video_with_beats):
        result = detect_beats(test_video_with_beats, energy_threshold=1.3)
        if result["count"] >= 2:
            assert result["bpm"] is not None
            assert result["bpm"] > 0

    def test_beats_min_interval(self, test_video_with_beats):
        result = detect_beats(
            test_video_with_beats,
            min_interval=1.0,
            energy_threshold=1.3,
        )
        if result["count"] >= 2:
            beats = result["beats"]
            for i in range(1, len(beats)):
                gap = beats[i].timestamp - beats[i - 1].timestamp
                assert gap >= 0.99  # small tolerance for float precision

    def test_beats_high_threshold_fewer_results(self, test_video_with_beats):
        low_thresh = detect_beats(test_video_with_beats, energy_threshold=1.2)
        high_thresh = detect_beats(test_video_with_beats, energy_threshold=3.0)
        assert high_thresh["count"] <= low_thresh["count"]

    def test_beat_info_serialization(self):
        beat = BeatInfo(timestamp=1.5, strength=2.1)
        d = beat.to_dict()
        assert d["timestamp"] == 1.5
        assert d["strength"] == 2.1
        restored = BeatInfo.from_dict(d)
        assert restored.timestamp == beat.timestamp
        assert restored.strength == beat.strength
