import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.exceptions import InvalidDefinition
from statemachine.transition import Transition

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
    assert transitions == ["slowdown", "stop", "go"]


def test_list_state_transitions(classic_traffic_light_machine):
    machine = classic_traffic_light_machine()
    events = [t.event for t in machine.green.transitions]
    assert events == ["slowdown"]


def test_transition_should_accept_decorator_syntax(traffic_light_machine):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green


def test_transition_as_decorator_should_call_method_before_activating_state(
    traffic_light_machine, capsys
):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green
    machine.cycle(1, 2, number=3, text="x")
    assert machine.current_state == machine.yellow

    captured = capsys.readouterr()
    assert captured.out == "Running cycle from green to yellow\n"


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
        self, internal, expected_calls, engine
    ):
        calls = []

        class TestStateMachine(StateMachine):
            initial = State(initial=True)

            loop = initial.to.itself(internal=internal)

            def _get_engine(self, rtc: bool):
                return engine(self, rtc)

            def on_exit_initial(self):
                calls.append("on_exit_initial")

            def on_enter_initial(self):
                calls.append("on_enter_initial")

        sm = TestStateMachine()
        sm.activate_initial_state()

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
        sm.activate_initial_state()  # no-op on sync engine

        assert sm.green.is_active
        sm.send("unknow_event")
        assert sm.green.is_active

    def test_send_not_valid_for_the_current_state_event(self, classic_traffic_light_machine):
        sm = classic_traffic_light_machine(allow_event_without_transition=True)
        sm.activate_initial_state()  # no-op on sync engine

        assert sm.green.is_active
        sm.stop()
        assert sm.green.is_active


class TestTransitionFromAny:
    @pytest.fixture()
    def account_sm(self):
        class AccountStateMachine(StateMachine):
            active = State("Active", initial=True)
            suspended = State("Suspended")
            overdrawn = State("Overdrawn")
            closed = State("Closed", final=True)

            # Define transitions between states
            suspend = active.to(suspended)
            activate = suspended.to(active)
            overdraft = active.to(overdrawn)
            resolve_overdraft = overdrawn.to(active)

            close_account = closed.from_.any(cond="can_close_account")

            can_close_account: bool = True

            # Actions performed during transitions
            def on_close_account(self):
                print("Account has been closed.")

        return AccountStateMachine

    def test_transition_from_any(self, account_sm):
        sm = account_sm()
        sm.close_account()
        assert sm.closed.is_active

    def test_can_close_from_every_state(self, account_sm):
        sm = account_sm()
        states_can_close = {}
        for state in sm.states:
            for transition in state.transitions:
                print(f"{state.id} -({transition.event})-> {transition.target.id}")
                if transition.target == sm.closed:
                    states_can_close[state.id] = state

        assert list(states_can_close) == ["active", "suspended", "overdrawn"]

    def test_transition_from_any_with_cond(self, account_sm):
        sm = account_sm()
        sm.can_close_account = False
        with pytest.raises(sm.TransitionNotAllowed):
            sm.close_account()
        assert sm.active.is_active

    def test_any_can_be_used_as_decorator(self):
        class AccountStateMachine(StateMachine):
            active = State("Active", initial=True)
            suspended = State("Suspended")
            overdrawn = State("Overdrawn")
            closed = State("Closed", final=True)

            # Define transitions between states
            suspend = active.to(suspended)
            activate = suspended.to(active)
            overdraft = active.to(overdrawn)
            resolve_overdraft = overdrawn.to(active)

            close_account = closed.from_.any()

            flag_for_debug: bool = False

            @close_account.on
            def do_close_account(self):
                self.flag_for_debug = True

        sm = AccountStateMachine()
        sm.close_account()
        assert sm.closed.is_active
        assert sm.flag_for_debug is True
