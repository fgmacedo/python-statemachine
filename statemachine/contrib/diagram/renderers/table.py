from ..model import DiagramGraph
from ..model import DiagramState
from ..model import DiagramTransition


class TransitionTableRenderer:
    """Renders a DiagramGraph as a transition table in markdown or RST format."""

    def render(self, graph: DiagramGraph, fmt: str = "md") -> str:
        """Render the transition table.

        Args:
            graph: The diagram IR to render.
            fmt: Output format — ``"md"`` for markdown, ``"rst"`` for reStructuredText.

        Returns:
            The formatted transition table as a string.
        """
        rows = self._collect_rows(graph.states, graph.transitions)

        if fmt == "rst":
            return self._render_rst(rows)
        return self._render_md(rows)

    def _collect_rows(
        self,
        states: list[DiagramState],
        transitions: list[DiagramTransition],
    ) -> "list[tuple[str, str, str, str]]":
        """Collect (State, Event, Guard, Target) tuples from the IR."""
        rows: list[tuple[str, str, str, str]] = []
        state_names = self._build_state_name_map(states)

        for t in transitions:
            if t.is_initial or t.is_internal:
                continue

            source_name = state_names.get(t.source, t.source)
            guard = ", ".join(t.guards) if t.guards else ""
            event = t.event or ""

            if t.targets:
                for target_id in t.targets:
                    target_name = state_names.get(target_id, target_id)
                    rows.append((source_name, event, guard, target_name))
            else:
                rows.append((source_name, event, guard, source_name))

        return rows

    def _build_state_name_map(self, states: list[DiagramState]) -> dict:
        """Build a mapping from state ID to display name, recursively."""
        result: dict = {}
        for state in states:
            result[state.id] = state.name
            if state.children:
                result.update(self._build_state_name_map(state.children))
        return result

    def _render_md(self, rows: "list[tuple[str, str, str, str]]") -> str:
        """Render as a markdown table."""
        headers = ("State", "Event", "Guard", "Target")
        col_widths = [len(h) for h in headers]

        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))

        def _fmt_row(cells: "tuple[str, ...]") -> str:
            parts = [cell.ljust(col_widths[i]) for i, cell in enumerate(cells)]
            return "| " + " | ".join(parts) + " |"

        lines = [_fmt_row(headers)]
        lines.append("| " + " | ".join("-" * w for w in col_widths) + " |")
        for row in rows:
            lines.append(_fmt_row(row))

        return "\n".join(lines) + "\n"

    def _render_rst(self, rows: "list[tuple[str, str, str, str]]") -> str:
        """Render as an RST grid table."""
        headers = ("State", "Event", "Guard", "Target")
        col_widths = [len(h) for h in headers]

        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))

        def _border(char: str = "-") -> str:
            return "+" + "+".join(char * (w + 2) for w in col_widths) + "+"

        def _data_row(cells: "tuple[str, ...]") -> str:
            parts = [f" {cell.ljust(col_widths[i])} " for i, cell in enumerate(cells)]
            return "|" + "|".join(parts) + "|"

        lines = [_border("-")]
        lines.append(_data_row(headers))
        lines.append(_border("="))
        for row in rows:
            lines.append(_data_row(row))
            lines.append(_border("-"))

        return "\n".join(lines) + "\n"
