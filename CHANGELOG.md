# Changelog

All notable changes to CutAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-02-18

### Added

- Styling parity between `text` and `animate`: `animate` layers now support `bg_color`, `bg_padding`, `shadow_color`, `shadow_offset`, `stroke_color`, and `stroke_width` — the same styling properties available in `text`
- Shadow and stroke support on static `text` entries via `shadow_color`/`shadow_offset` and `stroke_color`/`stroke_width`
- `--entries-file` flag for `text` command — load text entries from a JSON file instead of an inline string
- `--layers-file` flag for `animate` command — load animation layers from a JSON file instead of an inline string
- `review_timestamps` field in `text` and `animate` JSON output — midpoint timestamps for each overlay, ready for use with `cutagent frames --at` to visually verify overlays
- `text_layers` summary field in `text` and `animate` JSON output — concise per-layer metadata for agent consumption
- `edl_compatible` field on every operation in `capabilities` output — agents can now know upfront which operations work in EDL
- `keyframe_t_note` in `capabilities` `animate` schema — clarifies that `t` is absolute timeline time, not relative to layer start
- Agent workflow step in `capabilities`: extract frames at `review_timestamps` after text/animate to visually verify overlays
- Sans-serif font auto-detection (`Arial`, `Helvetica Neue`, `DejaVu Sans`, `Liberation Sans`) as default font for text and animate overlays, replacing the previous monospace default

### Fixed

- EDL executor now correctly recognises and runs `AnimateOp` — previously raised `unknown operation type: AnimateOp`
- EDL validator now validates `AnimateOp` with full field and constraint checks (layer type, required fields, animatable properties, easing functions)

## [0.2.0] - 2026-02-17

### Added

- Animation operation (`animate`) — declarative keyframe-driven animations compiled to FFmpeg filter expressions
- Support for animated text layers with `x`, `y`, `opacity`, and `font_size` properties
- Support for animated image overlay layers with `x`, `y`, `opacity`, and `scale` properties
- Five easing functions: `linear`, `ease-in`, `ease-out`, `ease-in-out`, `spring` (damped oscillation)
- Multi-segment keyframe interpolation with piecewise easing
- New CLI command: `animate`
- Full integration into EDL engine, validation, and capabilities schema
- Text overlay operation (`text` / `add_text`) — burn titles, descriptions, and annotations onto video using FFmpeg's `drawtext` filter
- Seven position presets (center, top-center, bottom-center, top-left, top-right, bottom-left, bottom-right) plus custom `x,y` coordinates
- Timed text display with `start`/`end` fields and optional background boxes
- Multiple text entries per operation for layered overlays
- New CLI command: `text`
- Audio mix operation (`mix_audio`) — overlay background music onto a video's existing audio with adjustable mix level
- Volume adjustment operation (`volume`) — boost or reduce audio gain in dB
- Audio replacement operation (`replace_audio`) — swap a video's audio track with a different audio file
- Audio normalization operation (`normalize`) — EBU R128 loudness normalization via FFmpeg's `loudnorm` filter
- Beat detection analysis (`beats`) — detect musical beats/onsets for rhythm-aligned cutting, with BPM estimation
- New CLI commands: `mix`, `volume`, `replace-audio`, `normalize`, `beats`
- All audio operations are fully integrated into the EDL engine, validation, and capabilities schema
- Updated agent workflow in `capabilities` with audio-aware editing guidance

## [0.1.1] - 2026-02-15

### Fixed

- Crossfade (`xfade`) filter now works on FFmpeg 7.x — added explicit `fps` filter to enforce constant frame rate inputs required by `xfade` on older FFmpeg versions
- macOS CI now uses Homebrew for FFmpeg installation, fixing arm64 (Apple Silicon) compatibility with `macos-latest` runners

## [0.1.0] - 2025-02-15

### Added

- Core video operations: trim, split, concat, reorder, extract, fade
- Edit Decision List (EDL) engine with `$N` reference resolution
- Comprehensive media probing: metadata, keyframes, scene detection, silence detection, audio levels
- Unified `summarize` command for full content intelligence maps
- AI-native CLI with pure JSON output on all commands
- `capabilities` command for machine-readable operation schemas
- Dry-run EDL validation with detailed error reporting
- Structured error handling with error codes and recovery suggestions
- Keyframe alignment warnings for copy-codec cuts
- Crossfade transition support for concat operations
