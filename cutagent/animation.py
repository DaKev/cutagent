"""Keyframe interpolation engine — compiles declarative animations to FFmpeg expressions.

Provides easing functions and an interpolation compiler that produces FFmpeg
filter expression strings from keyframe data. No external dependencies beyond
Python's math module.

Supported easings:
    linear, ease-in, ease-out, ease-in-out, spring
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Valid easing names
# ---------------------------------------------------------------------------

EASING_FUNCTIONS = {"linear", "ease-in", "ease-out", "ease-in-out", "spring"}

# ---------------------------------------------------------------------------
# Easing evaluation (for testing / preview)
# ---------------------------------------------------------------------------


def ease_value(easing: str, u: float) -> float:
    """Evaluate an easing function at normalized progress u (0..1).

    Args:
        easing: One of the EASING_FUNCTIONS names.
        u: Normalized progress, 0.0 to 1.0.

    Returns:
        Eased progress value.
    """
    u = max(0.0, min(1.0, u))

    if easing == "linear":
        return u
    if easing == "ease-in":
        return u * u
    if easing == "ease-out":
        return 1.0 - (1.0 - u) * (1.0 - u)
    if easing == "ease-in-out":
        return u * u * (3.0 - 2.0 * u)
    if easing == "spring":
        return 1.0 - math.exp(-4.0 * u) * math.cos(12.0 * u)

    raise ValueError(f"Unknown easing: {easing!r}. Use one of: {sorted(EASING_FUNCTIONS)}")


# ---------------------------------------------------------------------------
# FFmpeg expression builders
# ---------------------------------------------------------------------------

def _ffmpeg_clamp(expr: str, lo: float, hi: float) -> str:
    """Wrap an expression with min/max clamping."""
    return f"min({hi},max({lo},{expr}))"


def _ffmpeg_lerp(v0: float, v1: float, eased_u: str) -> str:
    """Build a linear interpolation expression: v0 + (v1 - v0) * eased_u."""
    delta = v1 - v0
    if delta == 0:
        return str(v0)
    if v0 == 0:
        return f"({delta})*({eased_u})"
    return f"({v0})+({delta})*({eased_u})"


def _ffmpeg_eased_u(easing: str, u_expr: str) -> str:
    """Return an FFmpeg expression for the eased progress.

    Args:
        easing: Easing function name.
        u_expr: FFmpeg expression for normalized progress (0..1).

    Returns:
        FFmpeg expression string for the eased value.
    """
    if easing == "linear":
        return u_expr
    if easing == "ease-in":
        return f"({u_expr})*({u_expr})"
    if easing == "ease-out":
        return f"(1-(1-({u_expr}))*(1-({u_expr})))"
    if easing == "ease-in-out":
        u = u_expr
        return f"({u})*({u})*(3-2*({u}))"
    if easing == "spring":
        return f"(1-exp(-4*({u_expr}))*cos(12*({u_expr})))"

    raise ValueError(f"Unknown easing: {easing!r}")


def interpolate_expr(
    t_var: str,
    keyframes: list[tuple[float, float]],
    easing: str = "linear",
) -> str:
    """Compile keyframes into an FFmpeg expression string.

    The returned expression evaluates against the time variable `t_var`
    to produce the animated value at any point in time.

    Args:
        t_var: FFmpeg time variable name (e.g. "t" for drawtext, "t" for overlay).
        keyframes: List of (time, value) tuples, sorted by time.
        easing: Easing function name from EASING_FUNCTIONS.

    Returns:
        FFmpeg expression string.

    Examples:
        >>> interpolate_expr("t", [(0.0, 0.0), (1.0, 100.0)], "linear")
        "if(lt(t,0),0,if(lt(t,1),(0)+(100)*(... ),100))"
    """
    if not keyframes:
        raise ValueError("keyframes must not be empty")
    if easing not in EASING_FUNCTIONS:
        raise ValueError(f"Unknown easing: {easing!r}. Use one of: {sorted(EASING_FUNCTIONS)}")

    # Single keyframe — constant value
    if len(keyframes) == 1:
        return str(keyframes[0][1])

    # Sort by time
    kfs = sorted(keyframes, key=lambda k: k[0])

    # Build nested if/else for each segment
    # Before first keyframe: hold first value
    # After last keyframe: hold last value
    # Between: interpolate
    return _build_segments_expr(t_var, kfs, easing)


def _build_segments_expr(
    t_var: str,
    kfs: list[tuple[float, float]],
    easing: str,
) -> str:
    """Build a nested if() expression for piecewise interpolation."""
    # For spring easing, use a dedicated expression builder
    if easing == "spring":
        return _build_spring_expr(t_var, kfs)

    first_val = kfs[0][1]
    last_val = kfs[-1][1]

    # Start: before first keyframe, hold first value
    # For each adjacent pair, add an if(lt(t, t_end), lerp_segment, ...)
    # End: hold last value

    segments: list[str] = []
    for i in range(len(kfs) - 1):
        t0, v0 = kfs[i]
        t1, v1 = kfs[i + 1]
        dt = t1 - t0

        if dt <= 0:
            segments.append((t1, str(v1)))
            continue

        # u = clamp((t - t0) / dt, 0, 1)
        u_expr = _ffmpeg_clamp(f"({t_var}-{t0})/{dt}", 0, 1)
        eased = _ffmpeg_eased_u(easing, u_expr)
        lerp = _ffmpeg_lerp(v0, v1, eased)
        segments.append((t1, lerp))

    # Build from inside out
    expr = str(last_val)
    for i in range(len(segments) - 1, -1, -1):
        t_end, seg_expr = segments[i]
        expr = f"if(lt({t_var},{t_end}),{seg_expr},{expr})"

    # Wrap with before-first-keyframe guard
    t_first = kfs[0][0]
    expr = f"if(lt({t_var},{t_first}),{first_val},{expr})"

    return expr


def _build_spring_expr(
    t_var: str,
    kfs: list[tuple[float, float]],
) -> str:
    """Build spring-physics expression: damped oscillation between keyframes.

    Spring formula: target + (start - target) * exp(-damping * elapsed) * cos(freq * elapsed)
    damping = 4.0, frequency = 12.0
    """
    first_val = kfs[0][1]
    last_val = kfs[-1][1]

    segments: list[str] = []
    for i in range(len(kfs) - 1):
        t0, v0 = kfs[i]
        t1, v1 = kfs[i + 1]
        dt = t1 - t0

        if dt <= 0:
            segments.append((t1, str(v1)))
            continue

        elapsed = f"({t_var}-{t0})"
        delta = v0 - v1
        if delta == 0:
            seg_expr = str(v1)
        else:
            seg_expr = f"({v1})+({delta})*exp(-4*{elapsed})*cos(12*{elapsed})"
        segments.append((t1, seg_expr))

    # Build nested if/else
    expr = str(last_val)
    for i in range(len(segments) - 1, -1, -1):
        t_end, seg_expr = segments[i]
        expr = f"if(lt({t_var},{t_end}),{seg_expr},{expr})"

    t_first = kfs[0][0]
    expr = f"if(lt({t_var},{t_first}),{first_val},{expr})"

    return expr
