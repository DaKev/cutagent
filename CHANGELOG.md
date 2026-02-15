# Changelog

All notable changes to CutAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
