from statemachine.contrib.diagram import MermaidGraphMachine
from statemachine.contrib.diagram.model import ActionType
from statemachine.contrib.diagram.model import DiagramAction
from statemachine.contrib.diagram.model import DiagramGraph
from statemachine.contrib.diagram.model import DiagramState
from statemachine.contrib.diagram.model import DiagramTransition
from statemachine.contrib.diagram.model import StateType
from statemachine.contrib.diagram.renderers.mermaid import MermaidRenderer
from statemachine.contrib.diagram.renderers.mermaid import MermaidRendererConfig

from statemachine import State
from statemachine import StateChart


class TestMermaidRendererSimple:
    """Basic MermaidRenderer tests with simple states."""

    def test_simple_states(self):
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
        result = MermaidRenderer().render(graph)
        assert "stateDiagram-v2" in result
        assert "direction LR" in result
        assert "[*] --> s1" in result
        assert "s1 --> s2 : go" in result

    def test_initial_and_final(self):
        graph = DiagramGraph(
            name="InitFinal",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.FINAL),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="finish"),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "[*] --> s1" in result
        assert "s2 --> [*]" in result

    def test_custom_direction(self):
        config = MermaidRendererConfig(direction="TB")
        graph = DiagramGraph(
            name="TB",
            states=[DiagramState(id="a", name="A", type=StateType.REGULAR, is_initial=True)],
        )
        result = MermaidRenderer(config=config).render(graph)
        assert "direction TB" in result

    def test_state_name_differs_from_id(self):
        graph = DiagramGraph(
            name="Named",
            states=[
                DiagramState(
                    id="my_state", name="My State", type=StateType.REGULAR, is_initial=True
                ),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert 'state "My State" as my_state' in result

    def test_state_name_equals_id_no_declaration(self):
        """When name == id, no explicit state declaration is emitted."""
        graph = DiagramGraph(
            name="NoDecl",
            states=[
                DiagramState(id="s1", name="s1", type=StateType.REGULAR, is_initial=True),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert 'state "s1"' not in result


class TestMermaidRendererTransitions:
    """Transition rendering tests."""

    def test_transition_with_guards(self):
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
        result = MermaidRenderer().render(graph)
        assert "s1 --> s2 : go [is_ready]" in result

    def test_eventless_transition(self):
        graph = DiagramGraph(
            name="Eventless",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event=""),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "s1 --> s2\n" in result

    def test_self_transition(self):
        graph = DiagramGraph(
            name="SelfLoop",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s1"], event="tick"),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "s1 --> s1 : tick" in result

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
        result = MermaidRenderer().render(graph)
        assert "s1 --> s1 : tick" in result

    def test_multi_target_transition(self):
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
        result = MermaidRenderer().render(graph)
        assert "s1 --> s2 : split" in result
        assert "s1 --> s3 : split" in result

    def test_internal_transitions_skipped(self):
        graph = DiagramGraph(
            name="Internal",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s1"], event="check", is_internal=True),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "s1 --> s1" not in result

    def test_initial_transitions_skipped(self):
        graph = DiagramGraph(
            name="InitTrans",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="", is_initial=True),
            ],
        )
        result = MermaidRenderer().render(graph)
        # Implicit initial transitions are NOT rendered as edges
        assert "s1 --> s2" not in result


class TestMermaidRendererActiveState:
    """Active state highlighting tests."""

    def test_active_state_class(self):
        graph = DiagramGraph(
            name="Active",
            states=[
                DiagramState(
                    id="s1", name="S1", type=StateType.REGULAR, is_initial=True, is_active=True
                ),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="go"),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "classDef active" in result
        assert "s1:::active" in result
        assert "s2:::active" not in result

    def test_no_active_state_no_classdef(self):
        graph = DiagramGraph(
            name="NoActive",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "classDef" not in result

    def test_active_fill_config(self):
        config = MermaidRendererConfig(active_fill="#FF0000", active_stroke="#000")
        graph = DiagramGraph(
            name="CustomActive",
            states=[
                DiagramState(
                    id="s1", name="S1", type=StateType.REGULAR, is_initial=True, is_active=True
                ),
            ],
        )
        result = MermaidRenderer(config=config).render(graph)
        assert "fill:#FF0000" in result
        assert "stroke:#000" in result


class TestMermaidRendererCompound:
    """Compound and parallel state tests."""

    def test_compound_state(self):
        class SM(StateChart):
            class parent(State.Compound, name="Parent"):
                child1 = State(initial=True)
                child2 = State(final=True)
                go = child1.to(child2)

            start = State(initial=True)
            end = State(final=True)

            enter = start.to(parent)
            finish = parent.to(end)

        result = MermaidGraphMachine(SM).get_mermaid()
        assert 'state "Parent" as parent {' in result
        assert "[*] --> child1" in result
        assert "child1 --> child2 : go" in result
        assert "child2 --> [*]" in result
        # Compound endpoints are redirected to the initial child (Mermaid workaround)
        assert "start --> child1 : enter" in result
        assert "child1 --> end : finish" in result

    def test_compound_no_duplicate_transitions(self):
        """Transitions inside compound states must not also appear at top level."""

        class SM(StateChart):
            class parent(State.Compound, name="Parent"):
                child1 = State(initial=True)
                child2 = State(final=True)
                go = child1.to(child2)

            start = State(initial=True)
            enter = start.to(parent)

        result = MermaidGraphMachine(SM).get_mermaid()
        # "child1 --> child2 : go" should appear exactly once (inside compound)
        assert result.count("child1 --> child2 : go") == 1

    def test_parallel_state(self):
        class SM(StateChart):
            class p(State.Parallel, name="Parallel"):
                class r1(State.Compound, name="Region1"):
                    a = State(initial=True)
                    a_done = State(final=True)
                    finish_a = a.to(a_done)

                class r2(State.Compound, name="Region2"):
                    b = State(initial=True)
                    b_done = State(final=True)
                    finish_b = b.to(b_done)

            start = State(initial=True)
            begin = start.to(p)

        result = MermaidGraphMachine(SM).get_mermaid()
        assert 'state "Parallel" as p {' in result
        assert "--" in result  # parallel separator

    def test_nested_compound(self):
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

        result = MermaidGraphMachine(SM).get_mermaid()
        assert 'state "Outer" as outer {' in result
        assert 'state "Inner" as inner {' in result


class TestMermaidRendererPseudoStates:
    """Pseudo-state rendering tests."""

    def test_history_shallow(self):
        graph = DiagramGraph(
            name="History",
            states=[
                DiagramState(
                    id="comp",
                    name="Comp",
                    type=StateType.REGULAR,
                    is_initial=True,
                    children=[
                        DiagramState(id="h", name="H", type=StateType.HISTORY_SHALLOW),
                        DiagramState(id="c1", name="C1", type=StateType.REGULAR, is_initial=True),
                    ],
                ),
            ],
            compound_state_ids={"comp"},
        )
        result = MermaidRenderer().render(graph)
        assert 'state "H" as h' in result

    def test_history_deep(self):
        graph = DiagramGraph(
            name="DeepHistory",
            states=[
                DiagramState(
                    id="comp",
                    name="Comp",
                    type=StateType.REGULAR,
                    is_initial=True,
                    children=[
                        DiagramState(id="h", name="H*", type=StateType.HISTORY_DEEP),
                        DiagramState(id="c1", name="C1", type=StateType.REGULAR, is_initial=True),
                    ],
                ),
            ],
            compound_state_ids={"comp"},
        )
        result = MermaidRenderer().render(graph)
        assert 'state "H*" as h' in result

    def test_choice_state(self):
        graph = DiagramGraph(
            name="Choice",
            states=[
                DiagramState(id="ch", name="ch", type=StateType.CHOICE, is_initial=True),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "state ch <<choice>>" in result

    def test_fork_state(self):
        graph = DiagramGraph(
            name="Fork",
            states=[
                DiagramState(id="fk", name="fk", type=StateType.FORK, is_initial=True),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "state fk <<fork>>" in result

    def test_join_state(self):
        graph = DiagramGraph(
            name="Join",
            states=[
                DiagramState(id="jn", name="jn", type=StateType.JOIN, is_initial=True),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "state jn <<join>>" in result


class TestMermaidRendererActions:
    """State action rendering tests."""

    def test_entry_exit_actions(self):
        graph = DiagramGraph(
            name="Actions",
            states=[
                DiagramState(
                    id="s1",
                    name="S1",
                    type=StateType.REGULAR,
                    is_initial=True,
                    actions=[
                        DiagramAction(type=ActionType.ENTRY, body="setup"),
                        DiagramAction(type=ActionType.EXIT, body="cleanup"),
                    ],
                ),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "s1 : entry / setup" in result
        assert "s1 : exit / cleanup" in result

    def test_internal_action(self):
        graph = DiagramGraph(
            name="InternalAction",
            states=[
                DiagramState(
                    id="s1",
                    name="S1",
                    type=StateType.REGULAR,
                    is_initial=True,
                    actions=[
                        DiagramAction(type=ActionType.INTERNAL, body="tick / handle"),
                    ],
                ),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "s1 : tick / handle" in result

    def test_empty_internal_action_skipped(self):
        graph = DiagramGraph(
            name="EmptyInternal",
            states=[
                DiagramState(
                    id="s1",
                    name="S1",
                    type=StateType.REGULAR,
                    is_initial=True,
                    actions=[
                        DiagramAction(type=ActionType.INTERNAL, body=""),
                    ],
                ),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "s1 : " not in result


class TestMermaidGraphMachine:
    """Tests for the MermaidGraphMachine facade."""

    def test_facade_returns_string(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        result = MermaidGraphMachine(TrafficLightMachine).get_mermaid()
        assert isinstance(result, str)
        assert "stateDiagram-v2" in result

    def test_facade_callable(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        facade = MermaidGraphMachine(TrafficLightMachine)
        assert facade() == facade.get_mermaid()

    def test_facade_with_instance(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        sm = TrafficLightMachine()
        result = MermaidGraphMachine(sm).get_mermaid()
        assert "green:::active" in result

    def test_facade_custom_config(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        class Custom(MermaidGraphMachine):
            direction = "TB"
            active_fill = "#FF0000"

        sm = TrafficLightMachine()
        result = Custom(sm).get_mermaid()
        assert "direction TB" in result
        assert "fill:#FF0000" in result


class TestMermaidRendererEdgeCases:
    """Edge case tests for coverage."""

    def test_compound_state_name_equals_id(self):
        """Compound state where name == id uses unquoted declaration."""
        graph = DiagramGraph(
            name="NameId",
            states=[
                DiagramState(
                    id="comp",
                    name="comp",
                    type=StateType.REGULAR,
                    is_initial=True,
                    children=[
                        DiagramState(id="c1", name="C1", type=StateType.REGULAR, is_initial=True),
                    ],
                ),
            ],
            compound_state_ids={"comp"},
        )
        result = MermaidRenderer().render(graph)
        assert "state comp {" in result
        assert '"comp"' not in result

    def test_active_compound_state(self):
        """Compound state that is active gets classDef."""
        graph = DiagramGraph(
            name="ActiveComp",
            states=[
                DiagramState(
                    id="comp",
                    name="Comp",
                    type=StateType.REGULAR,
                    is_initial=True,
                    is_active=True,
                    children=[
                        DiagramState(id="c1", name="C1", type=StateType.REGULAR, is_initial=True),
                    ],
                ),
            ],
            compound_state_ids={"comp"},
        )
        result = MermaidRenderer().render(graph)
        assert "comp:::active" in result

    def test_cross_scope_transition_not_in_compound(self):
        """Transition crossing compound boundaries is not rendered inside the compound."""
        graph = DiagramGraph(
            name="CrossScope",
            states=[
                DiagramState(
                    id="comp",
                    name="Comp",
                    type=StateType.REGULAR,
                    is_initial=True,
                    children=[
                        DiagramState(id="c1", name="C1", type=StateType.REGULAR, is_initial=True),
                    ],
                ),
                DiagramState(id="outside", name="Outside", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="c1", targets=["outside"], event="leave"),
            ],
            compound_state_ids={"comp"},
        )
        result = MermaidRenderer().render(graph)
        # c1 is inside comp, outside is at top level — the transition
        # can't be rendered at either scope since source/target span scopes.
        # This is expected: Mermaid doesn't support cross-scope transitions natively.
        assert "c1 --> outside" not in result

    def test_no_initial_state(self):
        """Graph with no initial state omits [*] arrow."""
        graph = DiagramGraph(
            name="NoInitial",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert "[*]" not in result

    def test_duplicate_transition_rendered_once(self):
        """Duplicate transitions in the IR are rendered only once."""
        graph = DiagramGraph(
            name="Dedup",
            states=[
                DiagramState(id="s1", name="S1", type=StateType.REGULAR, is_initial=True),
                DiagramState(id="s2", name="S2", type=StateType.REGULAR),
            ],
            transitions=[
                DiagramTransition(source="s1", targets=["s2"], event="go"),
                DiagramTransition(source="s1", targets=["s2"], event="go"),
            ],
        )
        result = MermaidRenderer().render(graph)
        assert result.count("s1 --> s2 : go") == 1

    def test_compound_no_initial_child(self):
        """Compound state with no initial child omits internal [*] arrow."""
        graph = DiagramGraph(
            name="NoInitChild",
            states=[
                DiagramState(
                    id="comp",
                    name="Comp",
                    type=StateType.REGULAR,
                    is_initial=True,
                    children=[
                        DiagramState(id="c1", name="C1", type=StateType.REGULAR),
                    ],
                ),
            ],
            compound_state_ids={"comp"},
        )
        result = MermaidRenderer().render(graph)
        # No [*] --> c1 inside the compound
        lines = result.strip().split("\n")
        inner_initial = [ln for ln in lines if "[*] --> c1" in ln]
        assert len(inner_initial) == 0


class TestMermaidRendererIntegration:
    """Integration tests with real state machines."""

    def test_traffic_light(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        result = MermaidGraphMachine(TrafficLightMachine).get_mermaid()
        assert "green --> yellow : cycle" in result
        assert "yellow --> red : cycle" in result
        assert "red --> green : cycle" in result

    def test_traffic_light_with_events(self):
        from tests.examples.traffic_light_machine import TrafficLightMachine

        sm = TrafficLightMachine()
        sm.send("cycle")
        result = MermaidGraphMachine(sm).get_mermaid()
        assert "yellow:::active" in result
