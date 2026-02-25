import json
import sys
from pathlib import Path
from typing import Callable, Optional

import typer

from cutagent.cli.utils import json_error, json_out
from cutagent.errors import EXIT_EXECUTION, EXIT_SUCCESS, EXIT_VALIDATION, CutAgentError

app = typer.Typer(help="EDL Execution and Validation")

def _read_edl_input(edl_arg: str | None = None, edl_json: str | None = None) -> str:
    """Read EDL from inline JSON, stdin (if '-'), or from a file path."""
    if edl_json:
        return edl_json
    if edl_arg is None:
        raise CutAgentError(
            code="MISSING_FIELD",
            message="No EDL provided — pass a file path, use '-' for stdin, or use --edl-json",
            recovery=["Provide an EDL file path", "Use '-' to read from stdin", "Use --edl-json '{...}'"],
        )
    if edl_arg == "-":
        return sys.stdin.read()
    try:
        return Path(edl_arg).read_text()
    except FileNotFoundError:
        raise FileNotFoundError(f"EDL file not found: {edl_arg}")

def _make_progress_callback(quiet: bool) -> Callable[[int, int, str, str], None] | None:
    """Return a progress callback that writes JSONL to stderr, or None if quiet."""
    if quiet:
        return None

    def _progress(step: int, total: int, op_name: str, status: str) -> None:
        line = json.dumps({"progress": {"step": step, "total": total, "op": op_name, "status": status}})
        print(line, file=sys.stderr, flush=True)

    return _progress

@app.command("validate")
def cmd_validate(
    edl: Optional[str] = typer.Argument(None, help="Path to the EDL JSON file (or '-' for stdin)"),
    edl_json: Optional[str] = typer.Option(None, "--edl-json", help="Inline EDL JSON string"),
) -> int:
    """Validate an EDL without executing."""
    from cutagent.validation import validate_edl
    try:
        edl_text = _read_edl_input(edl, edl_json)
        result = validate_edl(edl_text)
        code = EXIT_SUCCESS if result.valid else EXIT_VALIDATION
        return json_out(result.to_dict(), code)
    except CutAgentError as exc:
        return json_error(exc, EXIT_VALIDATION)
    except FileNotFoundError:
        return json_out({
            "error": True, "code": "INPUT_NOT_FOUND",
            "message": f"EDL file not found: {edl}",
            "recovery": ["Check the file path, or use '-' to read from stdin, or use --edl-json"],
        }, EXIT_VALIDATION)

@app.command("execute")
def cmd_execute(
    edl: Optional[str] = typer.Argument(None, help="Path to the EDL JSON file (or '-' for stdin)"),
    edl_json: Optional[str] = typer.Option(None, "--edl-json", help="Inline EDL JSON string"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress progress output on stderr"),
) -> int:
    """Execute an EDL."""
    from cutagent.engine import execute_edl
    try:
        edl_text = _read_edl_input(edl, edl_json)
        callback = _make_progress_callback(quiet)
        result = execute_edl(edl_text, progress_callback=callback)
        return json_out(result.to_dict())
    except CutAgentError as exc:
        return json_error(exc, EXIT_EXECUTION)
    except FileNotFoundError:
        return json_out({
            "error": True, "code": "INPUT_NOT_FOUND",
            "message": f"EDL file not found: {edl}",
            "recovery": ["Check the file path, or use '-' to read from stdin, or use --edl-json"],
        }, EXIT_VALIDATION)
