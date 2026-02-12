from contextlib import contextmanager
from unittest import mock

import pytest
from statemachine.contrib.diagram import DotGraphMachine
from statemachine.contrib.diagram import main
from statemachine.contrib.diagram import quickchart_write_svg

from statemachine import State
from statemachine import StateChart

pytestmark = pytest.mark.usefixtures("requires_dot_installed")


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
        validate_disconnected_states: bool = False

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
        validate_disconnected_states: bool = False

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
    child = State("child", initial=True)
    child._set_id("child")
    parent = State("parent", parallel=True, states=[child])
    parent._set_id("parent")

    graph_maker = DotGraphMachine.__new__(DotGraphMachine)
    subgraph = graph_maker._get_subgraph(child)
    assert "dashed" in subgraph.obj_dict["attributes"].get("style", "")


def test_initial_edge_with_compound_state_has_lhead():
    """Initial edge to a compound state sets lhead cluster attribute."""
    inner = State("inner", initial=True)
    inner._set_id("inner")
    compound = State("compound", states=[inner], initial=True)
    compound._set_id("compound")

    graph_maker = DotGraphMachine.__new__(DotGraphMachine)
    initial_node = graph_maker._initial_node(compound)
    edge = graph_maker._initial_edge(initial_node, compound)
    attrs = edge.obj_dict["attributes"]
    assert attrs.get("lhead") == f"cluster_{compound.id}"
