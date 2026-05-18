"""Regression tests for issue #622: ``pydot`` must remain optional.

These tests run in a subprocess so we can install a strict import hook that
rejects ``pydot`` without contaminating the main test interpreter (where the
diagram test suite legitimately requires ``pydot``).
"""

import subprocess
import sys
import textwrap


def _run_without_pydot(script: str) -> subprocess.CompletedProcess:
    """Execute ``script`` in a fresh interpreter where importing ``pydot`` fails."""
    preamble = textwrap.dedent(
        """
        import builtins
        _real_import = builtins.__import__

        def _guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pydot" or name.startswith("pydot."):
                raise ModuleNotFoundError("No module named 'pydot'")
            return _real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = _guarded
        """
    )
    return subprocess.run(
        [sys.executable, "-c", preamble + script],
        capture_output=True,
        text=True,
        check=False,
    )


def test_define_statemachine_without_pydot():
    """Defining a StateMachine subclass must not import ``pydot``."""
    result = _run_without_pydot(
        textwrap.dedent(
            """
            from statemachine import State, StateMachine

            class TrafficLight(StateMachine):
                'Light that cycles through colors.'
                green = State(initial=True)
                yellow = State()
                red = State(final=True)
                cycle = green.to(yellow) | yellow.to(red)

            import sys
            assert "pydot" not in sys.modules, "pydot was imported transitively"
            print("OK")
            """
        )
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_define_statechart_without_pydot():
    """Defining a StateChart subclass must not import ``pydot`` either."""
    result = _run_without_pydot(
        textwrap.dedent(
            """
            from statemachine import State
            from statemachine.statemachine import StateChart

            class Workflow(StateChart):
                'Workflow with a docstring but no statechart placeholder.'
                draft = State(initial=True)
                published = State(final=True)
                publish = draft.to(published)

            import sys
            assert "pydot" not in sys.modules
            print("OK")
            """
        )
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_mermaid_format_without_pydot():
    """The ``mermaid`` / ``md`` / ``rst`` formats must work without ``pydot``."""
    result = _run_without_pydot(
        textwrap.dedent(
            """
            from statemachine import State, StateMachine

            class TrafficLight(StateMachine):
                green = State(initial=True)
                red = State(final=True)
                stop = green.to(red)

            mermaid = format(TrafficLight, "mermaid")
            assert "stateDiagram-v2" in mermaid, mermaid

            md = format(TrafficLight, "md")
            assert "| State" in md, md

            import sys
            assert "pydot" not in sys.modules
            print("OK")
            """
        )
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_dot_format_requires_pydot_with_clear_error():
    """``dot``/``svg`` formats still need ``pydot``; the error should surface clearly."""
    result = _run_without_pydot(
        textwrap.dedent(
            """
            from statemachine import State, StateMachine

            class TrafficLight(StateMachine):
                green = State(initial=True)
                red = State(final=True)
                stop = green.to(red)

            try:
                format(TrafficLight, "dot")
            except ModuleNotFoundError as exc:
                assert "pydot" in str(exc), exc
                print("OK")
            else:
                raise AssertionError("Expected ModuleNotFoundError for dot format")
            """
        )
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
