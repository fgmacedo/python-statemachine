import re
from contextlib import contextmanager
from unittest import mock
from xml.etree import ElementTree

import pytest
from docutils import nodes
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
    # Verify the initial edge exists (from the black-dot initial node to child1)
    # The implicit initial transition from the compound state itself is NOT rendered
    # as an edge — it is represented only by the black-dot initial node inside the cluster.
    assert "parent_anchor -> child1" not in dot
    assert "-> child1" in dot


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

    transition = DiagramTransition(source="hist", targets=["child1"], event="")
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

    transition = DiagramTransition(source="source", targets=["target1", "target2"], event="go")
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
    # Implicit initial transitions from compound states are NOT rendered as edges —
    # they are represented by the black-dot initial node inside each cluster.
    assert "top_anchor -> entry" not in dot
    assert "-> entry" in dot


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


class TestSphinxDirective:
    """Unit tests for the statemachine-diagram Sphinx directive."""

    def test_parse_events(self):
        from statemachine.contrib.diagram.sphinx_ext import _parse_events

        assert _parse_events("start, ship") == ["start", "ship"]
        assert _parse_events("single") == ["single"]
        assert _parse_events(" a , b , c ") == ["a", "b", "c"]
        assert _parse_events("") == []

    def test_import_and_render_class(self, tmp_path):
        """Directive logic: import a class and generate SVG."""
        from statemachine.contrib.diagram import DotGraphMachine
        from statemachine.contrib.diagram import import_sm

        sm_class = import_sm("tests.examples.order_control_machine.OrderControl")
        graph = DotGraphMachine(sm_class).get_graph()
        svg_bytes = graph.create_svg()
        assert svg_bytes.startswith(b"<?xml")

    def test_import_and_render_with_events(self, tmp_path):
        """Directive logic: import, instantiate, send events, render SVG."""
        from statemachine.contrib.diagram import DotGraphMachine
        from statemachine.contrib.diagram import import_sm
        from statemachine.contrib.diagram.sphinx_ext import _parse_events

        sm_class = import_sm("tests.examples.traffic_light_machine.TrafficLightMachine")
        machine = sm_class()
        for event_name in _parse_events("cycle"):
            machine.send(event_name)

        graph = DotGraphMachine(machine).get_graph()
        svg_bytes = graph.create_svg()
        assert svg_bytes.startswith(b"<?xml")

    def test_import_invalid_qualname(self):
        """import_sm raises for invalid class paths."""
        from statemachine.contrib.diagram import import_sm

        with pytest.raises((ValueError, ModuleNotFoundError)):
            import_sm("nonexistent.module.SomeMachine")


class TestSplitLength:
    """Tests for the _split_length helper."""

    def test_split_pt(self):
        from statemachine.contrib.diagram.sphinx_ext import _split_length

        value, unit = _split_length("702pt")
        assert value == 702.0
        assert unit == "pt"

    def test_split_px(self):
        from statemachine.contrib.diagram.sphinx_ext import _split_length

        value, unit = _split_length("100px")
        assert value == 100.0
        assert unit == "px"

    def test_split_float(self):
        from statemachine.contrib.diagram.sphinx_ext import _split_length

        value, unit = _split_length("12.5em")
        assert value == 12.5
        assert unit == "em"

    def test_split_no_match(self):
        from statemachine.contrib.diagram.sphinx_ext import _split_length

        value, unit = _split_length("auto")
        assert value == 0.0
        assert unit == "auto"


class TestAlignSpec:
    """Tests for _align_spec option validator."""

    def test_valid_values(self):
        from statemachine.contrib.diagram.sphinx_ext import _align_spec

        assert _align_spec("left") == "left"
        assert _align_spec("center") == "center"
        assert _align_spec("right") == "right"

    def test_invalid_value(self):
        from statemachine.contrib.diagram.sphinx_ext import _align_spec

        with pytest.raises(ValueError, match="top"):
            _align_spec("top")


class TestSetup:
    """Tests for the Sphinx extension setup function."""

    def test_setup_returns_metadata(self):
        from statemachine.contrib.diagram.sphinx_ext import setup

        app = mock.MagicMock()
        result = setup(app)
        assert result["version"] == "0.1"
        assert result["parallel_read_safe"] is True
        assert result["parallel_write_safe"] is True
        app.add_directive.assert_called_once_with("statemachine-diagram", mock.ANY)


class TestPrepareSvg:
    """Tests for StateMachineDiagram._prepare_svg."""

    def _make_directive(self, options=None):
        from statemachine.contrib.diagram.sphinx_ext import StateMachineDiagram

        directive = StateMachineDiagram.__new__(StateMachineDiagram)
        directive.options = options or {}
        directive.arguments = ["test.Module"]
        return directive

    def test_strips_xml_prologue(self):
        svg_bytes = (
            b'<?xml version="1.0"?>\n<!DOCTYPE svg>\n'
            b'<svg width="100pt" height="50pt" viewBox="0 0 100 50">'
            b"<circle/></svg>"
        )
        directive = self._make_directive()
        svg_tag, w, h = directive._prepare_svg(svg_bytes)

        assert not svg_tag.startswith("<?xml")
        assert svg_tag.startswith("<svg")
        assert "</svg>" in svg_tag

    def test_extracts_intrinsic_dimensions(self):
        svg_bytes = b'<svg width="702pt" height="170pt"><rect/></svg>'
        directive = self._make_directive()
        _, w, h = directive._prepare_svg(svg_bytes)

        assert w == "702pt"
        assert h == "170pt"

    def test_removes_fixed_dimensions(self):
        svg_bytes = b'<svg width="702pt" height="170pt" viewBox="0 0 702 170"><rect/></svg>'
        directive = self._make_directive()
        svg_tag, _, _ = directive._prepare_svg(svg_bytes)

        assert 'width="702pt"' not in svg_tag
        assert 'height="170pt"' not in svg_tag
        assert "viewBox" in svg_tag

    def test_handles_no_dimensions(self):
        svg_bytes = b'<svg viewBox="0 0 100 50"><rect/></svg>'
        directive = self._make_directive()
        svg_tag, w, h = directive._prepare_svg(svg_bytes)

        assert w == ""
        assert h == ""

    def test_handles_px_dimensions(self):
        svg_bytes = b'<svg width="200px" height="100px"><rect/></svg>'
        directive = self._make_directive()
        _, w, h = directive._prepare_svg(svg_bytes)

        assert w == "200px"
        assert h == "100px"


class TestBuildSvgStyles:
    """Tests for StateMachineDiagram._build_svg_styles."""

    def _make_directive(self, options=None):
        from statemachine.contrib.diagram.sphinx_ext import StateMachineDiagram

        directive = StateMachineDiagram.__new__(StateMachineDiagram)
        directive.options = options or {}
        return directive

    def test_intrinsic_width_as_max_width(self):
        directive = self._make_directive()
        result = directive._build_svg_styles("702pt", "170pt")
        assert "max-width: 702pt" in result
        assert "height: auto" in result

    def test_explicit_width(self):
        directive = self._make_directive({"width": "400px"})
        result = directive._build_svg_styles("702pt", "170pt")
        assert "width: 400px" in result
        assert "max-width" not in result

    def test_explicit_height(self):
        directive = self._make_directive({"height": "200px"})
        result = directive._build_svg_styles("702pt", "170pt")
        assert "height: 200px" in result
        assert "height: auto" not in result

    def test_scale(self):
        directive = self._make_directive({"scale": "50%"})
        result = directive._build_svg_styles("702pt", "170pt")
        assert "width: 351.0pt" in result
        assert "height: 85.0pt" in result

    def test_scale_without_intrinsic(self):
        directive = self._make_directive({"scale": "50%"})
        result = directive._build_svg_styles("", "")
        # No width/height when no intrinsic dimensions to scale
        assert "max-width" not in result
        assert "height: auto" in result

    def test_no_dimensions(self):
        directive = self._make_directive()
        result = directive._build_svg_styles("", "")
        assert "height: auto" in result

    def test_explicit_width_overrides_scale(self):
        directive = self._make_directive({"width": "300px", "scale": "50%"})
        result = directive._build_svg_styles("702pt", "170pt")
        assert "width: 300px" in result
        assert "351" not in result


class TestBuildWrapperClasses:
    """Tests for StateMachineDiagram._build_wrapper_classes."""

    def _make_directive(self, options=None):
        from statemachine.contrib.diagram.sphinx_ext import StateMachineDiagram

        directive = StateMachineDiagram.__new__(StateMachineDiagram)
        directive.options = options or {}
        return directive

    def test_default_center_align(self):
        directive = self._make_directive()
        classes = directive._build_wrapper_classes()
        assert classes == ["statemachine-diagram", "align-center"]

    def test_custom_align(self):
        directive = self._make_directive({"align": "left"})
        classes = directive._build_wrapper_classes()
        assert classes == ["statemachine-diagram", "align-left"]

    def test_extra_css_classes(self):
        directive = self._make_directive({"class": ["my-class", "another"]})
        classes = directive._build_wrapper_classes()
        assert classes == ["statemachine-diagram", "align-center", "my-class", "another"]


class TestResolveTarget:
    """Tests for StateMachineDiagram._resolve_target."""

    def _make_directive(self, options=None, tmp_path=None):
        from statemachine.contrib.diagram.sphinx_ext import StateMachineDiagram

        directive = StateMachineDiagram.__new__(StateMachineDiagram)
        directive.options = options or {}
        directive.arguments = ["my.module.MyMachine"]
        if tmp_path is not None:
            directive.state = mock.MagicMock()
            directive.state.document.settings.env.app.outdir = str(tmp_path)
        return directive

    def test_no_target_option(self):
        directive = self._make_directive()
        assert directive._resolve_target(b"<svg/>") == ""

    def test_explicit_target_url(self):
        directive = self._make_directive({"target": "https://example.com/diagram.svg"})
        assert directive._resolve_target(b"<svg/>") == "https://example.com/diagram.svg"

    def test_empty_target_generates_file(self, tmp_path):
        directive = self._make_directive({"target": ""}, tmp_path=tmp_path)
        svg_data = b"<svg><rect/></svg>"
        result = directive._resolve_target(svg_data)

        assert result.startswith("/_images/statemachine-")
        assert result.endswith(".svg")

        # Verify the file was written
        images_dir = tmp_path / "_images"
        svg_files = list(images_dir.glob("statemachine-*.svg"))
        assert len(svg_files) == 1
        assert svg_files[0].read_bytes() == svg_data

    def test_empty_target_deterministic_filename(self, tmp_path):
        """Same qualname + events produces the same filename."""
        directive1 = self._make_directive({"target": "", "events": "go"}, tmp_path=tmp_path)
        directive2 = self._make_directive({"target": "", "events": "go"}, tmp_path=tmp_path)
        result1 = directive1._resolve_target(b"<svg>1</svg>")
        result2 = directive2._resolve_target(b"<svg>2</svg>")
        assert result1 == result2

    def test_different_events_different_filename(self, tmp_path):
        """Different events produce different filenames."""
        d1 = self._make_directive({"target": "", "events": "a"}, tmp_path=tmp_path)
        d2 = self._make_directive({"target": "", "events": "b"}, tmp_path=tmp_path)
        assert d1._resolve_target(b"<svg/>") != d2._resolve_target(b"<svg/>")


class TestDirectiveRun:
    """Integration tests for StateMachineDiagram.run()."""

    def _make_directive(self, qualname, options=None, tmp_path=None):
        from statemachine.contrib.diagram.sphinx_ext import StateMachineDiagram

        directive = StateMachineDiagram.__new__(StateMachineDiagram)
        directive.arguments = [qualname]
        directive.options = options or {}
        directive.lineno = 1
        directive.state_machine = mock.MagicMock()
        directive.state = mock.MagicMock()
        outdir = str(tmp_path) if tmp_path else "/tmp"
        directive.state.document.settings.env.app.outdir = outdir
        directive.content_offset = 0
        return directive

    def test_render_class_diagram(self, tmp_path):
        """Renders a class diagram (no events) as inline SVG."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            tmp_path=tmp_path,
        )
        result = directive.run()

        assert len(result) == 1
        node = result[0]
        assert isinstance(node, nodes.raw)
        assert node["format"] == "html"
        html = node.astext()
        assert "<svg" in html
        assert "statemachine-diagram" in html
        assert "align-center" in html

    def test_render_with_events(self, tmp_path):
        """Renders a diagram after sending events."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"events": "cycle"},
            tmp_path=tmp_path,
        )
        result = directive.run()

        assert len(result) == 1
        assert isinstance(result[0], nodes.raw)
        html = result[0].astext()
        assert "<svg" in html

    def test_render_with_empty_events(self, tmp_path):
        """Empty :events: instantiates the machine (highlights initial state)."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"events": ""},
            tmp_path=tmp_path,
        )
        result = directive.run()
        assert len(result) == 1
        assert isinstance(result[0], nodes.raw)

    def test_render_with_caption(self, tmp_path):
        """Caption wraps the diagram in a <figure> element."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"caption": "My caption"},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert "<figure" in html
        assert "<figcaption>My caption</figcaption>" in html

    def test_render_with_figclass(self, tmp_path):
        """figclass adds extra CSS classes to the figure wrapper."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"caption": "Test", "figclass": ["extra-fig"]},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert "extra-fig" in html

    def test_render_with_alt(self, tmp_path):
        """Custom alt text appears in aria-label."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"alt": "Traffic light diagram"},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert 'aria-label="Traffic light diagram"' in html

    def test_render_default_alt(self, tmp_path):
        """Default alt text uses the class name from the qualname."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert 'aria-label="TrafficLightMachine"' in html

    def test_render_with_explicit_target(self, tmp_path):
        """Explicit target wraps diagram in a link."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"target": "https://example.com"},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert 'href="https://example.com"' in html
        assert 'target="_blank"' in html

    def test_render_with_empty_target(self, tmp_path):
        """Empty target auto-generates a zoom SVG file."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"target": ""},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert 'href="/_images/statemachine-' in html

        # Verify SVG file was written
        images_dir = tmp_path / "_images"
        assert any(images_dir.glob("statemachine-*.svg"))

    def test_render_with_align(self, tmp_path):
        """Align option controls CSS class."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"align": "left"},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert "align-left" in html

    def test_render_with_width(self, tmp_path):
        """Width option is applied as inline style."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"width": "400px"},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert "width: 400px" in html

    def test_render_with_name(self, tmp_path):
        """Name option calls add_name for cross-referencing."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"name": "my-diagram"},
            tmp_path=tmp_path,
        )
        # add_name needs document and state attributes
        directive.state = mock.MagicMock()
        result = directive.run()

        assert len(result) == 1

    def test_render_with_class(self, tmp_path):
        """Custom CSS classes appear in the wrapper."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            options={"class": ["custom-class"]},
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert "custom-class" in html

    def test_invalid_qualname_returns_warning(self, tmp_path):
        """Invalid qualname returns a warning node."""
        directive = self._make_directive(
            "nonexistent.module.BadMachine",
            tmp_path=tmp_path,
        )
        result = directive.run()

        assert len(result) == 1
        # The warning is created via state_machine.reporter.warning mock
        directive.state_machine.reporter.warning.assert_called_once()
        call_args = directive.state_machine.reporter.warning.call_args
        assert "could not import" in call_args[0][0]

    def test_render_failure_returns_warning(self, tmp_path):
        """Diagram generation failure returns a warning node."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            tmp_path=tmp_path,
        )
        with mock.patch(
            "statemachine.contrib.diagram.DotGraphMachine",
            side_effect=RuntimeError("render failed"),
        ):
            result = directive.run()

        assert len(result) == 1
        directive.state_machine.reporter.warning.assert_called_once()
        call_args = directive.state_machine.reporter.warning.call_args
        assert "failed to generate" in call_args[0][0]

    def test_render_without_caption_uses_div(self, tmp_path):
        """Without caption, the wrapper is a plain <div>."""
        directive = self._make_directive(
            "tests.examples.traffic_light_machine.TrafficLightMachine",
            tmp_path=tmp_path,
        )
        result = directive.run()

        html = result[0].astext()
        assert "<figure" not in html
        assert "<div" in html
