from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

import pydot

from ..model import DiagramAction
from ..model import DiagramGraph
from ..model import DiagramState
from ..model import DiagramTransition
from ..model import StateType


def _escape_html(text: str) -> str:
    """Escape text for use inside HTML labels."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class DotRendererConfig:
    """Configuration for the DOT renderer, matching DotGraphMachine's class attributes."""

    graph_rankdir: str = "LR"
    font_name: str = "Helvetica"
    state_font_size: str = "12"
    state_active_penwidth: int = 2
    state_active_fillcolor: str = "turquoise"
    transition_font_size: str = "10"
    graph_attrs: Dict[str, str] = field(default_factory=dict)
    node_attrs: Dict[str, str] = field(default_factory=dict)
    edge_attrs: Dict[str, str] = field(default_factory=dict)


class DotRenderer:
    """Renders a DiagramGraph into a pydot.Dot graph with UML-inspired styling.

    Uses techniques inspired by state-machine-cat for cleaner visual output:
    - HTML TABLE labels for states with UML compartments
    - plaintext nodes with near-transparent fill
    - Refined graph/node/edge defaults
    """

    def __init__(self, config: Optional[DotRendererConfig] = None):
        self.config = config or DotRendererConfig()
        self._compound_ids: Set[str] = set()

    def render(self, graph: DiagramGraph) -> pydot.Dot:
        """Render a DiagramGraph to a pydot.Dot object."""
        self._collect_compound_ids(graph.states)
        dot = self._create_graph(graph.name)
        self._render_states(graph.states, graph.transitions, dot)
        return dot

    def _collect_compound_ids(self, states: List[DiagramState]) -> None:
        """Pre-collect IDs of states that have children (compound/parallel)."""
        for state in states:
            if state.children:
                self._compound_ids.add(state.id)
            self._collect_compound_ids(state.children)

    def _create_graph(self, name: str) -> pydot.Dot:
        cfg = self.config
        graph_attrs = {
            "fontname": cfg.font_name,
            "fontsize": cfg.state_font_size,
            "penwidth": "2.0",
            "splines": "true",
            "ordering": "out",
            "compound": "true",
            "nodesep": "0.3",
            "ranksep": "0.1",
        }
        graph_attrs.update(cfg.graph_attrs)

        dot = pydot.Dot(
            name,
            graph_type="digraph",
            label=name,
            rankdir=cfg.graph_rankdir,
            **graph_attrs,
        )

        # Set default node attributes
        node_defaults = {
            "fontname": cfg.font_name,
            "fontsize": cfg.state_font_size,
            "penwidth": "2.0",
        }
        node_defaults.update(cfg.node_attrs)
        dot.set_node_defaults(**node_defaults)

        # Set default edge attributes
        edge_defaults = {
            "fontname": cfg.font_name,
            "fontsize": cfg.transition_font_size,
        }
        edge_defaults.update(cfg.edge_attrs)
        dot.set_edge_defaults(**edge_defaults)

        return dot

    def _state_node_id(self, state_id: str) -> str:
        """Get the node ID to use for edges. Compound states use an anchor node."""
        if state_id in self._compound_ids:
            return f"{state_id}_anchor"
        return state_id

    def _render_states(
        self,
        states: List[DiagramState],
        transitions: List[DiagramTransition],
        parent_graph: "pydot.Dot | pydot.Subgraph",
    ) -> None:
        """Render states and transitions into the parent graph."""
        # Create initial node for this level
        initial_state = next((s for s in states if self._is_initial_candidate(s, states)), None)

        if initial_state:
            initial_node_id = f"__initial_{id(parent_graph)}"
            initial_node = self._create_initial_node(initial_node_id)
            initial_subgraph = pydot.Subgraph(
                graph_name=f"{initial_node_id}_sg",
                label="",
                peripheries=0,
                margin=0,
            )
            initial_subgraph.add_node(initial_node)
            parent_graph.add_subgraph(initial_subgraph)

            extra = {}
            if initial_state.children:
                extra["lhead"] = f"cluster_{initial_state.id}"
            parent_graph.add_edge(
                pydot.Edge(
                    initial_node_id,
                    self._state_node_id(initial_state.id),
                    label="",
                    **extra,
                )
            )

        # Separate compound vs atomic states
        atomic_subgraph = pydot.Subgraph(
            graph_name=f"cluster___atomic_{id(parent_graph)}",
            label="",
            peripheries=0,
            cluster="true",
        )

        has_atomic = False
        for state in states:
            if state.type in (StateType.HISTORY_SHALLOW, StateType.HISTORY_DEEP):
                atomic_subgraph.add_node(self._create_history_node(state))
                has_atomic = True
            elif state.children:
                subgraph = self._create_compound_subgraph(state)
                self._render_states(state.children, transitions, subgraph)
                parent_graph.add_subgraph(subgraph)
                # Add transitions originating from this compound state
                self._add_transitions_for_state(state, transitions, parent_graph)
            else:
                atomic_subgraph.add_node(self._create_atomic_node(state))
                has_atomic = True

        if has_atomic:
            parent_graph.add_subgraph(atomic_subgraph)

        # Add transitions for atomic/history states
        for state in states:
            if not state.children:
                self._add_transitions_for_state(state, transitions, parent_graph)

    def _is_initial_candidate(self, state: DiagramState, siblings: List[DiagramState]) -> bool:
        """Check if this state should get an initial arrow."""
        # History states and parallel areas don't get initial arrows at this level
        if state.type in (StateType.HISTORY_SHALLOW, StateType.HISTORY_DEEP):
            return False
        # For parallel states, don't show initial arrows
        parent_is_parallel = any(s.type == StateType.PARALLEL for s in siblings if s is not state)
        if parent_is_parallel:
            return False
        # Check if any state in the list is marked as initial
        # We rely on document order (first state) as a fallback
        return state is siblings[0] if siblings else False

    def _create_initial_node(self, node_id: str) -> pydot.Node:
        return pydot.Node(
            node_id,
            label="",
            shape="circle",
            style="filled",
            fillcolor="black",
            color="black",
            fixedsize="true",
            width=0.15,
            height=0.15,
            penwidth="0",
        )

    def _create_atomic_node(self, state: DiagramState) -> pydot.Node:
        """Create a node for an atomic state.

        States without actions use a native rounded rectangle.
        States with actions use an HTML TABLE label with UML compartments
        (name + separator + actions), inspired by state-machine-cat.
        """
        actions = [a for a in state.actions if a.type != "internal" or a.body]
        fillcolor = self.config.state_active_fillcolor if state.is_active else "white"
        penwidth = self.config.state_active_penwidth if state.is_active else 2

        if not actions:
            # Simple state: native rounded rectangle
            node = pydot.Node(
                state.id,
                label=state.name,
                shape="rectangle",
                style="rounded, filled",
                fontname=self.config.font_name,
                fontsize=self.config.state_font_size,
                fillcolor=fillcolor,
                penwidth=penwidth,
                peripheries=2 if state.type == StateType.FINAL else 1,
            )
        else:
            # State with actions: HTML TABLE with UML compartments
            label = self._build_html_table_label(state, actions, fillcolor, penwidth)
            node = pydot.Node(
                state.id,
                label=f"<{label}>",
                shape="plaintext",
                fontname=self.config.font_name,
                fontsize=self.config.state_font_size,
            )

        return node

    def _build_html_table_label(
        self,
        state: DiagramState,
        actions: List[DiagramAction],
        fillcolor: str,
        penwidth: int,
    ) -> str:
        """Build an HTML TABLE label with UML compartments (name | actions)."""
        name = _escape_html(state.name)
        font_size = self.config.state_font_size
        action_font_size = self.config.transition_font_size

        peripheries_border = (
            '<table align="center" cellborder="0" cellspacing="0" border="0"'
            ' cellpadding="2" style="rounded"><tr><td>'
            if state.type == StateType.FINAL
            else ""
        )
        peripheries_border_close = "</td></tr></table>" if state.type == StateType.FINAL else ""

        action_rows = "".join(
            f'<tr><td align="left" cellpadding="2">'
            f'<font point-size="{action_font_size}">'
            f"{_escape_html(self._format_action(a))}"
            f"</font></td></tr>"
            for a in actions
        )

        return (
            f"{peripheries_border}"
            f'<table align="center" cellborder="0" cellspacing="0"'
            f' border="{penwidth}" style="rounded" bgcolor="{fillcolor}">'
            f'<tr><td cellpadding="7">'
            f'<font point-size="{font_size}">{name}</font>'
            f"</td></tr>"
            f"<hr/>"
            f"{action_rows}"
            f"</table>"
            f"{peripheries_border_close}"
        )

    @staticmethod
    def _format_action(action: DiagramAction) -> str:
        if action.type == "internal":
            return action.body
        return f"{action.type} / {action.body}"

    def _create_history_node(self, state: DiagramState) -> pydot.Node:
        label = "H*" if state.type == StateType.HISTORY_DEEP else "H"
        return pydot.Node(
            state.id,
            label=label,
            shape="circle",
            style="filled",
            fillcolor="white",
            fontname=self.config.font_name,
            fontsize="8pt",
            fixedsize="true",
            width=0.3,
            height=0.3,
        )

    def _create_compound_subgraph(self, state: DiagramState) -> pydot.Subgraph:
        """Create a cluster subgraph for a compound/parallel state."""
        style = "rounded, solid"
        if state.is_parallel_area:
            style = "rounded, dashed"

        label = self._build_compound_label(state)

        subgraph = pydot.Subgraph(
            graph_name=f"cluster_{state.id}",
            label=f"<{label}>",
            style=style,
            cluster="true",
            penwidth="2.0",
            fontname=self.config.font_name,
            fontsize=self.config.state_font_size,
        )

        # Add invisible anchor node for edge routing
        subgraph.add_node(
            pydot.Node(
                f"{state.id}_anchor",
                shape="point",
                style="invis",
                width=0,
                height=0,
                fixedsize="true",
            )
        )

        return subgraph

    def _build_compound_label(self, state: DiagramState) -> str:
        """Build HTML label for a compound/parallel subgraph."""
        name = _escape_html(state.name)
        if state.type == StateType.PARALLEL:
            return f"<b>{name}</b> &#9783;"

        actions = [a for a in state.actions if a.type != "internal" or a.body]
        if not actions:
            return f"<b>{name}</b>"

        rows = [f"<b>{name}</b>"]
        for action in actions:
            action_text = _escape_html(self._format_action(action))
            rows.append(
                f'<font point-size="{self.config.transition_font_size}">{action_text}</font>'
            )
        return "<br/>".join(rows)

    def _add_transitions_for_state(
        self,
        state: DiagramState,
        all_transitions: List[DiagramTransition],
        graph: "pydot.Dot | pydot.Subgraph",
    ) -> None:
        """Add edges for all non-internal transitions originating from this state."""
        for transition in all_transitions:
            if transition.source != state.id or transition.is_internal:
                continue
            for edge in self._create_edges(transition):
                graph.add_edge(edge)

    def _create_edges(self, transition: DiagramTransition) -> List[pydot.Edge]:
        """Create pydot.Edge objects for a transition."""
        target_ids: List[Optional[str]] = (
            list(transition.targets) if transition.targets else [None]
        )

        cond = ", ".join(transition.guards)
        if cond:
            cond = f"\n[{cond}]"

        edges = []
        for i, target_id in enumerate(target_ids):
            extra: Dict[str, str] = {}
            source_is_compound = transition.source in self._compound_ids
            target_is_compound = target_id is not None and target_id in self._compound_ids

            if source_is_compound:
                extra["ltail"] = f"cluster_{transition.source}"
            if target_is_compound:
                extra["lhead"] = f"cluster_{target_id}"

            has_substates = source_is_compound or target_is_compound
            label = f"{transition.event}{cond}" if i == 0 else ""

            if target_id is not None:
                dst = self._state_node_id(target_id)
            else:
                dst = self._state_node_id(transition.source)

            edges.append(
                pydot.Edge(
                    self._state_node_id(transition.source),
                    dst,
                    label=label,
                    minlen=2 if has_substates else 1,
                    **extra,
                )
            )

        return edges
