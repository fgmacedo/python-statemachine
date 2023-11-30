import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import InvalidDefinition
from statemachine.statemachine import Transition

from .models import MyModel


def test_transition_representation(campaign_machine):
    s = repr([t for t in campaign_machine.draft.transitions if t.event == "produce"][0])
    assert s == (
        "Transition("
        "State('Draft', id='draft', value='draft', initial=True, final=False), "
        "State('Being produced', id='producing', value='producing', "
        "initial=False, final=False), event='produce', internal=False)"
    )


def test_list_machine_events(classic_traffic_light_machine):
    machine = classic_traffic_light_machine()
    transitions = [t.name for t in machine.events]
    assert transitions == ["go", "slowdown", "stop"]


def test_list_state_transitions(classic_traffic_light_machine):
    machine = classic_traffic_light_machine()
    events = [t.event for t in machine.green.transitions]
    assert events == ["slowdown"]


def test_transition_should_accept_decorator_syntax(traffic_light_machine):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green


def test_transition_as_decorator_should_call_method_before_activating_state(
    traffic_light_machine,
):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green
    assert (
        machine.cycle(1, 2, number=3, text="x") == "Running cycle from green to yellow"
    )
    assert machine.current_state == machine.yellow


@pytest.mark.parametrize(
    "machine_name",
    [
        "traffic_light_machine",
        "reverse_traffic_light_machine",
    ],
)
def test_cycle_transitions(request, machine_name):
    machine_class = request.getfixturevalue(machine_name)
    machine = machine_class()
    expected_states = ["green", "yellow", "red"] * 2
    for expected_state in expected_states:
        assert machine.current_state.id == expected_state
        machine.cycle()


def test_transition_call_can_only_be_used_as_decorator():
    source, dest = State("Source"), State("Destination")
    transition = Transition(source, dest)

    with pytest.raises(TypeError):
        transition("not a callable")


@pytest.fixture(params=["bounded", "unbounded"])
def transition_callback_machine(request):
    if request.param == "bounded":

        class ApprovalMachine(StateMachine):
            "A workflow"
            requested = State(initial=True)
            accepted = State(final=True)

            validate = requested.to(accepted)

            def on_validate(self):
                self.model.calls.append("on_validate")
                return "accepted"

    elif request.param == "unbounded":

        class ApprovalMachine(StateMachine):
            "A workflow"
            requested = State(initial=True)
            accepted = State(final=True)

            @requested.to(accepted)
            def validate(self):
                self.model.calls.append("on_validate")
                return "accepted"

    else:
        raise ValueError("machine not defined")

    return ApprovalMachine


def test_statemachine_transition_callback(transition_callback_machine):
    model = MyModel(state="requested", calls=[])
    machine = transition_callback_machine(model)
    assert machine.validate() == "accepted"
    assert model.calls == ["on_validate"]


def test_can_run_combined_transitions():
    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State(initial=True)
        producing = State()
        closed = State()

        abort = draft.to(closed) | producing.to(closed) | closed.to(closed)
        produce = draft.to(producing)

    machine = CampaignMachine()

    machine.abort()

    assert machine.closed.is_active


def test_can_detect_stuck_states():

    with pytest.raises(
        InvalidDefinition,
        match="All non-final states should have at least one outgoing transition.",
    ):

        class CampaignMachine(StateMachine, strict_states=True):
            "A workflow machine"
            draft = State(initial=True)
            producing = State()
            paused = State()
            closed = State()

            abort = draft.to(closed) | producing.to(closed) | closed.to(closed)
            produce = draft.to(producing)
            pause = producing.to(paused)


def test_can_detect_unreachable_final_states():

    with pytest.raises(
        InvalidDefinition,
        match="All non-final states should have at least one path to a final state.",
    ):

        class CampaignMachine(StateMachine, strict_states=True):
            "A workflow machine"
            draft = State(initial=True)
            producing = State()
            paused = State()
            closed = State(final=True)

            abort = closed.from_(draft, producing)
            produce = draft.to(producing)
            pause = producing.to(paused) | paused.to.itself()


def test_transitions_to_the_same_estate_as_itself():
    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State(initial=True)
        producing = State()
        closed = State()

        update = draft.to.itself()
        abort = draft.to(closed) | producing.to(closed) | closed.to.itself()
        produce = draft.to(producing)

    machine = CampaignMachine()

    machine.update()

    assert machine.draft.is_active


class TestReverseTransition:
    @pytest.mark.parametrize(
        "initial_state",
        [
            "green",
            "yellow",
            "red",
        ],
    )
    def test_reverse_transition(self, reverse_traffic_light_machine, initial_state):
        machine = reverse_traffic_light_machine(start_value=initial_state)
        assert machine.current_state.id == initial_state

        machine.stop()

        assert machine.red.is_active


def test_should_transition_with_a_dict_as_return():
    "regression test that verifies if a dict can be used as return"

    expected_result = {
        "a": 1,
        "b": 2,
        "c": 3,
    }

    class ApprovalMachine(StateMachine):
        "A workflow"
        requested = State(initial=True)
        accepted = State(final=True)
        rejected = State(final=True)

        accept = requested.to(accepted)
        reject = requested.to(rejected)

        def on_accept(self):
            return expected_result

    machine = ApprovalMachine()

    result = machine.send("accept")
    assert result == expected_result


class TestInternalTransition:
    @pytest.mark.parametrize(
        ("internal", "expected_calls"),
        [
            (False, ["on_exit_initial", "on_enter_initial"]),
            (True, []),
        ],
    )
    def test_should_not_execute_state_actions_on_internal_transitions(
        self, internal, expected_calls
    ):

        calls = []

        class TestStateMachine(StateMachine):
            initial = State(initial=True)

            loop = initial.to.itself(internal=internal)

            def on_exit_initial(self):
                calls.append("on_exit_initial")

            def on_enter_initial(self):
                calls.append("on_enter_initial")

        sm = TestStateMachine()
        calls.clear()
        sm.loop()
        assert calls == expected_calls

    def test_should_not_allow_internal_transitions_from_distinct_states(self):

        with pytest.raises(
            InvalidDefinition, match="Internal transitions should be self-transitions."
        ):

            class TestStateMachine(StateMachine):
                initial = State(initial=True)
                final = State(final=True)

                execute = initial.to(initial, final, internal=True)


class TestAllowEventWithoutTransition:
    def test_send_unknown_event(self, classic_traffic_light_machine):
        sm = classic_traffic_light_machine(allow_event_without_transition=True)
        assert sm.green.is_active
        sm.send("unknow_event")
        assert sm.green.is_active

    def test_send_not_valid_for_the_current_state_event(
        self, classic_traffic_light_machine
    ):
        sm = classic_traffic_light_machine(allow_event_without_transition=True)
        assert sm.green.is_active
        sm.stop()
        assert sm.green.is_active
