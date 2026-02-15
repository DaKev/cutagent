# CutAgent

**Agent-first video cutting library** — declarative JSON edits powered by FFmpeg.

[![CI](https://github.com/DaKev/cutagent/actions/workflows/ci.yml/badge.svg)](https://github.com/DaKev/cutagent/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

CutAgent is designed from the ground up for **AI agents** and **programmatic video editing**. Every CLI command outputs structured JSON. Every operation is composable through a declarative Edit Decision List (EDL) format. No GUI, no human-formatted text — just clean machine-readable interfaces for professional video cutting.

## Why CutAgent?

- **Agent-first**: Every command returns structured JSON — built for LLM tool use, not human eyes
- **Declarative EDL**: Describe your edit as a JSON document, execute it in one call
- **Zero runtime dependencies**: Pure Python + FFmpeg — nothing else to install
- **Content intelligence**: Scene detection, silence detection, audio levels, keyframe analysis
- **Professional operations**: Trim, split, concat, reorder, extract, fade with crossfade transitions
- **Structured errors**: Error codes, recovery hints, and context in every failure response

## Requirements

- Python 3.10+
- FFmpeg and FFprobe on `$PATH`

## Installation

**From GitHub:**

```bash
pip install git+https://github.com/DaKev/cutagent.git
```

**From source (development):**

```bash
git clone https://github.com/DaKev/cutagent.git
cd cutagent
pip install -e ".[dev]"
```

## Quick Start

### Python API

```python
from cutagent import probe, trim, execute_edl

# Inspect a video
info = probe("interview.mp4")
print(info.duration, info.width, info.height)

# Trim a segment
result = trim("interview.mp4", start="00:02:15", end="00:05:40", output="clip.mp4")

# Execute a full edit decision list
edl = {
    "version": "1.0",
    "inputs": ["interview.mp4"],
    "operations": [
        {"op": "trim", "source": "interview.mp4", "start": "00:02:15", "end": "00:05:40"},
        {"op": "trim", "source": "interview.mp4", "start": "00:12:00", "end": "00:14:30"},
        {"op": "concat", "segments": ["$0", "$1"]}
    ],
    "output": {"path": "highlight.mp4", "codec": "copy"}
}
result = execute_edl(edl)
```

### CLI (AI-Native — all output is JSON)

```bash
# Discover capabilities (returns machine-readable schema)
cutagent capabilities

# Probe a video
cutagent probe interview.mp4

# Get keyframe positions
cutagent keyframes interview.mp4

# Detect scene boundaries
cutagent scenes interview.mp4 --threshold 0.3

# Build a full content summary (scenes + silence + audio levels)
cutagent summarize interview.mp4

# Trim
cutagent trim interview.mp4 --start 00:02:15 --end 00:05:40 -o clip.mp4

# Split at multiple points
cutagent split interview.mp4 --at 00:05:00,00:10:00 --prefix segment

# Concatenate
cutagent concat clip1.mp4 clip2.mp4 -o merged.mp4

# Extract audio
cutagent extract interview.mp4 --stream audio -o audio.aac

# Validate an EDL without executing
cutagent validate edit.json

# Execute an EDL
cutagent execute edit.json
```

### EDL Format

The Edit Decision List is a declarative JSON format for multi-step edits. Operations run sequentially; `$N` references the output of operation N:

```json
{
  "version": "1.0",
  "inputs": ["interview.mp4", "broll.mp4"],
  "operations": [
    {"op": "trim", "source": "interview.mp4", "start": "00:01:00", "end": "00:03:00"},
    {"op": "trim", "source": "broll.mp4", "start": "00:00:10", "end": "00:00:20"},
    {"op": "fade", "source": "$1", "fade_in": 0.5, "fade_out": 0.5},
    {"op": "concat", "segments": ["$0", "$2"], "transition": "crossfade", "transition_duration": 0.5}
  ],
  "output": {"path": "final.mp4", "codec": "libx264"}
}
```

**Available operations:** `trim`, `split`, `concat`, `reorder`, `extract`, `fade`

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     cutagent (CLI / Python API)                  │
├──────────────────┬─────────────────┬─────────────────────────────┤
│  cli.py          │  engine.py      │  validation.py              │
│  JSON output     │  EDL execution  │  Dry-run validation         │
├──────────────────┼─────────────────┼─────────────────────────────┤
│  probe.py        │  operations.py  │  models.py                  │
│  Media analysis  │  Video ops      │  Typed dataclasses          │
├──────────────────┴─────────────────┴─────────────────────────────┤
│  ffmpeg.py  (subprocess wrappers)  │  errors.py  (error codes)   │
└──────────────────────────────────────────────────────────────────┘
```

- **`ffmpeg.py`** is the only module that spawns subprocesses
- **`models.py`** and **`errors.py`** have zero internal dependencies
- All public functions return typed dataclasses, never raw dicts
- The CLI outputs JSON exclusively — designed for machine consumption

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation error (bad input, invalid EDL) |
| 2 | Execution error (FFmpeg failed) |
| 3 | System error (FFmpeg not found, permissions) |

## Error Handling

Every error includes a code, message, and recovery suggestions:

```json
{
  "error": true,
  "code": "TRIM_BEYOND_DURATION",
  "message": "End time 01:00:00 (3600.000s) exceeds duration (120.500s)",
  "recovery": [
    "Source duration is 120.500s — set end to 120.500 or less",
    "Run 'cutagent probe <file>' to check the actual duration"
  ],
  "context": {"source": "clip.mp4", "duration": 120.5, "end": "01:00:00"}
}
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Setting up the development environment
- Architecture principles and code style
- Adding new operations
- The JSON output contract

## License

[MIT](LICENSE)
