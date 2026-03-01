import re
from contextlib import contextmanager
from unittest import mock
from xml.etree import ElementTree

import pytest
from statemachine.contrib.diagram import DotGraphMachine
from statemachine.contrib.diagram import main
from statemachine.contrib.diagram import quickchart_write_svg
from statemachine.contrib.diagram.model import StateType
from statemachine.contrib.diagram.renderers.dot import DotRenderer

from statemachine import State
from statemachine import StateChart

pytestmark = pytest.mark.usefixtures("requires_dot_installed")

SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def _parse_svg(graph):
    """Generate SVG from a pydot graph and parse it as XML."""
    svg_bytes = graph.create_svg()
    return ElementTree.fromstring(svg_bytes)


def _find_state_node(svg_root, state_id):
    """Find the SVG <g> element for a state node by its title text."""
    for g in svg_root.iter("{http://www.w3.org/2000/svg}g"):
        if g.get("class") != "node":
            continue
        title = g.find("{http://www.w3.org/2000/svg}title")
        if title is not None and title.text == state_id:
            return g
    return None


def _has_rectangular_fill(node_g):
    """Check if a node group has a <polygon> with a colored fill.

    A <polygon> fill inside a state node means the background is rectangular
    (no rounded corners), which is a visual regression — state backgrounds
    should use <path> with curves to match the rounded border.

    Ignores white fills and arrow-related polygons (which are in edge groups).
    """
    for polygon in node_g.findall("{http://www.w3.org/2000/svg}polygon"):
        fill = polygon.get("fill", "none")
        if fill not in ("none", "white", "black", "#ffffff"):
            return True
    return False


def _path_has_curves(d_attr):
    """Check if an SVG path `d` attribute contains curve commands (C, c, Q, q, A, a).

    Rounded corners are drawn with cubic Bezier curves (C command).
    A rectangular shape only has M (move) and L (line) commands.
    """
    return bool(re.search(r"[CcQqAa]", d_attr))


@pytest.fixture(
    params=[
        (
            "_repr_svg_",
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<!DOCTYPE svg',
        ),
        (
            "_repr_html_",
            '<div class="statemachine"><?xml version="1.0" encoding="UTF-8" standalone=',
        ),
    ]
)
def expected_reprs(request):
    return request.param


@pytest.mark.parametrize(
    "machine_name",
    [
        "AllActionsMachine",
        "OrderControl",
    ],
)
def test_machine_repr_custom_(request, machine_name, expected_reprs):
    machine_cls = request.getfixturevalue(machine_name)
    machine = machine_cls()

    magic_method, expected_repr = expected_reprs
    repr = getattr(machine, magic_method)()
    assert repr.startswith(expected_repr)


def test_machine_dot(OrderControl):
    machine = OrderControl()

    graph = DotGraphMachine(machine)
    dot = graph()

    dot_str = dot.to_string()  # or dot.to_string()
    assert dot_str.startswith("digraph OrderControl {")


class TestDiagramCmdLine:
    def test_generate_image(self, tmp_path):
        out = tmp_path / "sm.svg"

        main(["tests.examples.traffic_light_machine.TrafficLightMachine", str(out)])

        assert out.read_text().startswith(
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<!DOCTYPE svg'
        )

    def test_generate_image_from_module_path(self, tmp_path):
        """Accept a module path without the class name and auto-discover the SM class."""
        out = tmp_path / "sm.svg"

        main(["tests.examples.traffic_light_machine", str(out)])

        assert out.read_text().startswith(
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<!DOCTYPE svg'
        )

    def test_generate_complain_about_bad_sm_path(self, capsys, tmp_path):
        out = tmp_path / "sm.svg"

        expected_error = "TrafficLightMachineXXX is not a subclass of StateMachine"
        with pytest.raises(ValueError, match=expected_error):
            main(
                [
                    "tests.examples.traffic_light_machine.TrafficLightMachineXXX",
                    str(out),
                ]
            )

    def test_generate_complain_about_module_without_sm(self, tmp_path):
        out = tmp_path / "sm.svg"

        expected_error = "No StateMachine subclass found in module"
        with pytest.raises(ValueError, match=expected_error):
            main(["tests.examples", str(out)])


class TestQuickChart:
    @contextmanager
    def mock_quickchart(self, origin_img_path):
        with open(origin_img_path) as f:
            expected_image = f.read()

        with mock.patch("statemachine.contrib.diagram.urlopen", spec=True) as p:
            p().read.side_effect = lambda: expected_image.encode()
            yield p

    def test_should_call_write_svg(self, OrderControl):
        sm = OrderControl()
        with self.mock_quickchart("docs/images/_oc_machine_processing.svg"):
            quickchart_write_svg(sm, "docs/images/oc_machine_processing.svg")


def test_compound_state_diagram():
    """Diagram renders compound state subgraphs."""

    class SM(StateChart):
        class parent(State.Compound, name="Parent"):
            child1 = State(initial=True)
            child2 = State(final=True)

            go = child1.to(child2)

        start = State(initial=True)
        end = State(final=True)

        enter = start.to(parent)
        finish = parent.to(end)

    graph = DotGraphMachine(SM)
    result = graph()
    assert result is not None
    dot = result.to_string()
    assert "cluster_parent" in dot


def test_parallel_state_diagram():
    """Diagram renders parallel state with dashed style."""

    class SM(StateChart):
        class p(State.Parallel, name="p"):
            class r1(State.Compound, name="r1"):
                a = State(initial=True)
                a_done = State(final=True)
                finish_a = a.to(a_done)

            class r2(State.Compound, name="r2"):
                b = State(initial=True)
                b_done = State(final=True)
                finish_b = b.to(b_done)

        start = State(initial=True)
        begin = start.to(p)

    graph = DotGraphMachine(SM)
    result = graph()
    dot = result.to_string()
    assert "cluster_p" in dot
    assert "cluster_r1" in dot
    assert "cluster_r2" in dot


def test_nested_compound_state_diagram():
    """Diagram renders nested compound states."""

    class SM(StateChart):
        class outer(State.Compound, name="Outer"):
            class inner(State.Compound, name="Inner"):
                deep = State(initial=True)
                deep_final = State(final=True)
                go_deep = deep.to(deep_final)

            start_inner = State(initial=True)
            to_inner = start_inner.to(inner)

        begin = State(initial=True)
        enter = begin.to(outer)

    graph = DotGraphMachine(SM)
    result = graph()
    dot = result.to_string()
    assert "cluster_outer" in dot
    assert "cluster_inner" in dot


def test_subgraph_dashed_style_for_parallel_parent():
    """Subgraph uses dashed border when parent state is parallel."""

    class SM(StateChart):
        class p(State.Parallel, name="p"):
            class r1(State.Compound, name="r1"):
                a = State(initial=True)

        start = State(initial=True)
        begin = start.to(p)

    dot = DotGraphMachine(SM)().to_string()
    # The region subgraph inside a parallel state should have dashed style
    assert "dashed" in dot


def test_initial_edge_with_compound_state_has_lhead():
    """Initial edge to a compound state sets lhead cluster attribute."""

    class SM(StateChart):
        class parent(State.Compound, name="Parent"):
            child1 = State(initial=True)
            child2 = State(final=True)
            go = child1.to(child2)

        start = State(initial=True)
        enter = start.to(parent)

    dot = DotGraphMachine(SM)().to_string()
    assert "lhead=cluster_parent" in dot


def test_initial_edge_inside_compound_subgraph():
    """Compound substate has an initial edge from dot to initial child."""

    class SM(StateChart):
        class parent(State.Compound, name="Parent"):
            child1 = State(initial=True)
            child2 = State(final=True)

            go = child1.to(child2)

        start = State(initial=True)
        end = State(final=True)

        enter = start.to(parent)
        finish = parent.to(end)

    graph = DotGraphMachine(SM)
    dot = graph().to_string()
    # The compound subgraph should contain an initial point node and an edge to child1
    assert "parent_anchor" in dot
    assert "child1" in dot
    # Verify the initial edge exists (from parent's initial node to child1)
    assert "parent_anchor -> child1" in dot


def test_history_state_shallow_diagram():
    """DOT output contains an 'H' circle node for shallow history state."""
    from statemachine.contrib.diagram.model import DiagramState

    state = DiagramState(id="h_shallow", name="H", type=StateType.HISTORY_SHALLOW)
    renderer = DotRenderer()
    node = renderer._create_history_node(state)
    attrs = node.obj_dict["attributes"]
    assert attrs["label"] in ("H", '"H"')
    assert attrs["shape"] == "circle"


def test_history_state_deep_diagram():
    """DOT output contains an 'H*' circle node for deep history state."""
    from statemachine.contrib.diagram.model import DiagramState

    state = DiagramState(id="h_deep", name="H*", type=StateType.HISTORY_DEEP)
    renderer = DotRenderer()
    node = renderer._create_history_node(state)
    dot_str = node.to_string()
    assert "H*" in dot_str
    assert "circle" in dot_str


def test_history_state_default_transition():
    """History state's default transition appears as an edge in the diagram."""
    from statemachine.contrib.diagram.model import DiagramTransition

    transition = DiagramTransition(source="hist", target="child1", targets=["child1"], event="")
    renderer = DotRenderer()
    renderer._compound_ids = set()
    edges = renderer._create_edges(transition)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.obj_dict["points"] == ("hist", "child1")


def test_parallel_state_label_indicator():
    """Parallel subgraph label includes a visual indicator."""

    class SM(StateChart):
        class p(State.Parallel, name="p"):
            class r1(State.Compound, name="r1"):
                a = State(initial=True)

            class r2(State.Compound, name="r2"):
                b = State(initial=True)

        start = State(initial=True)
        begin = start.to(p)

    graph = DotGraphMachine(SM)
    dot = graph().to_string()
    # The parallel state label should contain an HTML-like label with the indicator
    assert "&#9783;" in dot


def test_history_state_in_graph_states():
    """History pseudo-state nodes appear in the full graph output."""
    from tests.examples.statechart_history_machine import PersonalityMachine

    graph = DotGraphMachine(PersonalityMachine)
    dot = graph().to_string()
    # History node should render as an 'H' circle
    assert '"H"' in dot or "H" in dot


def test_multi_target_transition_diagram():
    """Edges are created for all targets of a multi-target transition."""
    from statemachine.contrib.diagram.model import DiagramTransition

    transition = DiagramTransition(
        source="source", target="target1", targets=["target1", "target2"], event="go"
    )
    renderer = DotRenderer()
    renderer._compound_ids = set()
    edges = renderer._create_edges(transition)
    assert len(edges) == 2
    assert edges[0].obj_dict["points"] == ("source", "target1")
    assert edges[1].obj_dict["points"] == ("source", "target2")
    # Only the first edge gets a label
    assert "go" in edges[0].obj_dict["attributes"]["label"]
    assert edges[1].obj_dict["attributes"]["label"] == ""


def test_compound_and_parallel_mixed():
    """Full diagram with compound and parallel states renders without error."""

    class SM(StateChart):
        class top(State.Compound, name="Top"):
            class par(State.Parallel, name="Par"):
                class region1(State.Compound, name="Region1"):
                    r1_a = State(initial=True)
                    r1_b = State(final=True)
                    r1_go = r1_a.to(r1_b)

                class region2(State.Compound, name="Region2"):
                    r2_a = State(initial=True)
                    r2_b = State(final=True)
                    r2_go = r2_a.to(r2_b)

            entry = State(initial=True)
            start_par = entry.to(par)

        begin = State(initial=True)
        enter_top = begin.to(top)

    graph = DotGraphMachine(SM)
    dot = graph().to_string()
    assert "cluster_top" in dot
    assert "cluster_par" in dot
    assert "cluster_region1" in dot
    assert "cluster_region2" in dot
    # Parallel indicator
    assert "&#9783;" in dot
    # Verify initial edges exist for compound states (top and regions)
    assert "top_anchor -> entry" in dot


class TestSVGShapeConsistency:
    """Verify that active and inactive states render with the same shape in SVG.

    These tests parse the generated SVG to catch visual regressions that are
    hard to spot by inspecting DOT source alone. For example, using `bgcolor`
    on a `<td>` instead of a `<table>` causes Graphviz to render a rectangular
    `<polygon>` behind a rounded `<path>` border — the DOT looks fine but the
    visual result is broken.
    """

    def test_active_state_has_no_rectangular_fill(self):
        """Active state background must use rounded <path>, not rectangular <polygon>."""
        from tests.examples.traffic_light_machine import TrafficLightMachine

        sm = TrafficLightMachine()  # starts in Green
        graph = DotGraphMachine(sm).get_graph()
        svg = _parse_svg(graph)

        green_node = _find_state_node(svg, "green")
        assert green_node is not None, "Could not find 'green' node in SVG"
        assert not _has_rectangular_fill(green_node), (
            "Active state 'green' has a rectangular <polygon> fill — "
            "expected a rounded <path> fill to match the border shape"
        )

    def test_active_and_inactive_states_use_same_svg_element_type(self):
        """Active and inactive states must both render as rounded <path> elements.

        With ``shape=rectangle`` + ``style="rounded, filled"``, Graphviz renders
        each state as a single ``<path>`` with cubic Bezier curves (``C`` commands)
        for rounded corners. Both the fill and stroke are in the same ``<path>``.

        A regression would be if the active state rendered differently — e.g., a
        rectangular ``<polygon>`` for the fill behind a rounded ``<path>`` border.
        """
        from tests.examples.traffic_light_machine import TrafficLightMachine

        sm = TrafficLightMachine()
        graph = DotGraphMachine(sm).get_graph()
        svg = _parse_svg(graph)

        for state_id in ("green", "yellow", "red"):
            node = _find_state_node(svg, state_id)
            assert node is not None, f"Could not find '{state_id}' node in SVG"

            # Each state should have at least one <path> with rounded curves
            paths = node.findall("{http://www.w3.org/2000/svg}path")
            assert len(paths) >= 1, (
                f"State '{state_id}' should have at least 1 <path>, found {len(paths)}"
            )
            for p in paths:
                assert _path_has_curves(p.get("d", "")), (
                    f"State '{state_id}' has a <path> without curves — not rounded"
                )

    def test_no_state_node_has_rectangular_colored_fill(self):
        """No state in the diagram should have a rectangular <polygon> colored fill."""

        class SM(StateChart):
            s1 = State(initial=True)
            s2 = State()
            s3 = State(final=True)
            go = s1.to(s2)
            finish = s2.to(s3)

        sm = SM()
        sm.go()  # move to s2
        graph = DotGraphMachine(sm).get_graph()
        svg = _parse_svg(graph)

        for state_id in ("s1", "s2", "s3"):
            node = _find_state_node(svg, state_id)
            if node is None:
                continue
            assert not _has_rectangular_fill(node), (
                f"State '{state_id}' has a rectangular <polygon> colored fill"
            )
