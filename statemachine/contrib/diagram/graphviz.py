"""Run the Graphviz ``dot`` program and report its failures."""

import errno
import subprocess

from statemachine.exceptions import StateMachineError

GRAPHVIZ_DOWNLOAD_URL = "https://graphviz.org/download/"


class GraphvizError(StateMachineError):
    """Raised when the Graphviz ``dot`` program cannot run or fails to render a graph."""


class GraphvizNotFoundError(GraphvizError, FileNotFoundError):
    """Raised when the Graphviz program is not found in ``PATH``.

    Also a :class:`FileNotFoundError`, so ``except FileNotFoundError`` catches a missing
    Graphviz.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.errno = errno.ENOENT


def run_graphviz(dot_source: str, fmt: str, prog: str = "dot") -> bytes:
    """Render ``dot_source`` with Graphviz and return the output bytes.

    Args:
        dot_source: Graph in the DOT language.
        fmt: Graphviz output format, passed as ``-T<fmt>`` (``"svg"``, ``"png"``, ...).
        prog: Graphviz layout program to run, looked up on ``PATH``.

    Raises:
        GraphvizNotFoundError: If ``prog`` is not found in ``PATH``.
        GraphvizError: If ``prog`` cannot be run or exits with a non-zero code.
            The message carries what Graphviz wrote to stderr.
    """
    command = [prog, f"-T{fmt}"]
    try:
        completed = subprocess.run(
            command,
            input=dot_source.encode("utf-8"),
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as err:
        raise GraphvizNotFoundError(
            f"{prog!r} not found in PATH. Install Graphviz from {GRAPHVIZ_DOWNLOAD_URL} "
            "to generate diagrams."
        ) from err
    except OSError as err:
        raise GraphvizError(f"{prog!r} could not be run: {err}") from err

    if completed.returncode != 0:
        if completed.returncode < 0:
            message = f"{' '.join(command)} was terminated by signal {-completed.returncode}."
        else:
            message = f"{' '.join(command)} failed with exit code {completed.returncode}."
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        if stderr:
            message = f"{message}\n{stderr}"
        raise GraphvizError(message)

    return completed.stdout
