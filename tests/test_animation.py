"""Tests for cutagent.animation and cutagent.animation_ops — keyframe animations."""

import math
import os
import subprocess

import pytest

from cutagent.animation import (
    ease_value,
    interpolate_expr,
    EASING_FUNCTIONS,
)
from cutagent.models import (
    AnimationKeyframe,
    AnimationProperty,
    AnimationLayer,
    AnimateOp,
    parse_operation,
)
from cutagent.errors import CutAgentError


# ---------------------------------------------------------------------------
# Easing evaluation tests (pure Python, no FFmpeg needed)
# ---------------------------------------------------------------------------

class TestEaseValue:
    """Unit tests for the ease_value function."""

    def test_linear_endpoints(self):
        assert ease_value("linear", 0.0) == 0.0
        assert ease_value("linear", 1.0) == 1.0

    def test_linear_midpoint(self):
        assert ease_value("linear", 0.5) == 0.5

    def test_ease_in_starts_slow(self):
        assert ease_value("ease-in", 0.0) == 0.0
        assert ease_value("ease-in", 1.0) == 1.0
        assert ease_value("ease-in", 0.5) == 0.25

    def test_ease_out_ends_slow(self):
        assert ease_value("ease-out", 0.0) == 0.0
        assert ease_value("ease-out", 1.0) == 1.0
        assert ease_value("ease-out", 0.5) == 0.75

    def test_ease_in_out_symmetric(self):
        assert ease_value("ease-in-out", 0.0) == 0.0
        assert ease_value("ease-in-out", 1.0) == 1.0
        mid = ease_value("ease-in-out", 0.5)
        assert abs(mid - 0.5) < 1e-10

    def test_spring_overshoots(self):
        val = ease_value("spring", 0.3)
        assert val > 1.0, "spring should overshoot target at early progress"

    def test_spring_converges(self):
        val = ease_value("spring", 1.0)
        assert abs(val - 1.0) < 0.02, "spring should converge near 1.0 at u=1"

    def test_unknown_easing_raises(self):
        with pytest.raises(ValueError, match="Unknown easing"):
            ease_value("bounce", 0.5)

    def test_clamps_input(self):
        assert ease_value("linear", -0.5) == 0.0
        assert ease_value("linear", 1.5) == 1.0


# ---------------------------------------------------------------------------
# Interpolation expression tests (pure Python, no FFmpeg needed)
# ---------------------------------------------------------------------------

class TestInterpolateExpr:
    """Unit tests for the interpolate_expr FFmpeg expression compiler."""

    def test_single_keyframe_returns_constant(self):
        result = interpolate_expr("t", [(0.0, 42.0)])
        assert result == "42.0"

    def test_two_keyframes_linear_contains_if(self):
        result = interpolate_expr("t", [(0.0, 0.0), (1.0, 100.0)])
        assert "if(" in result
        assert "100" in result

    def test_empty_keyframes_raises(self):
        with pytest.raises(ValueError, match="keyframes must not be empty"):
            interpolate_expr("t", [])

    def test_unknown_easing_raises(self):
        with pytest.raises(ValueError, match="Unknown easing"):
            interpolate_expr("t", [(0.0, 0.0), (1.0, 1.0)], easing="bounce")

    def test_all_easings_produce_expressions(self):
        kfs = [(0.0, 0.0), (1.0, 100.0)]
        for easing in EASING_FUNCTIONS:
            result = interpolate_expr("t", kfs, easing=easing)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_three_keyframes_produces_nested_if(self):
        result = interpolate_expr("t", [(0.0, 0.0), (1.0, 50.0), (2.0, 100.0)])
        assert result.count("if(") >= 2

    def test_spring_expression_contains_exp_cos(self):
        result = interpolate_expr("t", [(0.0, 0.0), (1.0, 100.0)], easing="spring")
        assert "exp(" in result
        assert "cos(" in result

    def test_same_value_keyframes_returns_constant_segment(self):
        result = interpolate_expr("t", [(0.0, 50.0), (1.0, 50.0)])
        assert "50" in result


# ---------------------------------------------------------------------------
# Model serialization tests
# ---------------------------------------------------------------------------

class TestAnimationModels:
    """Tests for animation dataclass serialization."""

    def test_keyframe_roundtrip(self):
        kf = AnimationKeyframe(t=1.5, value=200.0)
        d = kf.to_dict()
        restored = AnimationKeyframe.from_dict(d)
        assert restored.t == kf.t
        assert restored.value == kf.value

    def test_property_roundtrip(self):
        prop = AnimationProperty(
            keyframes=[AnimationKeyframe(0.0, 0.0), AnimationKeyframe(1.0, 100.0)],
            easing="ease-out",
        )
        d = prop.to_dict()
        restored = AnimationProperty.from_dict(d)
        assert restored.easing == "ease-out"
        assert len(restored.keyframes) == 2

    def test_text_layer_roundtrip(self):
        layer = AnimationLayer(
            type="text",
            text="Hello",
            start=0.0,
            end=3.0,
            font_size=72,
            font_color="yellow",
            properties={
                "x": AnimationProperty(
                    keyframes=[AnimationKeyframe(0.0, -100.0), AnimationKeyframe(1.0, 200.0)],
                    easing="ease-in",
                ),
            },
        )
        d = layer.to_dict()
        assert d["type"] == "text"
        assert d["text"] == "Hello"
        restored = AnimationLayer.from_dict(d)
        assert restored.type == "text"
        assert restored.text == "Hello"
        assert "x" in restored.properties

    def test_image_layer_roundtrip(self):
        layer = AnimationLayer(
            type="image",
            path="logo.png",
            start=0.0,
            end=5.0,
            properties={
                "opacity": AnimationProperty(
                    keyframes=[AnimationKeyframe(0.0, 0.0), AnimationKeyframe(1.0, 1.0)],
                    easing="linear",
                ),
            },
        )
        d = layer.to_dict()
        assert d["type"] == "image"
        assert d["path"] == "logo.png"
        restored = AnimationLayer.from_dict(d)
        assert restored.path == "logo.png"

    def test_animate_op_roundtrip(self):
        op = AnimateOp(
            source="video.mp4",
            fps=24,
            layers=[
                AnimationLayer(
                    type="text",
                    text="Test",
                    start=0.0,
                    end=2.0,
                    properties={},
                ),
            ],
        )
        d = op.to_dict()
        assert d["op"] == "animate"
        assert d["fps"] == 24
        restored = AnimateOp.from_dict(d)
        assert restored.source == "video.mp4"
        assert restored.fps == 24
        assert len(restored.layers) == 1

    def test_parse_operation_recognizes_animate(self):
        data = {
            "op": "animate",
            "source": "test.mp4",
            "fps": 30,
            "layers": [{
                "type": "text",
                "text": "Hello",
                "start": 0.0,
                "end": 3.0,
                "properties": {},
            }],
        }
        op = parse_operation(data)
        assert isinstance(op, AnimateOp)
        assert op.source == "test.mp4"

    def test_text_layer_styling_roundtrip(self):
        layer = AnimationLayer(
            type="text",
            text="Styled",
            start=0.0,
            end=3.0,
            bg_color="black@0.5",
            bg_padding=12,
            shadow_color="black",
            shadow_offset=3,
            stroke_color="navy",
            stroke_width=2,
            properties={},
        )
        d = layer.to_dict()
        assert d["bg_color"] == "black@0.5"
        assert d["bg_padding"] == 12
        assert d["shadow_color"] == "black"
        assert d["shadow_offset"] == 3
        assert d["stroke_color"] == "navy"
        assert d["stroke_width"] == 2
        restored = AnimationLayer.from_dict(d)
        assert restored.bg_color == "black@0.5"
        assert restored.shadow_color == "black"
        assert restored.stroke_color == "navy"
        assert restored.stroke_width == 2

    def test_text_layer_no_styling_excludes_fields(self):
        layer = AnimationLayer(
            type="text", text="Plain", start=0.0, end=3.0, properties={},
        )
        d = layer.to_dict()
        assert "bg_color" not in d
        assert "shadow_color" not in d
        assert "stroke_color" not in d


# ---------------------------------------------------------------------------
# Validation tests (no FFmpeg needed)
# ---------------------------------------------------------------------------

class TestAnimationValidation:
    """Tests for animation layer validation logic."""

    def test_empty_layers_raises(self):
        from cutagent.animation_ops import animate
        with pytest.raises(CutAgentError, match="No animation layers"):
            animate("dummy.mp4", [], "out.mp4")

    def test_invalid_layer_type_raises(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(type="video", start=0, end=1)
        with pytest.raises(CutAgentError, match="invalid type"):
            _validate_layer(layer, 0)

    def test_text_layer_missing_text_raises(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(type="text", text=None, start=0, end=1)
        with pytest.raises(CutAgentError, match="requires a 'text' field"):
            _validate_layer(layer, 0)

    def test_image_layer_missing_path_raises(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(type="image", path=None, start=0, end=1)
        with pytest.raises(CutAgentError, match="requires a 'path' field"):
            _validate_layer(layer, 0)

    def test_invalid_property_for_layer_type_raises(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(
            type="text",
            text="Hello",
            start=0,
            end=1,
            properties={
                "scale": AnimationProperty(
                    keyframes=[AnimationKeyframe(0, 1.0)],
                    easing="linear",
                ),
            },
        )
        with pytest.raises(CutAgentError, match="not animatable"):
            _validate_layer(layer, 0)

    def test_invalid_easing_raises(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(
            type="text",
            text="Hello",
            start=0,
            end=1,
            properties={
                "x": AnimationProperty(
                    keyframes=[AnimationKeyframe(0, 0)],
                    easing="bounce",
                ),
            },
        )
        with pytest.raises(CutAgentError, match="unknown easing"):
            _validate_layer(layer, 0)

    def test_empty_keyframes_raises(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(
            type="text",
            text="Hello",
            start=0,
            end=1,
            properties={
                "x": AnimationProperty(keyframes=[], easing="linear"),
            },
        )
        with pytest.raises(CutAgentError, match="no keyframes"):
            _validate_layer(layer, 0)

    def test_valid_text_layer_passes(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(
            type="text",
            text="Hello",
            start=0,
            end=3,
            properties={
                "x": AnimationProperty(
                    keyframes=[AnimationKeyframe(0, -100), AnimationKeyframe(1, 200)],
                    easing="ease-out",
                ),
                "opacity": AnimationProperty(
                    keyframes=[AnimationKeyframe(0, 0), AnimationKeyframe(0.5, 1)],
                    easing="linear",
                ),
            },
        )
        _validate_layer(layer, 0)  # should not raise

    def test_valid_image_layer_passes(self):
        from cutagent.animation_ops import _validate_layer
        layer = AnimationLayer(
            type="image",
            path="logo.png",
            start=0,
            end=5,
            properties={
                "x": AnimationProperty(
                    keyframes=[AnimationKeyframe(0, 0), AnimationKeyframe(2, 200)],
                    easing="spring",
                ),
                "scale": AnimationProperty(
                    keyframes=[AnimationKeyframe(0, 0.5)],
                    easing="linear",
                ),
            },
        )
        _validate_layer(layer, 0)  # should not raise


# ---------------------------------------------------------------------------
# Integration test (requires FFmpeg with drawtext)
# ---------------------------------------------------------------------------

def _ffmpeg_has_drawtext(ffmpeg_bin: str = "ffmpeg") -> bool:
    """Check if FFmpeg supports the drawtext filter."""
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-filters"],
            capture_output=True, text=True, timeout=10,
        )
        return "drawtext" in result.stdout
    except Exception:
        return False


def _find_drawtext_ffmpeg() -> str | None:
    """Find an FFmpeg binary with drawtext support."""
    import shutil
    from pathlib import Path
    ffmpeg_dir = os.environ.get("CUTAGENT_FFMPEG_DIR")
    if ffmpeg_dir:
        candidate = str(Path(ffmpeg_dir) / "ffmpeg")
        if _ffmpeg_has_drawtext(candidate):
            return candidate
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
    reason="FFmpeg with drawtext filter not available",
)


@pytest.fixture(autouse=True)
def _use_drawtext_ffmpeg_animation():
    """Ensure animation integration tests use an FFmpeg with drawtext support."""
    if _drawtext_ffmpeg is None:
        yield
        return
    from cutagent.ffmpeg import reset_cache
    old = os.environ.get("CUTAGENT_FFMPEG")
    os.environ["CUTAGENT_FFMPEG"] = _drawtext_ffmpeg
    reset_cache()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("CUTAGENT_FFMPEG", None)
        else:
            os.environ["CUTAGENT_FFMPEG"] = old
        reset_cache()


@requires_drawtext
class TestAnimateIntegration:
    """Integration tests that run FFmpeg."""

    def test_text_animation_produces_output(self, test_video, tmp_path):
        from cutagent.animation_ops import animate
        output = str(tmp_path / "animated.mp4")
        layers = [
            AnimationLayer(
                type="text",
                text="Hello World",
                start=0.0,
                end=2.0,
                font_size=48,
                font_color="white",
                properties={
                    "x": AnimationProperty(
                        keyframes=[AnimationKeyframe(0.0, -200.0), AnimationKeyframe(1.0, 100.0)],
                        easing="ease-out",
                    ),
                    "opacity": AnimationProperty(
                        keyframes=[AnimationKeyframe(0.0, 0.0), AnimationKeyframe(0.5, 1.0)],
                        easing="linear",
                    ),
                },
            ),
        ]
        result = animate(test_video, layers, output)
        assert result.success
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0

    def test_multiple_text_layers(self, test_video, tmp_path):
        from cutagent.animation_ops import animate
        output = str(tmp_path / "multi_text.mp4")
        layers = [
            AnimationLayer(
                type="text", text="Title", start=0.0, end=2.0,
                font_size=72, font_color="white",
                properties={
                    "y": AnimationProperty(
                        keyframes=[AnimationKeyframe(0.0, -50.0), AnimationKeyframe(0.5, 100.0)],
                        easing="ease-out",
                    ),
                },
            ),
            AnimationLayer(
                type="text", text="Subtitle", start=0.5, end=3.0,
                font_size=36, font_color="yellow",
                properties={
                    "opacity": AnimationProperty(
                        keyframes=[AnimationKeyframe(0.5, 0.0), AnimationKeyframe(1.0, 1.0)],
                        easing="linear",
                    ),
                },
            ),
        ]
        result = animate(test_video, layers, output)
        assert result.success

    def test_spring_easing_renders(self, test_video, tmp_path):
        from cutagent.animation_ops import animate
        output = str(tmp_path / "spring.mp4")
        layers = [
            AnimationLayer(
                type="text", text="Bounce!", start=0.0, end=3.0,
                font_size=60, font_color="white",
                properties={
                    "x": AnimationProperty(
                        keyframes=[AnimationKeyframe(0.0, -200.0), AnimationKeyframe(1.0, 200.0)],
                        easing="spring",
                    ),
                },
            ),
        ]
        result = animate(test_video, layers, output)
        assert result.success
