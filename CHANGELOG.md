# Changelog

All notable changes to CutAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
