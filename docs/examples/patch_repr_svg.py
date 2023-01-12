import sys


def patch__repr_svg_():  # pragma: no cover
    """
    You're running this example directly from your browser! By using the amazing
    https://pyodide.org/.

    Since we're in a browser, the default dependency of GraphViz installed locally don't work. So
    this cell is an option to see our examples and try the library on the fly without the need to
    install anything.

    We've to patch `StateMachine._repr_svg_` to retrieve the svg diagram online as the graphviz is
    not available.

    This method will serialize and request the graph to an external service: https://quickchart.io.
    By using de diagrams support you trust quickchart.io. Please read
    https://quickchart.io/documentation/faq/.

    See also https://python-statemachine.readthedocs.io/en/latest/diagram.html
    """
    from urllib.parse import quote
    from statemachine import StateMachine

    def show_sm(sm):
        url = "https://quickchart.io/graphviz?graph={}".format(
            quote(sm._graph().to_string())
        )
        return '<svg width="auto" height="auto"><image xlink:href="{}"/>'.format(url)

    StateMachine._repr_svg_ = show_sm


if sys.platform == "emscripten":  # pragma: no cover
    # https://pyodide.org/ is the runtime!
    patch__repr_svg_()
    print(patch__repr_svg_.__doc__)
    print("'StateMachine._repr_svg_' patched!")
