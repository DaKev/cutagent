import sys

import click
import typer

from cutagent.cli.analysis import app as analysis_app
from cutagent.cli.agent import app as agent_app
from cutagent.cli.audio import app as audio_app
from cutagent.cli.editing import app as editing_app
from cutagent.cli.execution import app as execution_app
from cutagent.cli.system import app as system_app
from cutagent.cli.utils import json_error, json_out
from cutagent.cli.visual import app as visual_app
from cutagent.errors import EXIT_SYSTEM, EXIT_VALIDATION, CutAgentError

app = typer.Typer(
    name="cutagent",
    help="Agent-first video cutting — all output is JSON",
    add_completion=False,
)

# Merge all commands into the main app
# We use add_typer without a name to keep commands at the top level
app.add_typer(system_app, name="")
app.add_typer(agent_app, name="")
app.add_typer(analysis_app, name="")
app.add_typer(editing_app, name="")
app.add_typer(visual_app, name="")
app.add_typer(audio_app, name="")
app.add_typer(execution_app, name="")


def _usage_error_payload(exc: click.ClickException) -> dict[str, object]:
    """Convert Click/Typer usage errors into structured JSON."""
    if isinstance(exc, click.MissingParameter):
        option = None
        if exc.param is not None and getattr(exc.param, "opts", None):
            # Prefer the long option name users can copy/paste.
            long_opts = [opt for opt in exc.param.opts if opt.startswith("--")]
            option = long_opts[-1] if long_opts else exc.param.opts[-1]
        label = option or getattr(exc.param, "name", None) or "required argument"
        return {
            "error": True,
            "code": "MISSING_FIELD",
            "message": str(exc),
            "recovery": [f"Provide required option {label}" if option else "Provide the missing required field"],
            "context": {"missing": label},
        }
    return {
        "error": True,
        "code": "INVALID_ARGUMENT",
        "message": str(exc),
        "recovery": ["Run with --help to inspect required arguments and options"],
        "context": {},
    }


def main() -> None:
    """CLI entry point."""
    try:
        result = app(standalone_mode=False)
        if isinstance(result, int):
            sys.exit(result)
        sys.exit(0)
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except click.ClickException as exc:
        sys.exit(json_out(_usage_error_payload(exc), EXIT_VALIDATION))
    except CutAgentError as exc:
        sys.exit(json_error(exc))
    except Exception as exc:
        # typer handles SystemExit
        if isinstance(exc, SystemExit):
            raise
        sys.exit(json_out({
            "error": True,
            "code": "UNEXPECTED_ERROR",
            "message": str(exc),
            "recovery": ["This is an unexpected error — please report it"],
        }, EXIT_SYSTEM))

if __name__ == "__main__":
    main()
