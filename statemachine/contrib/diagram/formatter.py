"""Unified facade for rendering state machines in multiple text formats.

The :class:`Formatter` class provides a decorator-based registry where each
renderer declares the format names it handles.  Adding a new format only
requires writing a renderer function and decorating it — no changes to
``__format__``, ``factory.py``, or ``statemachine.py``.

A module-level :data:`formatter` instance is the single public entry point::

    from statemachine.contrib.diagram import formatter

    print(formatter.render(sm, "mermaid"))

    @formatter.register_format("plantuml")
    def _render_plantuml(machine):
        ...
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TypeAlias

    from statemachine.statemachine import StateChart

    MachineRef: TypeAlias = StateChart | type[StateChart]


class Formatter:
    """Unified facade for rendering state machines in multiple text formats."""

    def __init__(self) -> None:
        self._formats: dict[str, "Callable[[MachineRef], str]"] = {}

    def register_format(
        self, *names: str
    ) -> "Callable[[Callable[[MachineRef], str]], Callable[[MachineRef], str]]":
        """Decorator factory that registers a renderer under one or more format names.

        Usage::

            @formatter.register_format("md", "markdown")
            def _render_md(machine_or_class):
                ...
        """

        def decorator(
            fn: "Callable[[MachineRef], str]",
        ) -> "Callable[[MachineRef], str]":
            for name in names:
                self._formats[name] = fn
            return fn

        return decorator

    def render(self, machine_or_class: "MachineRef", fmt: str) -> str:
        """Render a state machine in the given text format.

        Args:
            machine_or_class: A ``StateChart`` instance or class.
            fmt: Format name (e.g., ``"mermaid"``, ``"dot"``, ``"md"``).
                Empty string falls back to ``repr()``.

        Raises:
            ValueError: If ``fmt`` is not registered.
        """
        if fmt == "":
            return repr(machine_or_class)

        renderer_fn = self._formats.get(fmt)
        if renderer_fn is None:
            primary = sorted({self._primary_name(fn) for fn in set(self._formats.values())})
            raise ValueError(
                f"Unsupported format: {fmt!r}. Use {', '.join(repr(n) for n in primary)}."
            )
        return renderer_fn(machine_or_class)

    def supported_formats(self) -> list[str]:
        """Return sorted list of all registered format names (including aliases)."""
        return sorted(self._formats)

    def _primary_name(self, fn: "Callable[[MachineRef], str]") -> str:
        """Return the first registered name for a given renderer function."""
        for name, registered_fn in self._formats.items():
            if registered_fn is fn:
                return name
        return "?"  # pragma: no cover


formatter = Formatter()
"""Module-level :class:`Formatter` instance — the single public entry point."""


# ---------------------------------------------------------------------------
# Built-in format registrations
# ---------------------------------------------------------------------------


@formatter.register_format("dot")
def _render_dot(machine_or_class: "MachineRef") -> str:
    from statemachine.contrib.diagram import DotGraphMachine

    return DotGraphMachine(machine_or_class).get_graph().to_string()  # type: ignore[no-any-return]


@formatter.register_format("svg")
def _render_svg(machine_or_class: "MachineRef") -> str:
    from statemachine.contrib.diagram import DotGraphMachine

    svg_bytes: bytes = DotGraphMachine(machine_or_class).get_graph().create_svg()  # type: ignore[attr-defined]
    return svg_bytes.decode("utf-8")


@formatter.register_format("mermaid")
def _render_mermaid(machine_or_class: "MachineRef") -> str:
    from statemachine.contrib.diagram import MermaidGraphMachine

    return MermaidGraphMachine(machine_or_class).get_mermaid()


@formatter.register_format("md", "markdown")
def _render_md(machine_or_class: "MachineRef") -> str:
    from statemachine.contrib.diagram.extract import extract
    from statemachine.contrib.diagram.renderers.table import TransitionTableRenderer

    return TransitionTableRenderer().render(extract(machine_or_class), fmt="md")


@formatter.register_format("rst")
def _render_rst(machine_or_class: "MachineRef") -> str:
    from statemachine.contrib.diagram.extract import extract
    from statemachine.contrib.diagram.renderers.table import TransitionTableRenderer

    return TransitionTableRenderer().render(extract(machine_or_class), fmt="rst")
