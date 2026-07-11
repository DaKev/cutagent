# CutAgent AI-Agent Evaluation Report

**Date:** 2026-03-09
**Evaluator:** AI Agent (Claude)
**Test Video:** `tests/Test videos/Dune du Pylat.mp4` (1920x1080, 3m52s, H.264+AAC, ~300MB)
**CutAgent Version:** 0.3.0
**FFmpeg Version:** 8.0.1

---

## Executive Summary

CutAgent is **exceptionally well-designed for AI-agent use**. The structured JSON output, comprehensive capability discovery, declarative EDL format, and rich error messages with recovery hints make it one of the most agent-friendly CLI tools I've encountered. The `capabilities` command alone provides everything an agent needs to plan a full video editing workflow.

**Overall Rating: 9/10** — Minor issues prevent a perfect score (see bugs below).

---

## Features Tested

### 1. Discovery & Setup

| Command | Status | Notes |
|---------|--------|-------|
| `cutagent doctor` | PASS | Clear health check with FFmpeg version, filter availability, disk space |
| `cutagent capabilities` | PASS | Outstanding — provides operations, schemas, workflow, recipes, quality checklist |
| `cutagent schema index` | PASS | Lists all targets and operations |
| `cutagent schema operation <name>` | PASS | Returns full JSON Schema for any operation |
| `cutagent schema edl` | PASS | Returns EDL format schema with reference documentation |
| `cutagent schema command` | PASS | Documents all CLI commands and options |

**Agent Intuitiveness: 10/10** — The `AGENTS.md` + `capabilities` command forms a perfect onboarding path. An agent can fully self-discover every feature without documentation.

### 2. Analysis Commands

| Command | Status | Notes |
|---------|--------|-------|
| `probe` | PASS | Fast (<0.5s), clean output with streams, duration, resolution |
| `probe --fields` | PASS | Field projection works perfectly — critical for context conservation |
| `summarize` | PASS | Excellent content map with scenes + silence + suggested cut points |
| `summarize --frame-dir` | PASS | Scene frames with 10/50/90% offsets — great for visual understanding |
| `scenes` | PASS | Scene detection with configurable threshold |
| `silence` | PASS | Detects silence intervals with threshold/min-duration params |
| `beats` | PASS | Beat detection with timestamp + strength |
| `keyframes` | PASS | Returns all keyframe positions |
| `audio-levels` | PASS | Per-second RMS dB levels |
| `thumbnail` | PASS | Single frame extraction |
| `frames` | PASS | Multi-frame extraction at specified timestamps |

**Agent Intuitiveness: 8/10** — See issues below regarding output volume.

### 3. Editing Operations

| Command | Status | Notes |
|---------|--------|-------|
| `trim` | PASS | Keyframe proximity warnings are extremely helpful |
| `split` | PASS | Returns all segment paths with durations |
| `concat` | PASS | Simple concat with copy codec |
| `speed` | PASS | Factor-based speed control |
| `extract` | PASS | Audio/video stream extraction |

**Agent Intuitiveness: 10/10** — All operations are predictable and well-documented.

### 4. Audio Polish

| Command | Status | Notes |
|---------|--------|-------|
| `normalize` | PASS | EBU R128 loudness normalization |
| `volume` | PASS | dB-based volume adjustment |
| `mix` | PASS | Background audio mixing with level control |
| `replace-audio` | PASS | Full audio track replacement |

**Agent Intuitiveness: 10/10** — Clean, predictable behavior.

### 5. Visual Polish

| Command | Status | Notes |
|---------|--------|-------|
| `fade` | PASS | Fade-in/fade-out works perfectly |
| `text` | BLOCKED | Requires `drawtext` filter (missing in Homebrew FFmpeg 8.0.1) |
| `animate` | BLOCKED | Requires `drawtext` filter (same dependency) |

**Agent Intuitiveness: 9/10** — The error message correctly identifies the missing filter and suggests remediation. The `doctor` command also flags it proactively.

### 6. EDL Workflow

| Command | Status | Notes |
|---------|--------|-------|
| `validate` (inline) | PASS | `--edl-json` works perfectly |
| `validate` (stdin) | PASS | Pipe via `cutagent execute -` works |
| `execute` (inline) | PASS | Full EDL execution with progress on stderr |
| `execute --dry-run` | PASS | Validation without media mutation |
| `execute --quiet` | PASS | Suppresses progress JSONL |
| `op <name> --dry-run` | PASS | Single-operation validation |
| `op <name> --json` | PASS | Single-operation execution |
| Named references (`$name`) | PASS | Works alongside positional (`$N`) references |
| Complex multi-step EDL | PASS | 6-operation EDL (trim→normalize→concat→fade) executed correctly |

**Agent Intuitiveness: 10/10** — The EDL system is the crown jewel. The ability to compose complex workflows declaratively, validate before executing, and reference prior operations by name or index is perfectly suited for AI agents.

### 7. Output Shaping

| Feature | Status | Notes |
|---------|--------|-------|
| `--fields` on `probe` | PASS | Perfect for context conservation |
| `--fields` on `scenes` | PASS | Works correctly |
| `--fields` on other commands | FAIL | Not supported — returns "No such option" |
| `--response-format ndjson` on `scenes` | PASS | Returns one JSON object per line |
| `--response-format ndjson` on `audio-levels` | PASS | Returns one JSON object per line |
| `--response-format ndjson` on `keyframes` | FAIL | Not supported |
| `--response-format ndjson` on `beats` | FAIL | Not supported |
| `--response-format ndjson` on `silence` | FAIL | Not supported |
| `--sanitize-output basic` | PASS | Works on execute |

**Agent Intuitiveness: 6/10** — The inconsistent availability of `--fields` and `--response-format` across commands is confusing.

### 8. Error Handling

| Scenario | Status | Error Code | Notes |
|----------|--------|-----------|-------|
| Nonexistent file | PASS | `INPUT_NOT_FOUND` | Great recovery hints |
| Trim beyond duration | PASS | `TRIM_BEYOND_DURATION` | Includes actual duration in context |
| Start after end | PASS | `TRIM_START_AFTER_END` | Suggests swapping times |
| Speed factor = 0 | PASS | `INVALID_ARGUMENT` | Clear bounds guidance |
| Invalid EDL operation | PASS | `UNKNOWN_OPERATION` | Lists all supported operations |
| Invalid reference | PASS | `INVALID_REFERENCE` | Explains what's wrong |
| Missing FFmpeg filter | PASS | `FFMPEG_FAILED` | Points to doctor command |

**Agent Intuitiveness: 9/10** — Error messages are best-in-class. Recovery hints are actionable and specific.

---

## Bugs Found

### BUG-1: Exit Codes Not Matching Documentation (Severity: Medium)

**Expected:** The README documents exit codes 1 (validation error), 2 (execution error), 3 (system error).

**Actual:** Errors like `INPUT_NOT_FOUND`, `TRIM_BEYOND_DURATION`, and `TRIM_START_AFTER_END` all return **exit code 0** instead of exit code 1. Only `FFMPEG_FAILED` correctly returns exit code 2.

**Impact:** Agents that check `$?` for success/failure will miss errors. They must parse the JSON `"error": true` field instead.

**Reproduction:**
```bash
cutagent probe /nonexistent/file.mp4; echo $?   # Returns 0, should be 1
cutagent trim file.mp4 --start 10 --end 5 -o out.mp4; echo $?  # Returns 0, should be 1
```

### BUG-2: EDL Version Validation Missing (Severity: Low)

**Expected:** `"version": "2.0"` should fail validation since only `"1.0"` is supported.

**Actual:** `cutagent validate` accepts `"version": "2.0"` with `{"valid": true}`.

**Reproduction:**
```bash
cutagent validate --edl-json '{"version": "2.0", "inputs": [], "operations": [], "output": {"path": "out.mp4"}}'
# Returns {"valid": true, "errors": [], "warnings": []}
```

### BUG-3: `doctor` Reports `versions_match: false` Despite Matching Versions (Severity: Low)

**Observed:** FFmpeg 8.0.1 and FFprobe 8.0.1 report `versions_match: false`. The version strings differ only in copyright text (`"Copyright (c) 2000-2025"` vs `"Copyright (c) 2007-2025"`), which triggers a false mismatch. The check should compare version numbers, not full strings.

### BUG-4: `thumbnail` Error Message Misleading (Severity: Low)

**Command:** `cutagent thumbnail file.mp4 -o thumb.jpg` (missing `--at`)

**Error:** `"message": "Missing parameter: at"` with `"code": "UNEXPECTED_ERROR"` and recovery saying "This is an unexpected error — please report it."

**Expected:** Should be a validation error (not "unexpected") with recovery hint like "Use --at to specify the timestamp for the thumbnail."

---

## Design Issues / Improvement Suggestions

### ISSUE-1: `--fields` and `--response-format` Inconsistently Available (Severity: Medium)

These options are critical for agent context conservation, but they're only available on a subset of commands:

| Command | `--fields` | `--response-format ndjson` |
|---------|------------|---------------------------|
| `probe` | Yes | No |
| `scenes` | Yes | Yes |
| `audio-levels` | No | Yes |
| `frames` | Yes | Yes |
| `keyframes` | No | No |
| `beats` | No | No |
| `silence` | No | No |
| `summarize` | No | No |

**Impact:** `keyframes` (388 items) and `beats` (473 items) produce massive JSON arrays that consume significant agent context. Without `--response-format ndjson`, agents can't stream-process these. The AGENTS.md recommends `--response-format ndjson` for "list-heavy analysis" but it doesn't work on the heaviest-output commands.

**Recommendation:** Add `--response-format ndjson` to all list-producing analysis commands, especially `keyframes`, `beats`, and `silence`.

### ISSUE-2: `keyframes` and `beats` Output Volume (Severity: Medium)

A ~4-minute video produces 388 keyframes and 473 beats. This consumes enormous agent context. Suggestions:
- Add a `--limit N` option to cap results
- Add a `--min-strength` filter for beats
- Consider summarizing keyframe intervals (e.g., "every ~0.6s") instead of listing all

### ISSUE-3: `audio-levels` Always Returns Per-Second Data (Severity: Low)

For a 232-second video, this produces 229 entries. The `--interval` option is available (per `frames --help`) but for audio-levels, the default 1-second interval is always used. An agent-facing summary (min, max, average, sections of notable change) would be more useful.

### ISSUE-4: No `--help` in JSON Format (Severity: Low)

Running `cutagent <command> --help` outputs human-formatted text (Rich/Click styled), which breaks the "all output is JSON" contract. While `schema command` exists as an alternative, an agent might naturally try `--help` first.

### ISSUE-5: Progress JSONL Mixed with Result JSON on Different Streams (Severity: Informational)

During `execute`, progress goes to stderr and the final result to stdout. This is actually well-designed for agents (parse stdout for result, optionally watch stderr for progress), but it's not documented in `capabilities`. The `progress_output` section does mention it but doesn't specify which stream.

---

## What Works Exceptionally Well

1. **`capabilities` command** — The single most valuable feature. It provides operation schemas, workflow guidance, recipes, quality checklists, and examples all in one structured response. An agent can go from zero knowledge to executing complex edits.

2. **Structured error recovery** — Every error includes specific, actionable recovery hints. The `TRIM_BEYOND_DURATION` error even includes the actual duration so the agent can immediately retry with correct values.

3. **EDL system** — Declarative, composable, validatable before execution. Named and positional references are intuitive. The ability to pipe via stdin or pass inline JSON eliminates temp file management.

4. **`op` command** — The payload-first single-operation workflow with `--dry-run` is perfect for agents that want to validate before mutating.

5. **`summarize` command** — Combines scene detection, silence detection, and suggested cut points into one call, saving the agent multiple round-trips.

6. **Keyframe proximity warnings** — When trimming with `codec: copy`, the warnings about non-keyframe-aligned cuts prevent silent quality issues.

7. **`doctor` command** — Proactive capability checking, including filter availability, before any work begins.

8. **`schema` introspection** — Runtime schema discovery means agents don't need pre-baked knowledge of the tool's API.

---

## Recommendation Summary

| Priority | Issue | Effort |
|----------|-------|--------|
| High | BUG-1: Fix exit codes for pre-execution errors | Low |
| Medium | ISSUE-1: Add `--fields`/`--response-format` to all analysis commands | Medium |
| Medium | ISSUE-2: Add `--limit`/`--min-strength` to reduce output volume | Low |
| Low | BUG-2: Validate EDL version field | Low |
| Low | BUG-3: Fix version comparison logic in doctor | Low |
| Low | BUG-4: Better error code for missing required options | Low |

---

## Test Environment

- macOS (darwin 25.3.0, Apple Silicon)
- Python 3.12
- FFmpeg 8.0.1 (Homebrew, missing `drawtext`/`subtitles` filters)
- CutAgent 0.3.0 (installed from source via `pip install -e "."`)
