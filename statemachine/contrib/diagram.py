import importlib
import sys

import pydot

from ..statemachine import BaseStateMachine


class DotGraphMachine(object):
    graph_rankdir = "LR"
    """
    Diretion of the graph. Defaults to "LR" (option "TB" for top botton)
    http://www.graphviz.org/doc/info/attrs.html#d:rankdir
    """

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
            fontsize=self.transition_font_size,
        )

    def _state_actions(self, state):
        entry = ", ".join(
            [getattr(action.func, "__name__", action.func) for action in state.enter]
        )
        exit = ", ".join(
            [getattr(action.func, "__name__", action.func) for action in state.exit]
        )

        if entry:
            entry = "entry / {}".format(entry)
        if exit:
            exit = "exit / {}".format(exit)

        actions = "\n".join(x for x in [entry, exit] if x)

        if actions:
            actions = "\n{}".format(actions)

        return actions

    def _state_as_node(self, state):
        actions = self._state_actions(state)

        node = pydot.Node(
            state.id,
            label="{}{}".format(state.name, actions),
            shape="rectangle",
            style="rounded, filled",
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
        def _get_condition_repr(cond):
            name = getattr(cond.func, "__name__", cond.func)
            return name if cond.expected_value else "!{}".format(name)

        cond = ", ".join([_get_condition_repr(cond) for cond in transition.cond])
        if cond:
            cond = "\n[{}]".format(cond)
        return pydot.Edge(
            transition.source.id,
            transition.target.id,
            label="{}{}".format(transition.event, cond),
            color="blue",
            fontsize=self.transition_font_size,
        )

    def get_graph(self):
        graph = self._get_graph()

        initial_node = self._initial_node()
        initial_edge = self._initial_edge()
        graph.add_node(initial_node)
        graph.add_edge(initial_edge)

        for state in self.machine.states:
            graph.add_node(self._state_as_node(state))
            for transition in state.transitions:
                graph.add_edge(self._transition_as_edge(transition))

        return graph

    def __call__(self):
        return self.get_graph()


def import_sm(qualname):
    module_name, class_name = qualname.rsplit(".", 1)
    module = importlib.import_module(module_name)
    smclass = getattr(module, class_name, None)
    if not smclass or not issubclass(smclass, BaseStateMachine):
        raise ValueError("{} is not a subclass of StateMachine".format(class_name))

    return smclass


def write_image(qualname, out):
    """
    Given a `qualname`, that is the fully qualified dotted path to a StateMachine
    classe, imports the class and generates a dot graph using the `pydot` lib.
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
        usage="%(prog)s [OPTION] <classpath> <out>",
        description="Generate diagrams for StateMachine classes.",
    )
    parser.add_argument(
        "classpath", help="A fully-qualified dotted path to the StateMachine class."
    )
    parser.add_argument(
        "out",
        help="File to generate the image using extension as the output format.",
    )

    args = parser.parse_args(argv)
    write_image(qualname=args.classpath, out=args.out)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
