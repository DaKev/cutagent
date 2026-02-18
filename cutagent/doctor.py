"""Diagnostic checks for cutagent prerequisites."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _get_version(binary_path: str) -> str | None:
    """Run a binary with -version and return the first line."""
    try:
        result = subprocess.run(
            [binary_path, "-version"],
            capture_output=True, text=True, timeout=10,
        )
        first_line = result.stdout.strip().splitlines()[0] if result.stdout else ""
        return first_line or None
    except Exception:
        return None


def _detect_source(binary_name: str, path: str) -> str:
    """Determine how a binary was discovered."""
    env_exact = os.environ.get(f"CUTAGENT_{binary_name.upper()}")
    if env_exact and Path(env_exact).is_file() and os.path.samefile(env_exact, path):
        return f"CUTAGENT_{binary_name.upper()} env var"

    env_dir = os.environ.get("CUTAGENT_FFMPEG_DIR")
    if env_dir:
        candidate = Path(env_dir) / binary_name
        if candidate.is_file():
            try:
                if os.path.samefile(str(candidate), path):
                    return "CUTAGENT_FFMPEG_DIR env var"
            except OSError:
                pass

    system_path = shutil.which(binary_name)
    if system_path:
        try:
            if os.path.samefile(system_path, path):
                return "system PATH"
        except OSError:
            pass

    if "static_ffmpeg" in path or "static-ffmpeg" in path:
        return "static-ffmpeg package"
    if "imageio_ffmpeg" in path or "imageio-ffmpeg" in path:
        return "imageio-ffmpeg package"

    return "unknown"


def _check_binary(name: str) -> dict:
    """Check a single binary (ffmpeg or ffprobe)."""
    from cutagent.ffmpeg import find_ffmpeg, find_ffprobe

    finder = find_ffmpeg if name == "ffmpeg" else find_ffprobe
    try:
        path = finder()
        version = _get_version(path)
        source = _detect_source(name, path)
        return {
            "found": True,
            "path": path,
            "version": version,
            "source": source,
        }
    except Exception:
        return {"found": False, "path": None, "version": None, "source": None}


def _check_package(package_name: str) -> dict:
    """Check if a Python package is importable."""
    try:
        mod = __import__(package_name)
        version = getattr(mod, "__version__", "unknown")
        return {"installed": True, "version": version}
    except ImportError:
        return {"installed": False, "version": None}


def _check_temp_dir() -> dict:
    """Check temp directory is writable and report free space."""
    tmp = tempfile.gettempdir()
    writable = os.access(tmp, os.W_OK)
    free_bytes = None
    try:
        stat = shutil.disk_usage(tmp)
        free_bytes = stat.free
    except OSError:
        pass
    return {
        "path": tmp,
        "writable": writable,
        "free_bytes": free_bytes,
        "free_human": _human_bytes(free_bytes) if free_bytes is not None else None,
    }


def _human_bytes(n: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _check_env_vars() -> dict:
    """Report cutagent-related environment variables."""
    keys = ["CUTAGENT_FFMPEG", "CUTAGENT_FFPROBE", "CUTAGENT_FFMPEG_DIR"]
    return {k: os.environ.get(k) for k in keys}


_IMPORTANT_FILTERS = ["drawtext", "subtitles", "overlay", "scale"]


def _check_ffmpeg_filters(ffmpeg_path: str | None) -> dict:
    """Check which important ffmpeg filters are available."""
    if not ffmpeg_path:
        return {"checked": False, "available": {}, "missing": _IMPORTANT_FILTERS}
    try:
        result = subprocess.run(
            [ffmpeg_path, "-filters"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout
        available: dict[str, bool] = {}
        for f in _IMPORTANT_FILTERS:
            available[f] = any(
                f == line.split()[1]
                for line in output.splitlines()
                if len(line.split()) >= 2
            )
        missing = [f for f, ok in available.items() if not ok]
        return {"checked": True, "available": available, "missing": missing}
    except Exception:
        return {"checked": False, "available": {}, "missing": _IMPORTANT_FILTERS}


def _check_shebang() -> dict:
    """Check if the cutagent script has a valid interpreter in its shebang."""
    script_path = shutil.which("cutagent")
    if not script_path:
        return {
            "ok": None,
            "detail": "cutagent not found on PATH — cannot check shebang",
        }
    try:
        with open(script_path, "rb") as f:
            first_line = f.readline(256)
        if not first_line.startswith(b"#!"):
            return {"ok": True, "detail": "No shebang (binary entry point)", "path": script_path}
        shebang = first_line[2:].decode("utf-8", errors="replace").strip()
        parts = shebang.split()
        interpreter = parts[-1] if parts else shebang
        if Path(interpreter).exists():
            return {"ok": True, "detail": shebang, "path": script_path, "interpreter": interpreter}
        return {
            "ok": False,
            "detail": f"Shebang interpreter not found: {interpreter}",
            "path": script_path,
            "interpreter": interpreter,
            "recovery": [
                "Reinstall cutagent: pip install --force-reinstall cutagent",
                "Or use pipx: pipx install cutagent",
                "This often happens after upgrading Python",
            ],
        }
    except Exception as exc:
        return {"ok": None, "detail": f"Could not read script: {exc}", "path": script_path}


def run_doctor() -> dict:
    """Run all diagnostic checks and return a structured report."""
    ffmpeg_info = _check_binary("ffmpeg")
    ffprobe_info = _check_binary("ffprobe")

    versions_match = None
    if ffmpeg_info["version"] and ffprobe_info["version"]:
        versions_match = ffmpeg_info["version"] == ffprobe_info["version"]

    checks = []

    # ffmpeg check
    checks.append({
        "name": "ffmpeg",
        "ok": ffmpeg_info["found"],
        "detail": ffmpeg_info,
    })

    # ffprobe check
    checks.append({
        "name": "ffprobe",
        "ok": ffprobe_info["found"],
        "detail": ffprobe_info,
    })

    # Version match
    checks.append({
        "name": "versions_match",
        "ok": versions_match if versions_match is not None else None,
        "detail": {"ffmpeg": ffmpeg_info["version"], "ffprobe": ffprobe_info["version"]},
    })

    # ffmpeg filters
    filter_info = _check_ffmpeg_filters(ffmpeg_info.get("path"))
    checks.append({
        "name": "ffmpeg_filters",
        "ok": len(filter_info["missing"]) == 0 if filter_info["checked"] else None,
        "detail": filter_info,
    })

    # Shebang
    shebang_info = _check_shebang()
    checks.append({
        "name": "shebang",
        "ok": shebang_info.get("ok"),
        "detail": shebang_info,
    })

    # Packages
    for pkg in ("static_ffmpeg", "imageio_ffmpeg"):
        info = _check_package(pkg)
        checks.append({
            "name": f"package:{pkg}",
            "ok": info["installed"],
            "detail": info,
        })

    # Temp dir
    tmp_info = _check_temp_dir()
    checks.append({
        "name": "temp_directory",
        "ok": tmp_info["writable"],
        "detail": tmp_info,
    })

    # Env vars
    env_info = _check_env_vars()
    checks.append({
        "name": "env_vars",
        "ok": True,
        "detail": env_info,
    })

    all_ok = ffmpeg_info["found"] and ffprobe_info["found"] and tmp_info["writable"]

    return {
        "healthy": all_ok,
        "checks": checks,
    }
