from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from ..model import ActionType
from ..model import DiagramAction
from ..model import DiagramGraph
from ..model import DiagramState
from ..model import DiagramTransition
from ..model import StateType


@dataclass
class MermaidRendererConfig:
    """Configuration for the Mermaid renderer."""

    direction: str = "LR"
    active_fill: str = "#40E0D0"
    active_stroke: str = "#333"


class MermaidRenderer:
    """Renders a DiagramGraph into a Mermaid stateDiagram-v2 source string.

    Mermaid's stateDiagram-v2 has a rendering bug where transitions whose source
    or target is a compound state (``state X { ... }``) inside a parallel region
    crash with ``Cannot set properties of undefined (setting 'rank')``.  To work
    around this, the renderer rewrites compound-state endpoints to cross the
    boundary:

    - Transition **to** a compound → redirected to its initial child.
    - Transition **from** a compound → redirected from its initial child.

    This is applied universally (not only inside parallel regions) for simplicity
    and consistency — the visual effect is equivalent.
    """

    def __init__(self, config: Optional[MermaidRendererConfig] = None):
        self.config = config or MermaidRendererConfig()
        self._active_ids: List[str] = []
        self._rendered_transitions: Set[tuple] = set()
        self._compound_ids: Set[str] = set()
        self._initial_child_map: Dict[str, str] = {}

    def render(self, graph: DiagramGraph) -> str:
        """Render a DiagramGraph to a Mermaid stateDiagram-v2 string."""
        self._active_ids = []
        self._rendered_transitions = set()
        self._compound_ids = graph.compound_state_ids
        self._initial_child_map = self._build_initial_child_map(graph.states)

        lines: List[str] = []
        lines.append("stateDiagram-v2")
        lines.append(f"    direction {self.config.direction}")

        top_ids = {s.id for s in graph.states}
        self._render_states(graph.states, graph.transitions, lines, indent=1)
        self._render_initial_and_final(graph.states, lines, indent=1)
        self._render_scope_transitions(graph.transitions, top_ids, lines, indent=1)

        if self._active_ids:
            cfg = self.config
            lines.append("")
            lines.append(f"    classDef active fill:{cfg.active_fill},stroke:{cfg.active_stroke}")
            for sid in self._active_ids:
                lines.append(f"    {sid}:::active")

        return "\n".join(lines) + "\n"

    def _build_initial_child_map(self, states: List[DiagramState]) -> Dict[str, str]:
        """Build a map from compound state ID to its initial child ID (recursive)."""
        result: Dict[str, str] = {}
        for state in states:
            if state.children:
                initial = next((c for c in state.children if c.is_initial), None)
                if initial:
                    result[state.id] = initial.id
                result.update(self._build_initial_child_map(state.children))
        return result

    def _resolve_endpoint(self, state_id: str) -> str:
        """Resolve a transition endpoint, redirecting compound states to their initial child."""
        if state_id in self._compound_ids and state_id in self._initial_child_map:
            return self._initial_child_map[state_id]
        return state_id

    def _render_states(
        self,
        states: List[DiagramState],
        transitions: List[DiagramTransition],
        lines: List[str],
        indent: int,
    ) -> None:
        for state in states:
            if state.type in (StateType.HISTORY_SHALLOW, StateType.HISTORY_DEEP):
                label = "H*" if state.type == StateType.HISTORY_DEEP else "H"
                pad = "    " * indent
                lines.append(f'{pad}state "{label}" as {state.id}')
                continue

            if state.type == StateType.CHOICE:
                pad = "    " * indent
                lines.append(f"{pad}state {state.id} <<choice>>")
                continue

            if state.type == StateType.FORK:
                pad = "    " * indent
                lines.append(f"{pad}state {state.id} <<fork>>")
                continue

            if state.type == StateType.JOIN:
                pad = "    " * indent
                lines.append(f"{pad}state {state.id} <<join>>")
                continue

            if state.children:
                self._render_compound_state(state, transitions, lines, indent)
            else:
                self._render_atomic_state(state, lines, indent)

    def _render_atomic_state(
        self,
        state: DiagramState,
        lines: List[str],
        indent: int,
    ) -> None:
        pad = "    " * indent

        if state.name != state.id:
            lines.append(f'{pad}state "{state.name}" as {state.id}')

        actions = [a for a in state.actions if a.type != ActionType.INTERNAL or a.body]
        if actions:
            for action in actions:
                lines.append(f"{pad}{state.id} : {self._format_action(action)}")

        if state.is_active:
            self._active_ids.append(state.id)

    def _render_compound_state(
        self,
        state: DiagramState,
        transitions: List[DiagramTransition],
        lines: List[str],
        indent: int,
    ) -> None:
        pad = "    " * indent

        if state.type == StateType.PARALLEL:
            lines.append(f'{pad}state "{state.name}" as {state.id} {{')
            regions = [c for c in state.children if c.is_parallel_area or c.children]
            for i, region in enumerate(regions):
                if i > 0:
                    lines.append(f"{pad}    --")
                self._render_compound_state(region, transitions, lines, indent + 1)
            lines.append(f"{pad}}}")
        else:
            label = state.name if state.name != state.id else ""
            if label:
                lines.append(f'{pad}state "{label}" as {state.id} {{')
            else:
                lines.append(f"{pad}state {state.id} {{")

            initial_child = next((c for c in state.children if c.is_initial), None)
            if initial_child:
                lines.append(f"{pad}    [*] --> {initial_child.id}")

            self._render_states(state.children, transitions, lines, indent + 1)

            # Render transitions scoped to this compound
            child_ids = self._collect_all_descendant_ids(state.children)
            self._render_scope_transitions(transitions, child_ids, lines, indent + 1)

            # Final state transitions
            for child in state.children:
                if child.type == StateType.FINAL:
                    lines.append(f"{pad}    {child.id} --> [*]")

            lines.append(f"{pad}}}")

        if state.is_active:
            self._active_ids.append(state.id)

    def _collect_all_descendant_ids(self, states: List[DiagramState]) -> Set[str]:
        """Collect all state IDs in a subtree (direct children only for scope)."""
        ids: Set[str] = set()
        for s in states:
            ids.add(s.id)
        return ids

    def _render_scope_transitions(
        self,
        transitions: List[DiagramTransition],
        scope_ids: Set[str],
        lines: List[str],
        indent: int,
    ) -> None:
        """Render transitions where both source and all targets are in scope_ids.

        Mermaid does not support transitions where the source or target is a
        compound state rendered with ``state X { ... }`` inside a parallel region.
        To work around this, endpoints that reference compound states are
        redirected to the compound's initial child.  Scope membership is checked
        on the **original** IDs (which belong to this scope level), while the
        rendered arrow uses the **resolved** (possibly redirected) IDs.
        """
        for t in transitions:
            if t.is_initial or t.is_internal:
                continue

            targets = t.targets if t.targets else [t.source]

            # Check scope membership with original IDs
            if t.source not in scope_ids:
                continue
            if not all(target in scope_ids for target in targets):
                continue

            # Resolve endpoints for rendering (redirect compound → initial child)
            source = self._resolve_endpoint(t.source)
            resolved_targets = [self._resolve_endpoint(tid) for tid in targets]

            for target in resolved_targets:
                key = (source, target, t.event)
                if key in self._rendered_transitions:
                    continue
                self._rendered_transitions.add(key)
                self._render_single_transition(t, source, target, lines, indent)

    def _render_single_transition(
        self,
        transition: DiagramTransition,
        source: str,
        target: str,
        lines: List[str],
        indent: int,
    ) -> None:
        pad = "    " * indent
        label_parts: List[str] = []
        if transition.event:
            label_parts.append(transition.event)
        if transition.guards:
            label_parts.append(f"[{', '.join(transition.guards)}]")

        label = " ".join(label_parts)
        if label:
            lines.append(f"{pad}{source} --> {target} : {label}")
        else:
            lines.append(f"{pad}{source} --> {target}")

    @staticmethod
    def _format_action(action: DiagramAction) -> str:
        if action.type == ActionType.INTERNAL:
            return action.body
        return f"{action.type.value} / {action.body}"

    def _render_initial_and_final(
        self,
        states: List[DiagramState],
        lines: List[str],
        indent: int,
    ) -> None:
        """Render top-level [*] --> initial and final --> [*] arrows."""
        pad = "    " * indent
        initial = next((s for s in states if s.is_initial), None)
        if initial:
            lines.append(f"{pad}[*] --> {initial.id}")

        for state in states:
            if state.type == StateType.FINAL:
                lines.append(f"{pad}{state.id} --> [*]")
