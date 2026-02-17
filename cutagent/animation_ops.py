"""Animation operations — apply keyframe-driven animated layers onto video.

Compiles AnimateOp layers into FFmpeg filter_complex expressions using
drawtext (text layers) and overlay (image layers) with animated properties.
"""

from __future__ import annotations

from pathlib import Path

from cutagent.animation import interpolate_expr, EASING_FUNCTIONS
from cutagent.errors import (
    CutAgentError,
    MISSING_FIELD,
    EMPTY_ANIMATION_LAYERS,
    INVALID_LAYER_TYPE,
    INVALID_ANIMATION_EASING,
    INVALID_ANIMATION_PROPERTY,
    MISSING_LAYER_FIELD,
)
from cutagent.ffmpeg import run_ffmpeg
from cutagent.models import (
    AnimationLayer,
    OperationResult,
    TEXT_ANIMATABLE_PROPS,
    IMAGE_ANIMATABLE_PROPS,
    ANIMATION_LAYER_TYPES,
    ANIMATION_EASINGS,
)
from cutagent.probe import probe as probe_file


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_layer(layer: AnimationLayer, idx: int) -> None:
    """Validate a single animation layer, raising CutAgentError on problems."""
    if layer.type not in ANIMATION_LAYER_TYPES:
        raise CutAgentError(
            code=INVALID_LAYER_TYPE,
            message=f"Layer {idx}: invalid type {layer.type!r}",
            recovery=[f"Use one of: {sorted(ANIMATION_LAYER_TYPES)}"],
            context={"layer_index": idx, "type": layer.type},
        )

    if layer.type == "text" and not layer.text:
        raise CutAgentError(
            code=MISSING_LAYER_FIELD,
            message=f"Layer {idx}: text layer requires a 'text' field",
            recovery=["Add a 'text' field to the text animation layer"],
            context={"layer_index": idx},
        )

    if layer.type == "image" and not layer.path:
        raise CutAgentError(
            code=MISSING_LAYER_FIELD,
            message=f"Layer {idx}: image layer requires a 'path' field",
            recovery=["Add a 'path' field pointing to the image file"],
            context={"layer_index": idx},
        )

    allowed_props = TEXT_ANIMATABLE_PROPS if layer.type == "text" else IMAGE_ANIMATABLE_PROPS
    for prop_name, prop in layer.properties.items():
        if prop_name not in allowed_props:
            raise CutAgentError(
                code=INVALID_ANIMATION_PROPERTY,
                message=f"Layer {idx}: property {prop_name!r} is not animatable for {layer.type!r} layers",
                recovery=[f"Animatable properties for {layer.type}: {sorted(allowed_props)}"],
                context={"layer_index": idx, "property": prop_name},
            )
        if prop.easing not in ANIMATION_EASINGS:
            raise CutAgentError(
                code=INVALID_ANIMATION_EASING,
                message=f"Layer {idx}: unknown easing {prop.easing!r} on property {prop_name!r}",
                recovery=[f"Use one of: {sorted(ANIMATION_EASINGS)}"],
                context={"layer_index": idx, "easing": prop.easing},
            )
        if not prop.keyframes:
            raise CutAgentError(
                code=MISSING_FIELD,
                message=f"Layer {idx}: property {prop_name!r} has no keyframes",
                recovery=["Add at least one keyframe with 't' and 'value'"],
                context={"layer_index": idx, "property": prop_name},
            )


# ---------------------------------------------------------------------------
# Text layer → drawtext filter
# ---------------------------------------------------------------------------

def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\\\\\''")
    text = text.replace(":", "\\:")
    text = text.replace(";", "\\;")
    text = text.replace("%", "%%")
    return text


def _build_text_filter(layer: AnimationLayer) -> str:
    """Build a drawtext filter string with animated expressions."""
    escaped = _escape_drawtext(layer.text)

    parts = [f"text='{escaped}'"]

    # x — animated or default center
    if "x" in layer.properties:
        kfs = [(kf.t, kf.value) for kf in layer.properties["x"].keyframes]
        x_expr = interpolate_expr("t", kfs, layer.properties["x"].easing)
        parts.append(f"x='{x_expr}'")
    else:
        parts.append("x='(w-text_w)/2'")

    # y — animated or default center
    if "y" in layer.properties:
        kfs = [(kf.t, kf.value) for kf in layer.properties["y"].keyframes]
        y_expr = interpolate_expr("t", kfs, layer.properties["y"].easing)
        parts.append(f"y='{y_expr}'")
    else:
        parts.append("y='(h-text_h)/2'")

    # font_size — animated or static
    if "font_size" in layer.properties:
        kfs = [(kf.t, kf.value) for kf in layer.properties["font_size"].keyframes]
        fs_expr = interpolate_expr("t", kfs, layer.properties["font_size"].easing)
        parts.append(f"fontsize='{fs_expr}'")
    else:
        parts.append(f"fontsize={layer.font_size}")

    parts.append(f"fontcolor={layer.font_color}")

    if layer.font:
        parts.append(f"font='{layer.font}'")

    # opacity — animated or full
    if "opacity" in layer.properties:
        kfs = [(kf.t, kf.value) for kf in layer.properties["opacity"].keyframes]
        alpha_expr = interpolate_expr("t", kfs, layer.properties["opacity"].easing)
        parts.append(f"alpha='{alpha_expr}'")

    # Timed display: enable='between(t,start,end)'
    parts.append(f"enable='between(t,{layer.start},{layer.end})'")

    return "drawtext=" + ":".join(parts)


# ---------------------------------------------------------------------------
# Image layer → overlay filter
# ---------------------------------------------------------------------------

def _build_image_filters(layer: AnimationLayer, input_idx: int) -> tuple[list[str], str]:
    """Build filter chains for an image overlay layer.

    Returns:
        (filter_lines, final_label) — list of filter expressions and the
        output stream label to overlay onto the main video.
    """
    filters: list[str] = []
    img_label = f"img{input_idx}"

    # Scale the image if a static scale is given
    scale_filter = ""
    if "scale" in layer.properties:
        kfs = layer.properties["scale"].keyframes
        if len(kfs) == 1:
            s = kfs[0].value
            scale_filter = f",scale=iw*{s}:ih*{s}"

    # Format the image input as rgba
    filters.append(f"[{input_idx}:v]format=rgba{scale_filter}[{img_label}]")

    # Build overlay expression
    overlay_parts: list[str] = []

    if "x" in layer.properties:
        kfs = [(kf.t, kf.value) for kf in layer.properties["x"].keyframes]
        x_expr = interpolate_expr("t", kfs, layer.properties["x"].easing)
        overlay_parts.append(f"x='{x_expr}'")
    else:
        overlay_parts.append("x='(W-w)/2'")

    if "y" in layer.properties:
        kfs = [(kf.t, kf.value) for kf in layer.properties["y"].keyframes]
        y_expr = interpolate_expr("t", kfs, layer.properties["y"].easing)
        overlay_parts.append(f"y='{y_expr}'")
    else:
        overlay_parts.append("y='(H-h)/2'")

    overlay_parts.append(f"enable='between(t,{layer.start},{layer.end})'")

    return filters, ":".join(overlay_parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def animate(
    source: str,
    layers: list[AnimationLayer],
    output: str,
    fps: int = 30,
    codec: str = "libx264",
) -> OperationResult:
    """Apply animated layers onto a video using FFmpeg filter_complex.

    Args:
        source: Path to the source video.
        layers: List of AnimationLayer objects.
        output: Path for the output file.
        fps: Frames per second for the output.
        codec: Video codec (default libx264).

    Returns:
        OperationResult with the output path.
    """
    if not layers:
        raise CutAgentError(
            code=EMPTY_ANIMATION_LAYERS,
            message="No animation layers provided — at least one is required",
            recovery=["Add at least one layer to the 'layers' list"],
        )

    for idx, layer in enumerate(layers):
        _validate_layer(layer, idx)

    info = probe_file(source)

    # Separate text and image layers (order matters for filter chain)
    text_layers = [l for l in layers if l.type == "text"]
    image_layers = [l for l in layers if l.type == "image"]

    # Build filter_complex
    args: list[str] = ["-i", source]

    # Add image inputs
    image_input_indices: list[int] = []
    for img_layer in image_layers:
        idx = len(image_input_indices) + 1  # 0 is the video source
        args += ["-i", str(img_layer.path)]
        image_input_indices.append(idx)

    filter_lines: list[str] = []
    current_video = "0:v"
    current_label = "base"

    # Step 1: Apply text layers as chained drawtext filters on the base video
    if text_layers:
        drawtext_chain = ",".join(_build_text_filter(l) for l in text_layers)
        filter_lines.append(f"[{current_video}]{drawtext_chain}[textout]")
        current_label = "textout"
    else:
        # No text layers — pass through
        current_label = "0:v"

    # Step 2: Apply image overlays sequentially
    for i, (img_layer, input_idx) in enumerate(zip(image_layers, image_input_indices)):
        img_filters, overlay_params = _build_image_filters(img_layer, input_idx)
        filter_lines.extend(img_filters)

        out_label = f"ovr{i}"
        img_label = f"img{input_idx}"
        filter_lines.append(
            f"[{current_label}][{img_label}]overlay={overlay_params}[{out_label}]"
        )
        current_label = out_label

    if not filter_lines:
        raise CutAgentError(
            code=EMPTY_ANIMATION_LAYERS,
            message="No renderable animation layers after processing",
            recovery=["Check that layers have valid type and properties"],
        )

    filter_complex = ";".join(filter_lines)

    args += [
        "-filter_complex", filter_complex,
        "-map", f"[{current_label}]",
        "-map", "0:a?",
        "-c:v", codec,
        "-c:a", "aac",
        output,
    ]

    run_ffmpeg(args)

    return OperationResult(
        success=True,
        output_path=output,
        duration_seconds=info.duration,
    )
