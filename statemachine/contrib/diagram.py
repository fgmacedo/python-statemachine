import importlib
import sys
from urllib.parse import quote
from urllib.request import urlopen

import pydot

from ..statemachine import StateMachine


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

    def _get_graph(self):
        machine = self.machine
        return pydot.Dot(
            "list",
            graph_type="digraph",
            label=machine.name,
            fontname=self.font_name,
            fontsize=self.state_font_size,
            rankdir=self.graph_rankdir,
        )

    def _initial_node(self):
        node = pydot.Node(
            "i",
            shape="circle",
            style="filled",
            fontsize="1pt",
            fixedsize="true",
            width=0.2,
            height=0.2,
        )
        node.set_fillcolor("black")
        return node

    def _initial_edge(self):
        return pydot.Edge(
            "i",
            self.machine.initial_state.id,
            label="",
            color="blue",
            fontname=self.font_name,
            fontsize=self.transition_font_size,
        )

    def _state_actions(self, state):
        entry = ", ".join([str(action) for action in state.enter])
        exit = ", ".join([str(action) for action in state.exit])
        internal = ", ".join(
            f"{transition.event} / {transition.on!s}"
            for transition in state.transitions
            if transition.internal
        )

        if entry:
            entry = f"entry / {entry}"
        if exit:
            exit = f"exit / {exit}"

        actions = "\n".join(x for x in [entry, exit, internal] if x)

        if actions:
            actions = f"\n{actions}"

        return actions

    def _state_as_node(self, state):
        actions = self._state_actions(state)

        node = pydot.Node(
            state.id,
            label=f"{state.name}{actions}",
            shape="rectangle",
            style="rounded, filled",
            fontname=self.font_name,
            fontsize=self.state_font_size,
            peripheries=2 if state.final else 1,
        )
        if state == self.machine.current_state:
            node.set_penwidth(self.state_active_penwidth)
            node.set_fillcolor(self.state_active_fillcolor)
        else:
            node.set_fillcolor("white")
        return node

    def _transition_as_edge(self, transition):
        cond = ", ".join([str(cond) for cond in transition.cond])
        if cond:
            cond = f"\n[{cond}]"
        return pydot.Edge(
            transition.source.id,
            transition.target.id,
            label=f"{transition.event}{cond}",
            color="blue",
            fontname=self.font_name,
            fontsize=self.transition_font_size,
        )

    def get_graph(self):
        graph = self._get_graph()
        graph.add_node(self._initial_node())
        graph.add_edge(self._initial_edge())

        for state in self.machine.states:
            graph.add_node(self._state_as_node(state))
            for transition in state.transitions:
                if transition.internal:
                    continue
                graph.add_edge(self._transition_as_edge(transition))

        return graph

    def __call__(self):
        return self.get_graph()


def quickchart_write_svg(sm: StateMachine, path: str):
    """
    If the default dependency of GraphViz installed locally doesn't work for you. As an option,
    you can generate the image online from the output of the `dot` language,
    using one of the many services available.

    To get the **dot** representation of your state machine is as easy as follows:

    >>> from tests.examples.order_control_machine import OrderControl
    >>> sm = OrderControl()
    >>> print(sm._graph().to_string())
    digraph list {
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
    if not smclass or not issubclass(smclass, StateMachine):
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
