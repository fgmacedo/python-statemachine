from dataclasses import dataclass
from dataclasses import field
from typing import Any

import pydot

from ..model import ActionType
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
    graph_attrs: dict[str, str] = field(default_factory=dict)
    node_attrs: dict[str, str] = field(default_factory=dict)
    edge_attrs: dict[str, str] = field(default_factory=dict)


class DotRenderer:
    """Renders a DiagramGraph into a pydot.Dot graph with UML-inspired styling.

    Uses techniques inspired by state-machine-cat for cleaner visual output:
    - HTML TABLE labels for states with UML compartments
    - plaintext nodes with near-transparent fill
    - Refined graph/node/edge defaults
    """

    def __init__(self, config: DotRendererConfig | None = None):
        self.config = config or DotRendererConfig()
        self._compound_ids: set[str] = set()
        self._compound_bidir_ids: set[str] = set()

    def render(self, graph: DiagramGraph) -> pydot.Dot:
        """Render a DiagramGraph to a pydot.Dot object."""
        self._compound_ids = graph.compound_state_ids
        self._compound_bidir_ids = graph.bidirectional_compound_ids
        dot = self._create_graph(graph.name)
        self._render_states(graph.states, graph.transitions, dot)
        return dot

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
            "ranksep": "0.3",
            "forcelabels": "true",
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
            "labeldistance": "1.5",
        }
        edge_defaults.update(cfg.edge_attrs)
        dot.set_edge_defaults(**edge_defaults)

        return dot

    def _state_node_id(self, state_id: str) -> str:
        """Get the node ID to use for edges. Compound states use an anchor node."""
        if state_id in self._compound_ids:
            return f"{state_id}_anchor"
        return state_id

    def _compound_edge_anchor(self, state_id: str, direction: str) -> str:
        """Return the appropriate anchor node ID for a compound ↔ other edge.

        Compound states that have both incoming and outgoing explicit transitions
        get separate ``_anchor_out`` / ``_anchor_in`` nodes so Graphviz can route
        the two directions through physically distinct points, avoiding overlap.
        """
        if state_id in self._compound_bidir_ids:
            return f"{state_id}_anchor_{direction}"
        return f"{state_id}_anchor"

    def _render_states(
        self,
        states: list[DiagramState],
        transitions: list[DiagramTransition],
        parent_graph: "pydot.Dot | pydot.Subgraph",
        extra_nodes: list[pydot.Node] | None = None,
    ) -> None:
        """Render states and transitions into the parent graph."""
        initial_state = next((s for s in states if s.is_initial), None)

        # The atomic subgraph groups all non-compound states and the inner
        # initial dot (when inside a compound cluster) so Graphviz places them
        # in the same rank region, keeping the initial arrow short.
        atomic_subgraph = pydot.Subgraph(
            graph_name=f"cluster___atomic_{id(parent_graph)}",
            label="",
            peripheries=0,
            margin=0,
            cluster="true",
        )
        has_atomic = False

        if initial_state:
            has_atomic = (
                self._render_initial_arrow(initial_state, parent_graph, atomic_subgraph)
                or has_atomic
            )

        for state in states:
            if state.type in (StateType.HISTORY_SHALLOW, StateType.HISTORY_DEEP):
                atomic_subgraph.add_node(self._create_history_node(state))
                has_atomic = True
            elif state.children:
                subgraph = self._create_compound_subgraph(state)
                anchor_nodes = self._create_compound_anchor_nodes(state)
                self._render_states(
                    state.children, transitions, subgraph, extra_nodes=anchor_nodes
                )
                parent_graph.add_subgraph(subgraph)
                # Add transitions originating from this compound state
                self._add_transitions_for_state(state, transitions, parent_graph)
            else:
                atomic_subgraph.add_node(self._create_atomic_node(state))
                has_atomic = True

        has_atomic = self._place_extra_nodes(
            extra_nodes, atomic_subgraph, parent_graph, has_atomic
        )

        if has_atomic:
            parent_graph.add_subgraph(atomic_subgraph)

        # Add transitions for atomic/history states
        for state in states:
            if not state.children:
                self._add_transitions_for_state(state, transitions, parent_graph)

    @staticmethod
    def _place_extra_nodes(
        extra_nodes: list[pydot.Node] | None,
        atomic_subgraph: pydot.Subgraph,
        parent_graph: "pydot.Dot | pydot.Subgraph",
        has_atomic: bool,
    ) -> bool:
        """Place anchor nodes from the parent compound into the graph.

        Co-locates them with real states when possible. If there are no atomic
        states at this level (e.g. a parallel state with only compound children),
        adds them directly to the parent graph to avoid an empty cluster.

        Returns the updated ``has_atomic`` flag.
        """
        if not extra_nodes:
            return has_atomic
        target = atomic_subgraph if has_atomic else parent_graph
        for node in extra_nodes:
            target.add_node(node)
        return has_atomic or (target is atomic_subgraph)

    def _render_initial_arrow(
        self,
        initial_state: DiagramState,
        parent_graph: "pydot.Dot | pydot.Subgraph",
        atomic_subgraph: pydot.Subgraph,
    ) -> bool:
        """Render the black-dot initial arrow pointing to ``initial_state``.

        Returns True if nodes were added to ``atomic_subgraph``.
        """
        initial_node_id = f"__initial_{id(parent_graph)}"
        initial_node = self._create_initial_node(initial_node_id)
        added_to_atomic = False

        extra: dict[str, Any] = {}
        if initial_state.children:
            extra["lhead"] = f"cluster_{initial_state.id}"

        if initial_state.children or isinstance(parent_graph, pydot.Dot):
            # Compound initial state, or top-level atomic initial state:
            # keep the dot in a plain wrapper subgraph attached to parent.
            wrapper = pydot.Subgraph(
                graph_name=f"{initial_node_id}_sg",
                label="",
                peripheries=0,
                margin=0,
            )
            wrapper.add_node(initial_node)
            parent_graph.add_subgraph(wrapper)
        else:
            # Inner (compound parent) with atomic initial state: add the
            # dot directly into the atomic cluster so it shares the same
            # rank region as the target state, avoiding a long arrow caused
            # by the compound cluster's anchor nodes pushing step1 further.
            atomic_subgraph.add_node(initial_node)
            added_to_atomic = True

        parent_graph.add_edge(
            pydot.Edge(
                initial_node_id,
                self._state_node_id(initial_state.id),
                label="",
                minlen=1,
                weight=100,
                **extra,
            )
        )
        return added_to_atomic

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

        All states use a native ``shape="rectangle"`` with ``style="rounded, filled"``
        so that Graphviz clips edges at the actual rounded border.  States with
        entry/exit actions embed an HTML TABLE (``border="0"``) inside the native
        shape to render UML-style compartments (name + separator + actions).
        """
        actions = [a for a in state.actions if a.type != ActionType.INTERNAL or a.body]
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
            # State with actions: native shape + HTML TABLE label (border=0).
            # The native shape handles edge clipping; the TABLE provides
            # UML compartment layout with <hr/> separator.
            label = self._build_html_table_label(state, actions)
            node = pydot.Node(
                state.id,
                label=f"<{label}>",
                shape="rectangle",
                style="rounded, filled",
                fontname=self.config.font_name,
                fontsize=self.config.state_font_size,
                fillcolor=fillcolor,
                penwidth=penwidth,
                margin="0",
                peripheries=2 if state.type == StateType.FINAL else 1,
            )

        return node

    def _build_html_table_label(
        self,
        state: DiagramState,
        actions: list[DiagramAction],
    ) -> str:
        """Build an HTML TABLE label with UML compartments (name | actions).

        The TABLE has ``border="0"`` because the visible border is drawn by
        the native Graphviz shape, ensuring edges are clipped correctly.
        """
        name = _escape_html(state.name)
        font_size = self.config.state_font_size
        action_font_size = self.config.transition_font_size

        action_lines = "<br/>".join(
            f'<font point-size="{action_font_size}">{_escape_html(self._format_action(a))}</font>'
            for a in actions
        )

        return (
            f'<table border="0" cellborder="0" cellspacing="0" cellpadding="0">'
            f'<tr><td cellpadding="4">'
            f'<font point-size="{font_size}">{name}</font>'
            f"</td></tr>"
            f"<hr/>"
            f'<tr><td align="left" cellpadding="6">'
            f"{action_lines}"
            f"</td></tr>"
            f"</table>"
        )

    @staticmethod
    def _format_action(action: DiagramAction) -> str:
        if action.type == ActionType.INTERNAL:
            return action.body
        return f"{action.type.value} / {action.body}"

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

    def _create_compound_anchor_nodes(self, state: DiagramState) -> list[pydot.Node]:
        """Create invisible anchor nodes for edge routing inside a compound cluster.

        These nodes are injected into the children's atomic_subgraph so they
        share the same layout row as the real states, avoiding blank space at
        the top of the compound cluster.
        """
        # For bidirectional compounds, all edges route through _anchor_in/_anchor_out;
        # the generic _anchor node is never used and would become an orphan that
        # Graphviz places arbitrarily, creating blank vertical space in the cluster.
        if state.id not in self._compound_bidir_ids:
            nodes = [
                pydot.Node(
                    f"{state.id}_anchor",
                    shape="point",
                    style="invis",
                    width=0,
                    height=0,
                    fixedsize="true",
                )
            ]
        else:
            nodes = []
            for direction in ("in", "out"):
                nodes.append(
                    pydot.Node(
                        f"{state.id}_anchor_{direction}",
                        shape="point",
                        style="invis",
                        width=0,
                        height=0,
                        fixedsize="true",
                    )
                )
        return nodes

    def _create_compound_subgraph(self, state: DiagramState) -> pydot.Subgraph:
        """Create a cluster subgraph for a compound/parallel state."""
        style = "rounded, solid"
        if state.is_parallel_area:
            style = "rounded, dashed"

        label = self._build_compound_label(state)

        return pydot.Subgraph(
            graph_name=f"cluster_{state.id}",
            label=f"<{label}>",
            style=style,
            cluster="true",
            penwidth="2.0",
            fontname=self.config.font_name,
            fontsize=self.config.state_font_size,
            margin="4",
        )

    def _build_compound_label(self, state: DiagramState) -> str:
        """Build HTML label for a compound/parallel subgraph."""
        name = _escape_html(state.name)
        if state.type == StateType.PARALLEL:
            return f"<b>{name}</b> &#9783;"

        actions = [a for a in state.actions if a.type != ActionType.INTERNAL or a.body]
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
        all_transitions: list[DiagramTransition],
        graph: "pydot.Dot | pydot.Subgraph",
    ) -> None:
        """Add edges for all non-internal transitions originating from this state."""
        for transition in all_transitions:
            if transition.source != state.id or transition.is_internal:
                continue
            # Skip implicit initial transitions — represented by the black-dot initial node.
            if transition.is_initial:
                continue
            for edge in self._create_edges(transition):
                graph.add_edge(edge)

    def _create_edges(self, transition: DiagramTransition) -> list[pydot.Edge]:
        """Create pydot.Edge objects for a transition."""
        target_ids: list[str | None] = list(transition.targets) if transition.targets else [None]

        cond = ", ".join(transition.guards)
        cond_html = f"<br/>[{_escape_html(cond)}]" if cond else ""

        return [
            self._create_single_edge(transition, target_id, i, cond_html)
            for i, target_id in enumerate(target_ids)
        ]

    def _create_single_edge(
        self,
        transition: DiagramTransition,
        target_id: str | None,
        index: int,
        cond_html: str,
    ) -> pydot.Edge:
        """Create a single pydot.Edge for one target of a transition."""
        src, dst, extra = self._resolve_edge_endpoints(transition, target_id)
        has_substates = bool(extra)
        html_label = self._build_edge_label(transition.event, cond_html, index)

        return pydot.Edge(
            src,
            dst,
            label=html_label,
            minlen=2 if has_substates else 1,
            **extra,
        )

    def _resolve_edge_endpoints(
        self,
        transition: DiagramTransition,
        target_id: str | None,
    ) -> "tuple[str, str, dict[str, Any]]":
        """Resolve source/destination node IDs and cluster attributes for an edge."""
        extra: dict[str, Any] = {}
        source_is_compound = transition.source in self._compound_ids
        target_is_compound = target_id is not None and target_id in self._compound_ids

        if source_is_compound:
            extra["ltail"] = f"cluster_{transition.source}"
        if target_is_compound:
            extra["lhead"] = f"cluster_{target_id}"

        dst = (
            self._state_node_id(target_id)
            if target_id is not None
            else self._state_node_id(transition.source)
        )
        src = self._state_node_id(transition.source)

        # For compound states in bidirectional pairs, route outgoing edges
        # through _anchor_out and incoming through _anchor_in so Graphviz
        # places them at different physical positions inside the cluster.
        if source_is_compound and transition.source in self._compound_bidir_ids:
            src = self._compound_edge_anchor(transition.source, "out")
            extra["ltail"] = f"cluster_{transition.source}"
        if target_is_compound and target_id in self._compound_bidir_ids:
            dst = self._compound_edge_anchor(target_id, "in")
            extra["lhead"] = f"cluster_{target_id}"

        return src, dst, extra

    def _build_edge_label(self, event: str, cond_html: str, index: int) -> str:
        """Build the HTML label for a transition edge."""
        event_text = _escape_html(event) if index == 0 else ""
        if not event_text and not (cond_html and index == 0):
            return ""

        label_content = f"{event_text}{cond_html}" if index == 0 else ""
        font_size = self.config.transition_font_size
        return (
            f'<<table border="0" cellborder="0" cellspacing="0" cellpadding="0">'
            f'<tr><td cellpadding="4">'
            f'<font point-size="{font_size}">{label_content}</font>'
            f"</td></tr>"
            f'<tr><td cellpadding="1"></td></tr>'
            f"</table>>"
        )
