import importlib
import sys
from urllib.parse import quote
from urllib.request import urlopen

import pydot

from ..statemachine import StateChart


class DotGraphMachine:
    graph_rankdir = "LR"
    """
    Direction of the graph. Defaults to "LR" (option "TB" for top bottom)
    http://www.graphviz.org/doc/info/attrs.html#d:rankdir
    """

    font_name = "Arial"
    """Graph font face name"""

    state_font_size = "10pt"
    """State font size"""

    state_active_penwidth = 2
    """Active state external line width"""

    state_active_fillcolor = "turquoise"

    transition_font_size = "9pt"
    """Transition font size"""

    def __init__(self, machine):
        self.machine = machine

    def _get_graph(self, machine):
        return pydot.Dot(
            machine.name,
            graph_type="digraph",
            label=machine.name,
            fontname=self.font_name,
            fontsize=self.state_font_size,
            rankdir=self.graph_rankdir,
            compound="true",
        )

    def _get_subgraph(self, state):
        style = ", solid"
        if state.parent and state.parent.parallel:
            style = ", dashed"
        label = state.name
        if state.parallel:
            label = f"<<b>{state.name}</b> &#9783;>"
        subgraph = pydot.Subgraph(
            label=label,
            graph_name=f"cluster_{state.id}",
            style=f"rounded{style}",
            cluster="true",
        )
        return subgraph

    def _initial_node(self, state):
        node = pydot.Node(
            self._state_id(state),
            label="",
            shape="point",
            style="filled",
            fontsize="1pt",
            fixedsize="true",
            width=0.2,
            height=0.2,
        )
        node.set_fillcolor("black")
        return node

    def _initial_edge(self, initial_node, state):
        extra_params = {}
        if state.states:
            extra_params["lhead"] = f"cluster_{state.id}"
        return pydot.Edge(
            initial_node.get_name(),
            self._state_id(state),
            label="",
            color="blue",
            fontname=self.font_name,
            fontsize=self.transition_font_size,
            **extra_params,
        )

    def _actions_getter(self):
        if isinstance(self.machine, StateChart):

            def getter(grouper):
                return self.machine._callbacks.str(grouper.key)
        else:

            def getter(grouper):
                all_names = set(dir(self.machine))
                return ", ".join(
                    str(c) for c in grouper if not c.is_convention or c.func in all_names
                )

        return getter

    def _state_actions(self, state):
        getter = self._actions_getter()

        entry = str(getter(state.enter))
        exit_ = str(getter(state.exit))
        internal = ", ".join(
            f"{transition.event} / {str(getter(transition.on))}"
            for transition in state.transitions
            if transition.internal
        )

        if entry:
            entry = f"entry / {entry}"
        if exit_:
            exit_ = f"exit / {exit_}"

        actions = "\n".join(x for x in [entry, exit_, internal] if x)

        if actions:
            actions = f"\n{actions}"

        return actions

    @staticmethod
    def _state_id(state):
        if state.states:
            return f"{state.id}_anchor"
        else:
            return state.id

    def _history_node(self, state):
        label = "H*" if state.deep else "H"
        return pydot.Node(
            self._state_id(state),
            label=label,
            shape="circle",
            style="filled",
            fillcolor="white",
            fontname=self.font_name,
            fontsize="8pt",
            fixedsize="true",
            width=0.3,
            height=0.3,
        )

    def _state_as_node(self, state):
        actions = self._state_actions(state)

        node = pydot.Node(
            self._state_id(state),
            label=f"{state.name}{actions}",
            shape="rectangle",
            style="rounded, filled",
            fontname=self.font_name,
            fontsize=self.state_font_size,
            peripheries=2 if state.final else 1,
        )
        if (
            isinstance(self.machine, StateChart)
            and state.value in self.machine.configuration_values
        ):
            node.set_penwidth(self.state_active_penwidth)
            node.set_fillcolor(self.state_active_fillcolor)
        else:
            node.set_fillcolor("white")
        return node

    def _transition_as_edges(self, transition):
        targets = transition.targets if transition.targets else [None]
        cond = ", ".join([str(c) for c in transition.cond])
        if cond:
            cond = f"\n[{cond}]"

        edges = []
        for i, target in enumerate(targets):
            extra_params = {}
            has_substates = transition.source.states or (target and target.states)
            if transition.source.states:
                extra_params["ltail"] = f"cluster_{transition.source.id}"
            if target and target.states:
                extra_params["lhead"] = f"cluster_{target.id}"

            targetless = target is None
            label = f"{transition.event}{cond}" if i == 0 else ""
            dst = self._state_id(target) if not targetless else self._state_id(transition.source)
            edges.append(
                pydot.Edge(
                    self._state_id(transition.source),
                    dst,
                    label=label,
                    color="blue",
                    fontname=self.font_name,
                    fontsize=self.transition_font_size,
                    minlen=2 if has_substates else 1,
                    **extra_params,
                )
            )
        return edges

    def get_graph(self):
        graph = self._get_graph(self.machine)
        self._graph_states(self.machine, graph, is_root=True)
        return graph

    def _add_transitions(self, graph, state):
        for transition in state.transitions:
            if transition.internal:
                continue
            for edge in self._transition_as_edges(transition):
                graph.add_edge(edge)

    def _graph_states(self, state, graph, is_root=False):
        initial_node = self._initial_node(state)
        initial_subgraph = pydot.Subgraph(
            graph_name=f"{initial_node.get_name()}_initial",
            label="",
            peripheries=0,
            margin=0,
        )
        atomic_states_subgraph = pydot.Subgraph(
            graph_name=f"cluster_{initial_node.get_name()}_atomic",
            label="",
            peripheries=0,
            cluster="true",
        )
        initial_subgraph.add_node(initial_node)
        graph.add_subgraph(initial_subgraph)
        graph.add_subgraph(atomic_states_subgraph)

        if state.states and not getattr(state, "parallel", False):
            initial = next((s for s in state.states if s.initial), None)
            if initial:
                graph.add_edge(self._initial_edge(initial_node, initial))

        for substate in state.states:
            if substate.states:
                subgraph = self._get_subgraph(substate)
                self._graph_states(substate, subgraph)
                graph.add_subgraph(subgraph)
            else:
                atomic_states_subgraph.add_node(self._state_as_node(substate))
            self._add_transitions(graph, substate)

        for history_state in getattr(state, "history", []):
            atomic_states_subgraph.add_node(self._history_node(history_state))
            self._add_transitions(graph, history_state)

    def __call__(self):
        return self.get_graph()


def quickchart_write_svg(sm: StateChart, path: str):
    """
    If the default dependency of GraphViz installed locally doesn't work for you. As an option,
    you can generate the image online from the output of the `dot` language,
    using one of the many services available.

    To get the **dot** representation of your state machine is as easy as follows:

    >>> from tests.examples.order_control_machine import OrderControl
    >>> sm = OrderControl()
    >>> print(sm._graph().to_string())
    digraph OrderControl {
    compound=true;
    fontname=Arial;
    fontsize="10pt";
    label=OrderControl;
    rankdir=LR;
    ...

    To give you an example, we included this method that will serialize the dot, request the graph
    to https://quickchart.io, and persist the result locally as an ``.svg`` file.


    .. warning::
        Quickchart is an external graph service that supports many formats to generate diagrams.

        By using this method, you should trust http://quickchart.io.

        Please read https://quickchart.io/documentation/faq/ for more information.

    >>> quickchart_write_svg(sm, "docs/images/oc_machine_processing.svg")  # doctest: +SKIP

    """
    dot_representation = sm._graph().to_string()

    url = f"https://quickchart.io/graphviz?graph={quote(dot_representation)}"

    response = urlopen(url)
    data = response.read()

    with open(path, "wb") as f:
        f.write(data)


def import_sm(qualname):
    module_name, class_name = qualname.rsplit(".", 1)
    module = importlib.import_module(module_name)
    smclass = getattr(module, class_name, None)
    if not smclass or not issubclass(smclass, StateChart):
        raise ValueError(f"{class_name} is not a subclass of StateMachine")

    return smclass


def write_image(qualname, out):
    """
    Given a `qualname`, that is the fully qualified dotted path to a StateMachine
    classes, imports the class and generates a dot graph using the `pydot` lib.
    Writes the graph representation to the filename 'out' that will
    open/create and truncate such file and write on it a representation of
    the graph defined by the statemachine, in the format specified by
    the extension contained in the out path (out.ext).
    """
    smclass = import_sm(qualname)

    graph = DotGraphMachine(smclass).get_graph()
    out_extension = out.rsplit(".", 1)[1]
    graph.write(out, format=out_extension)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] <class_path> <out>",
        description="Generate diagrams for StateMachine classes.",
    )
    parser.add_argument(
        "class_path", help="A fully-qualified dotted path to the StateMachine class."
    )
    parser.add_argument(
        "out",
        help="File to generate the image using extension as the output format.",
    )

    args = parser.parse_args(argv)
    write_image(qualname=args.class_path, out=args.out)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
