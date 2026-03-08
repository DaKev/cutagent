import sys

import typer

from cutagent.cli.analysis import app as analysis_app
from cutagent.cli.agent import app as agent_app
from cutagent.cli.audio import app as audio_app
from cutagent.cli.editing import app as editing_app
from cutagent.cli.execution import app as execution_app
from cutagent.cli.system import app as system_app
from cutagent.cli.utils import json_error, json_out
from cutagent.cli.visual import app as visual_app
from cutagent.errors import EXIT_SYSTEM, CutAgentError

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

def main() -> None:
    """CLI entry point."""
    try:
        app(standalone_mode=False)
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except CutAgentError as exc:
        sys.exit(json_error(exc, EXIT_SYSTEM))
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
