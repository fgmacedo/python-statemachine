import importlib
from urllib.parse import quote
from urllib.request import urlopen

from .extract import extract
from .renderers.dot import DotRenderer
from .renderers.dot import DotRendererConfig


class DotGraphMachine:
    """Backwards-compatible facade that uses the extract + render pipeline.

    Maintains the same public API and class-level customization attributes
    as the original monolithic DotGraphMachine.
    """

    graph_rankdir = "LR"
    """
    Direction of the graph. Defaults to "LR" (option "TB" for top bottom)
    http://www.graphviz.org/doc/info/attrs.html#d:rankdir
    """

    graph_dpi = 200
    """Graph resolution in dots per inch"""

    font_name = "Helvetica"
    """Graph font face name"""

    state_font_size = "10"
    """State font size"""

    state_active_penwidth = 2
    """Active state external line width"""

    state_active_fillcolor = "turquoise"

    transition_font_size = "9"
    """Transition font size"""

    def __init__(self, machine):
        self.machine = machine

    def _build_config(self) -> DotRendererConfig:
        return DotRendererConfig(
            graph_rankdir=self.graph_rankdir,
            graph_dpi=self.graph_dpi,
            font_name=self.font_name,
            state_font_size=self.state_font_size,
            state_active_penwidth=self.state_active_penwidth,
            state_active_fillcolor=self.state_active_fillcolor,
            transition_font_size=self.transition_font_size,
        )

    def get_graph(self):
        ir = extract(self.machine)
        renderer = DotRenderer(config=self._build_config())
        return renderer.render(ir)

    def __call__(self):
        return self.get_graph()


def quickchart_write_svg(sm, path: str):
    """
    If the default dependency of GraphViz installed locally doesn't work for you. As an option,
    you can generate the image online from the output of the `dot` language,
    using one of the many services available.

    To get the **dot** representation of your state machine is as easy as follows:

    >>> from tests.examples.order_control_machine import OrderControl
    >>> sm = OrderControl()
    >>> print(sm._graph().to_string())  # doctest: +ELLIPSIS
    digraph OrderControl {
    ...
    }

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


def _find_sm_class(module):
    """Find the first StateChart subclass defined in a module."""
    import inspect

    from statemachine.statemachine import StateChart

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, StateChart)
            and obj is not StateChart
            and obj.__module__ == module.__name__
        ):
            return obj
    return None


def import_sm(qualname):
    from statemachine.statemachine import StateChart

    module_name, class_name = qualname.rsplit(".", 1)
    module = importlib.import_module(module_name)
    smclass = getattr(module, class_name, None)
    if smclass is not None and isinstance(smclass, type) and issubclass(smclass, StateChart):
        return smclass

    # qualname may be a module path without a class name — try importing
    # the whole path as a module and find the first StateChart subclass.
    try:
        module = importlib.import_module(qualname)
    except ImportError as err:
        raise ValueError(f"{class_name} is not a subclass of StateMachine") from err

    smclass = _find_sm_class(module)
    if smclass is None:
        raise ValueError(f"No StateMachine subclass found in module {qualname!r}")

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
