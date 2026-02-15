# Contributing to CutAgent

Thank you for your interest in contributing to CutAgent! This project aims to be the best AI-agent-first tool for professional video cutting, and community contributions are essential to that mission.

## Getting Started

### Prerequisites

- Python 3.10+
- FFmpeg and FFprobe on your `$PATH`
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/DaKev/cutagent.git
cd cutagent

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in development mode with test dependencies
pip install -e ".[dev]"

# Verify everything works
pytest
```

## How to Contribute

### Reporting Bugs

Open a [bug report](../../issues/new?template=bug_report.md) with:

- CutAgent version (`cutagent capabilities | python -c "import sys,json; print(json.load(sys.stdin)['version'])"`)
- FFmpeg version (`ffmpeg -version | head -1`)
- Python version (`python --version`)
- Steps to reproduce
- Expected vs actual behavior

### Suggesting Features

Open a [feature request](../../issues/new?template=feature_request.md). Since CutAgent is **agent-first**, consider:

- How would an AI agent use this feature?
- What JSON input/output would the CLI produce?
- Does it fit the declarative EDL model?

### Submitting Code

1. **Fork** the repository
2. **Create a branch** from `main`: `git checkout -b feature/your-feature`
3. **Make your changes** following the guidelines below
4. **Add tests** for any new functionality
5. **Run the test suite**: `pytest`
6. **Commit** with a clear message (see [Commit Messages](#commit-messages))
7. **Push** and open a Pull Request

## Development Guidelines

### Architecture Principles

CutAgent has a layered architecture. Please respect these boundaries:

```
cli.py          → CLI parsing, JSON output (no business logic)
engine.py       → EDL parsing and execution orchestration
operations.py   → Individual video operations (trim, split, concat, etc.)
probe.py        → Media inspection and content intelligence
models.py       → Data models, all JSON-serializable
validation.py   → Dry-run EDL validation
ffmpeg.py       → Low-level FFmpeg/FFprobe subprocess wrappers
errors.py       → Error codes and structured error handling
```

- **`ffmpeg.py`** is the only module that spawns subprocesses
- **`models.py`** has no dependencies on other CutAgent modules
- **`errors.py`** has no dependencies on other CutAgent modules
- All public functions return typed dataclasses, never raw dicts
- The CLI outputs JSON only — no human-formatted text

### Code Style

- Keep files under 300 lines. Refactor if approaching that limit.
- Use type hints on all public function signatures.
- Write docstrings for all public functions (Google style).
- No runtime dependencies beyond the Python standard library — FFmpeg is the only external tool.

### Testing

- Tests live in `tests/` and use `pytest`.
- Test fixtures that create video files are in `tests/conftest.py`.
- Integration tests require FFmpeg on `$PATH`.
- Aim for tests that cover both success paths and error cases.

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_operations.py

# Run with verbose output
pytest -v
```

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add speed change operation

fix: handle empty keyframe list in trim warnings

docs: add EDL format examples to README

test: add crossfade concat edge case tests
```

Prefixes: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

### JSON Output Contract

Every CLI command outputs a JSON object to stdout. When adding or modifying commands:

- Success responses must include the relevant data fields
- Error responses must include `error: true`, `code`, `message`, and `recovery` fields
- Never print non-JSON output to stdout (logs go to stderr)
- Use exit codes: 0 (success), 1 (validation), 2 (execution), 3 (system)

### EDL Operations

When adding a new operation type:

1. Add a dataclass in `models.py` with `to_dict()` and `from_dict()`
2. Register it in `OPERATION_TYPES` in `models.py`
3. Implement the operation in `operations.py`
4. Add execution handling in `engine.py` (`_execute_operation`)
5. Add validation in `validation.py`
6. Add a CLI subcommand in `cli.py`
7. Add the capability schema in `cmd_capabilities`
8. Add tests for the operation, engine integration, and validation

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold a welcoming, inclusive community.

## License

By contributing to CutAgent, you agree that your contributions will be licensed under the [MIT License](LICENSE).
