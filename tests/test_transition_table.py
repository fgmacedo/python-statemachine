from statemachine.contrib.diagram.extract import extract
from statemachine.contrib.diagram.model import DiagramGraph
from statemachine.contrib.diagram.model import DiagramState
from statemachine.contrib.diagram.model import DiagramTransition
from statemachine.contrib.diagram.model import StateType
from statemachine.contrib.diagram.renderers.table import TransitionTableRenderer

from statemachine import State
from statemachine import StateChart


class TestTransitionTableMarkdown:
    """Markdown transition table tests."""

    def test_simple_table(self):
        graph = DiagramGraph(
            name="Simple",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="go"),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="md")
        assert "| State" in result
        assert "| Event" in result
        assert "| Guard" in result
        assert "| Target" in result
        assert "| S1" in result
        assert "go" in result
        assert "| S2" in result

    def test_with_guards(self):
        graph = DiagramGraph(
            name="Guards",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="go", guards=["is_ready"]),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="md")
        assert "is_ready" in result

    def test_multiple_targets(self):
        graph = DiagramGraph(
            name="Multi",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
                DiagramState(id="s3", name="S3", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2", "s3"], event="split"),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="md")
        lines = result.strip().split("\n")
        # Header + separator + 2 data rows
        assert len(lines) == 4

    def test_skips_initial_transitions(self):
        graph = DiagramGraph(
            name="SkipInit",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="", is_initial=True),
                DiagramTransition(source="s1", targets=["s2"], event="go"),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="md")
        lines = result.strip().split("\n")
        # Header + separator + 1 data row (initial skipped)
        assert len(lines) == 3

    def test_skips_internal_transitions(self):
        graph = DiagramGraph(
            name="SkipInternal",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s1"], event="check", is_internal=True),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="md")
        lines = result.strip().split("\n")
        # Header + separator only (no data rows)
        assert len(lines) == 2

    def test_targetless_transition(self):
        graph = DiagramGraph(
            name="Targetless",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=[], event="tick"),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="md")
        assert "tick" in result
        # Target falls back to source name
        assert "S1" in result


class TestTransitionTableRST:
    """RST grid table tests."""

    def test_rst_format(self):
        graph = DiagramGraph(
            name="RST",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="go"),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="rst")
        assert "+---" in result
        assert "|" in result
        assert "====" in result  # header separator
        assert "go" in result

    def test_rst_with_guards(self):
        graph = DiagramGraph(
            name="RSTGuards",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="go", guards=["is_ready"]),
            ],
        )
        result = TransitionTableRenderer().render(graph, fmt="rst")
        assert "is_ready" in result


class TestTransitionTableIntegration:
    """Integration tests with real state machines."""

    def test_traffic_light_md(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        ir = extract(TrafficLightMachine)
        result = TransitionTableRenderer().render(ir, fmt="md")
        assert "Green" in result
        assert "Yellow" in result
        assert "Red" in result
        assert "cycle" in result

    def test_traffic_light_rst(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        ir = extract(TrafficLightMachine)
        result = TransitionTableRenderer().render(ir, fmt="rst")
        assert "Green" in result
        assert "cycle" in result
        assert "+---" in result

    def test_compound_state_names(self):
        """Child state names are properly resolved."""

        class SM(StateChart):
            class parent(State.Compound, name="Parent"):
                child1 = State(initial=True)
                child2 = State(final=True)
                go = child1.to(child2)

            start = State(initial=True)
            enter = start.to(parent)

        ir = extract(SM)
        result = TransitionTableRenderer().render(ir, fmt="md")
        assert "Child1" in result
        assert "Child2" in result

    def test_default_format_is_md(self):
        """render() without fmt defaults to markdown."""
        graph = DiagramGraph(
            name="Default",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="go"),
            ],
        )
        result = TransitionTableRenderer().render(graph)
        assert "| State" in result  # markdown uses pipes
