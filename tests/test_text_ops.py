"""Tests for cutagent.text_ops — text overlay, descriptions, and annotations."""

import json
import os
import subprocess

import pytest
from cutagent.text_ops import add_text
from cutagent.models import TextEntry
from cutagent.errors import CutAgentError
from cutagent.validation import validate_edl


# ---------------------------------------------------------------------------
# Drawtext availability check
# ---------------------------------------------------------------------------

def _ffmpeg_has_drawtext(ffmpeg_bin: str = "ffmpeg") -> bool:
    """Check if the given FFmpeg binary supports the drawtext filter."""
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-filters"],
            capture_output=True, text=True, timeout=10,
        )
        return "drawtext" in result.stdout
    except Exception:
        return False


def _find_drawtext_ffmpeg() -> str | None:
    """Find an FFmpeg binary with drawtext support (system or static-ffmpeg)."""
    import shutil
    system = shutil.which("ffmpeg")
    if system and _ffmpeg_has_drawtext(system):
        return system
    try:
        from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise
        ffmpeg_path, _ = get_or_fetch_platform_executables_else_raise()
        if _ffmpeg_has_drawtext(ffmpeg_path):
            return ffmpeg_path
    except Exception:
        pass
    return None


_drawtext_ffmpeg = _find_drawtext_ffmpeg()
requires_drawtext = pytest.mark.skipif(
    _drawtext_ffmpeg is None,
    reason="FFmpeg with drawtext filter not available (install static-ffmpeg or rebuild FFmpeg with --enable-libfreetype)",
)


@pytest.fixture(autouse=True)
def _use_drawtext_ffmpeg():
    """Ensure cutagent uses an FFmpeg binary that has the drawtext filter."""
    if _drawtext_ffmpeg is None:
        yield
        return
    from cutagent.ffmpeg import reset_cache
    old = os.environ.get("CUTAGENT_FFMPEG")
    os.environ["CUTAGENT_FFMPEG"] = _drawtext_ffmpeg
    reset_cache()
    yield
    reset_cache()
    if old is None:
        os.environ.pop("CUTAGENT_FFMPEG", None)
    else:
        os.environ["CUTAGENT_FFMPEG"] = old


# ---------------------------------------------------------------------------
# Direct API tests
# ---------------------------------------------------------------------------

@requires_drawtext
class TestAddTextBasic:
    def test_single_centered_text(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_center.mp4")
        entries = [TextEntry(text="Hello World")]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)
        assert result.duration_seconds is not None

    def test_text_with_custom_font_size(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_large.mp4")
        entries = [TextEntry(text="Big Title", font_size=72, font_color="yellow")]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)

    def test_text_with_background(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_bg.mp4")
        entries = [TextEntry(
            text="With Background",
            bg_color="black@0.5",
            bg_padding=12,
        )]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)

    def test_text_with_timing(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_timed.mp4")
        entries = [TextEntry(text="Timed Text", start="0", end="2")]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)


@requires_drawtext
class TestAddTextPositions:
    @pytest.mark.parametrize("position", [
        "center", "top-center", "bottom-center",
        "top-left", "top-right", "bottom-left", "bottom-right",
    ])
    def test_position_presets(self, test_video, output_dir, position):
        out = os.path.join(output_dir, f"text_{position}.mp4")
        entries = [TextEntry(text=f"At {position}", position=position)]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)

    def test_custom_xy_position(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_custom_pos.mp4")
        entries = [TextEntry(text="Custom XY", position="100,200")]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)


@requires_drawtext
class TestAddTextMultipleEntries:
    def test_two_entries(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_multi.mp4")
        entries = [
            TextEntry(text="Title", position="top-center", font_size=72),
            TextEntry(text="Subtitle", position="bottom-center", font_size=36),
        ]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)

    def test_timed_entries(self, test_video, output_dir):
        out = os.path.join(output_dir, "text_multi_timed.mp4")
        entries = [
            TextEntry(text="First", start="0", end="2"),
            TextEntry(text="Second", start="2", end="4"),
        ]
        result = add_text(test_video, entries, out)
        assert result.success
        assert os.path.exists(out)


@requires_drawtext
class TestAddTextErrors:
    def test_empty_entries(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        with pytest.raises(CutAgentError) as exc_info:
            add_text(test_video, [], out)
        assert exc_info.value.code == "EMPTY_TEXT_ENTRIES"

    def test_invalid_font_size(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        entries = [TextEntry(text="Bad", font_size=0)]
        with pytest.raises(CutAgentError) as exc_info:
            add_text(test_video, entries, out)
        assert exc_info.value.code == "INVALID_FONT_SIZE"

    def test_negative_font_size(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        entries = [TextEntry(text="Bad", font_size=-10)]
        with pytest.raises(CutAgentError) as exc_info:
            add_text(test_video, entries, out)
        assert exc_info.value.code == "INVALID_FONT_SIZE"

    def test_invalid_position(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        entries = [TextEntry(text="Bad", position="nowhere")]
        with pytest.raises(CutAgentError) as exc_info:
            add_text(test_video, entries, out)
        assert exc_info.value.code == "INVALID_TEXT_POSITION"

    def test_invalid_timing_start_after_end(self, test_video, output_dir):
        out = os.path.join(output_dir, "bad.mp4")
        entries = [TextEntry(text="Bad", start="5", end="2")]
        with pytest.raises(CutAgentError) as exc_info:
            add_text(test_video, entries, out)
        assert exc_info.value.code == "INVALID_TEXT_TIMING"


# ---------------------------------------------------------------------------
# EDL integration tests
# ---------------------------------------------------------------------------

@requires_drawtext
class TestTextEDLIntegration:
    def test_text_in_edl(self, test_video, output_dir):
        """Text operation works in a multi-step EDL."""
        from cutagent.engine import execute_edl
        out = os.path.join(output_dir, "edl_text.mp4")
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
                {
                    "op": "text", "source": "$0",
                    "entries": [{"text": "EDL Title", "position": "center"}],
                },
            ],
            "output": {"path": out, "codec": "libx264"},
        }
        result = execute_edl(edl)
        assert result.success
        assert os.path.exists(out)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestTextValidation:
    def test_valid_text_edl(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {
                    "op": "text", "source": "$input.0",
                    "entries": [{"text": "Valid", "position": "center"}],
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid

    def test_validate_empty_entries(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "text", "source": "$input.0", "entries": []},
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "EMPTY_TEXT_ENTRIES" in codes

    def test_validate_invalid_position(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {
                    "op": "text", "source": "$input.0",
                    "entries": [{"text": "Bad", "position": "invalid-spot"}],
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_TEXT_POSITION" in codes

    def test_validate_invalid_font_size(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {
                    "op": "text", "source": "$input.0",
                    "entries": [{"text": "Bad", "font_size": -5}],
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_FONT_SIZE" in codes

    def test_validate_invalid_timing(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {
                    "op": "text", "source": "$input.0",
                    "entries": [{"text": "Bad", "start": "5", "end": "2"}],
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert not result.valid
        codes = [e["code"] for e in result.errors]
        assert "INVALID_TEXT_TIMING" in codes

    def test_validate_custom_xy_position(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {
                    "op": "text", "source": "$input.0",
                    "entries": [{"text": "OK", "position": "50,100"}],
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid

    def test_validate_preserves_duration(self, test_video):
        edl = {
            "version": "1.0",
            "inputs": [test_video],
            "operations": [
                {"op": "trim", "source": "$input.0", "start": "0", "end": "3"},
                {
                    "op": "text", "source": "$0",
                    "entries": [{"text": "Title"}],
                },
            ],
            "output": {"path": "out.mp4", "codec": "libx264"},
        }
        result = validate_edl(edl)
        assert result.valid
        assert result.estimated_duration == pytest.approx(3.0, abs=0.1)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestTextModels:
    def test_text_entry_to_dict(self):
        entry = TextEntry(text="Hello", position="center", font_size=48)
        d = entry.to_dict()
        assert d["text"] == "Hello"
        assert d["position"] == "center"
        assert d["font_size"] == 48
        assert "bg_color" not in d  # None values excluded

    def test_text_entry_from_dict(self):
        data = {"text": "Hi", "position": "top-left", "font_size": 72}
        entry = TextEntry.from_dict(data)
        assert entry.text == "Hi"
        assert entry.position == "top-left"
        assert entry.font_size == 72
        assert entry.bg_color is None

    def test_text_entry_roundtrip(self):
        original = TextEntry(
            text="Test", position="bottom-center", font_size=36,
            font_color="red", start="1", end="5",
            bg_color="black@0.7", bg_padding=15,
        )
        d = original.to_dict()
        restored = TextEntry.from_dict(d)
        assert restored.text == original.text
        assert restored.position == original.position
        assert restored.font_size == original.font_size
        assert restored.bg_color == original.bg_color

    def test_text_op_to_dict(self):
        from cutagent.models import TextOp
        op = TextOp(
            source="$input.0",
            entries=[TextEntry(text="Title", position="center")],
        )
        d = op.to_dict()
        assert d["op"] == "text"
        assert d["source"] == "$input.0"
        assert len(d["entries"]) == 1
        assert d["entries"][0]["text"] == "Title"

    def test_text_op_parse(self):
        from cutagent.models import parse_operation
        data = {
            "op": "text",
            "source": "$input.0",
            "entries": [
                {"text": "Hello", "position": "center", "font_size": 72},
            ],
        }
        op = parse_operation(data)
        assert op.op == "text"
        assert len(op.entries) == 1
        assert op.entries[0].text == "Hello"
        assert op.entries[0].font_size == 72
