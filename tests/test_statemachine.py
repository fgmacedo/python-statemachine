import pytest
from statemachine.orderedset import OrderedSet

from statemachine import HistoryState
from statemachine import State
from statemachine import StateChart
from statemachine import exceptions
from tests.models import MyModel


def test_machine_repr(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)
    assert (
        repr(machine) == "CampaignMachine(model=MyModel({'state': 'draft'}), "
        "state_field='state', configuration=['draft'])"
    )


def test_machine_should_be_at_start_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert [s.value for s in campaign_machine.states] == [
        "draft",
        "producing",
        "closed",
    ]
    assert [t.name for t in campaign_machine.events] == [
        "add_job",
        "produce",
        "deliver",
    ]

    assert model.state == "draft"
    assert machine.draft.is_active


def test_machine_should_only_allow_only_one_initial_state():
    with pytest.raises(exceptions.InvalidDefinition):

        class CampaignMachine(StateChart):
            "A workflow machine"

            draft = State(initial=True)
            producing = State()
            closed = State(
                "Closed", initial=True
            )  # Should raise an Exception right after the class is defined

            add_job = draft.to(draft) | producing.to(producing)
            produce = draft.to(producing)
            deliver = producing.to(closed)


def test_machine_should_activate_initial_state(mocker):
    spy = mocker.Mock()

    class CampaignMachine(StateChart):
        "A workflow machine"

        draft = State(initial=True)
        producing = State()
        closed = State(final=True)

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

        def on_enter_draft(self):
            spy("draft")
            return "draft"

    sm = CampaignMachine()

    spy.assert_called_once_with("draft")
    assert sm.draft.is_active
    assert sm.draft.is_active

    spy.reset_mock()
    # trying to activate the initial state again should does nothing
    assert sm.activate_initial_state() is None

    spy.assert_not_called()
    assert sm.draft.is_active
    assert sm.draft.is_active


def test_machine_should_not_allow_transitions_from_final_state():
    with pytest.raises(exceptions.InvalidDefinition):

        class CampaignMachine(StateChart):
            "A workflow machine"

            draft = State(initial=True)
            producing = State()
            closed = State(final=True)

            add_job = draft.to(draft) | producing.to(producing) | closed.to(draft)
            produce = draft.to(producing)
            deliver = producing.to(closed)


def test_should_change_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == "draft"
    assert machine.draft.is_active

    machine.produce()

    assert model.state == "producing"
    assert machine.producing.is_active


def test_should_run_a_transition_that_keeps_the_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == "draft"
    assert machine.draft.is_active

    machine.add_job()
    assert model.state == "draft"
    assert machine.draft.is_active

    machine.produce()
    assert model.state == "producing"
    assert machine.producing.is_active

    machine.add_job()
    assert model.state == "producing"
    assert machine.producing.is_active


def test_should_change_state_with_multiple_machine_instances(campaign_machine):
    model1 = MyModel()
    model2 = MyModel()
    machine1 = campaign_machine(model1)
    machine2 = campaign_machine(model2)

    assert machine1.draft.is_active
    assert machine2.draft.is_active

    p1 = machine1.produce
    p2 = machine2.produce

    p2()
    assert machine1.draft.is_active
    assert machine2.producing.is_active

    p1()
    assert machine1.producing.is_active
    assert machine2.producing.is_active


def test_machine_should_list_allowed_events_in_the_current_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == "draft"
    assert [t.name for t in machine.allowed_events] == ["add_job", "produce"]

    machine.produce()
    assert model.state == "producing"
    assert [t.name for t in machine.allowed_events] == ["add_job", "deliver"]

    deliver = machine.allowed_events[1]

    deliver()
    assert model.state == "closed"
    assert machine.allowed_events == []


def test_machine_should_run_a_transition_by_his_key(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == "draft"

    machine.send("add_job")
    assert model.state == "draft"
    assert machine.draft.is_active

    machine.send("produce")
    assert model.state == "producing"
    assert machine.producing.is_active


def test_machine_should_use_and_model_attr_other_than_state(campaign_machine):
    model = MyModel(status="producing")
    machine = campaign_machine(model, state_field="status")

    assert getattr(model, "state", None) is None
    assert model.status == "producing"
    assert machine.producing.is_active

    machine.deliver()

    assert model.status == "closed"
    assert machine.closed.is_active


def test_cant_assign_an_invalid_state_directly(campaign_machine):
    machine = campaign_machine()
    with pytest.raises(exceptions.InvalidStateValue):
        machine.current_state_value = "non existing state"


def test_should_allow_validate_data_for_transition(campaign_machine_with_validator):
    model = MyModel()
    machine = campaign_machine_with_validator(model)

    with pytest.raises(LookupError):
        machine.produce()

    machine.produce(goods="something")

    assert model.state == "producing"


def test_should_check_if_is_in_status(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert machine.draft.is_active
    assert not machine.producing.is_active
    assert not machine.closed.is_active

    machine.produce()

    assert not machine.draft.is_active
    assert machine.producing.is_active
    assert not machine.closed.is_active

    machine.deliver()

    assert not machine.draft.is_active
    assert not machine.producing.is_active
    assert machine.closed.is_active


def test_defined_value_must_be_assigned_to_models(campaign_machine_with_values):
    model = MyModel()
    machine = campaign_machine_with_values(model)

    assert model.state == 1
    machine.produce()
    assert model.state == 2
    machine.deliver()
    assert model.state == 3


def test_state_machine_without_model(campaign_machine):
    machine = campaign_machine()
    assert machine.draft.is_active
    assert not machine.producing.is_active
    assert not machine.closed.is_active

    machine.produce()

    assert not machine.draft.is_active
    assert machine.producing.is_active
    assert not machine.closed.is_active


@pytest.mark.parametrize(
    ("model", "machine_name", "start_value"),
    [
        (None, "campaign_machine", "producing"),
        (None, "campaign_machine_with_values", 2),
        (MyModel(), "campaign_machine", "producing"),
        (MyModel(), "campaign_machine_with_values", 2),
    ],
)
def test_state_machine_with_a_start_value(request, model, machine_name, start_value):
    machine_cls = request.getfixturevalue(machine_name)
    machine = machine_cls(model, start_value=start_value)
    assert not machine.draft.is_active
    assert machine.producing.is_active
    assert not model or model.state == start_value


@pytest.mark.parametrize(
    ("model", "machine_name", "start_value"),
    [
        (None, "campaign_machine", "tapioca"),
        (None, "campaign_machine_with_values", 99),
        (MyModel(), "campaign_machine", "tapioca"),
        (MyModel(), "campaign_machine_with_values", 99),
    ],
)
def test_state_machine_with_a_invalid_start_value(request, model, machine_name, start_value):
    machine_cls = request.getfixturevalue(machine_name)
    with pytest.raises(exceptions.InvalidStateValue):
        machine_cls(model, start_value=start_value)


def test_state_machine_with_a_invalid_model_state_value(request, campaign_machine):
    machine_cls = campaign_machine
    model = MyModel(state="tapioca")
    sm = machine_cls(model)

    with pytest.raises(KeyError):
        sm.configuration  # noqa: B018


def test_should_not_create_instance_of_abstract_machine():
    class EmptyMachine(StateChart):
        "An empty machine"

        pass

    with pytest.raises(exceptions.InvalidDefinition):
        EmptyMachine()


def test_should_not_create_instance_of_machine_without_states():
    s1 = State()

    class OnlyTransitionMachine(StateChart):
        t1 = s1.to.itself()

    with pytest.raises(exceptions.InvalidDefinition):
        OnlyTransitionMachine()


def test_should_not_create_instance_of_machine_without_transitions():
    with pytest.raises(exceptions.InvalidDefinition):

        class NoTransitionsMachine(StateChart):
            "A machine without transitions"

            initial = State(initial=True)


def test_should_not_create_disconnected_machine():
    expected = (
        r"There are unreachable states. The statemachine graph should have a single component. "
        r"Disconnected states: \['blue'\]"
    )
    with pytest.raises(exceptions.InvalidDefinition, match=expected):

        class BrokenTrafficLightMachine(StateChart):
            "A broken traffic light machine"

            green = State(initial=True)
            yellow = State()
            blue = State()  # This state is unreachable

            cycle = green.to(yellow) | yellow.to(green)


def test_should_not_create_big_disconnected_machine():
    expected = (
        r"There are unreachable states. The statemachine graph should have a single component. "
        r"Disconnected states: \[.*\]$"
    )
    with pytest.raises(exceptions.InvalidDefinition, match=expected):

        class BrokenTrafficLightMachine(StateChart):
            "A broken traffic light machine"

            green = State(initial=True)
            yellow = State()
            magenta = State()  # This state is unreachable
            red = State()
            cyan = State()
            blue = State()  # This state is also unreachable

            cycle = green.to(yellow)
            diverge = green.to(cyan) | cyan.to(red)
            validate = yellow.to(green)


def test_disconnected_validation_bypassed_by_flag():
    """Setting validate_disconnected_states=False allows unreachable states."""

    class DisconnectedButAllowed(StateChart):
        validate_disconnected_states = False
        green = State(initial=True)
        yellow = State()
        blue = State()  # unreachable, but flag disables the check

        cycle = green.to(yellow) | yellow.to(green)
        blink = blue.to.itself()

    assert "green" in DisconnectedButAllowed.states_map


def test_parallel_states_reachable_without_disabling_flag():
    """Substates of parallel regions are reachable via hierarchy."""

    class ParallelMachine(StateChart):
        class top(State.Parallel):
            class region1(State.Compound):
                a = State(initial=True)
                b = State(final=True)
                go = a.to(b)

            class region2(State.Compound):
                c = State(initial=True)
                d = State(final=True)
                go2 = c.to(d)

    assert "a" in ParallelMachine.states_map
    assert "c" in ParallelMachine.states_map


def test_compound_substates_reachable_without_disabling_flag():
    """Substates of a compound state are reachable via hierarchy."""

    class CompoundMachine(StateChart):
        start = State(initial=True)

        class parent(State.Compound):
            child1 = State(initial=True)
            child2 = State(final=True)
            inner = child1.to(child2)

        enter = start.to(parent)

    assert "child1" in CompoundMachine.states_map
    assert "child2" in CompoundMachine.states_map


def test_history_state_reachable_without_disabling_flag():
    """History states and their parent compound are reachable via hierarchy."""

    class HistoryMachine(StateChart):
        outside = State(initial=True)

        class compound(State.Compound):
            a = State(initial=True)
            b = State()
            h = HistoryState()
            go = a.to(b)

        enter_via_history = outside.to(compound.h)
        leave = compound.to(outside)

    assert "compound" in HistoryMachine.states_map
    assert "a" in HistoryMachine.states_map


def test_state_value_is_correct():
    STATE_NEW = 0
    STATE_DRAFT = 1

    class ValueTestModel(StateChart):
        new = State(STATE_NEW, value=STATE_NEW, initial=True)
        draft = State(STATE_DRAFT, value=STATE_DRAFT, final=True)

        write = new.to(draft)

    model = ValueTestModel()
    assert model.new.value == STATE_NEW
    assert model.draft.value == STATE_DRAFT


def test_final_states(campaign_machine_with_final_state):
    model = MyModel()
    machine = campaign_machine_with_final_state(model)
    final_states = machine.final_states
    assert len(final_states) == 1
    assert final_states[0].name == "Closed"


def test_should_not_override_states_properties(campaign_machine):
    machine = campaign_machine()
    with pytest.raises(exceptions.StateMachineError) as e:
        machine.draft = "something else"

    assert "State overriding is not allowed. Trying to add 'something else' to draft" in str(e)


class TestWarnings:
    def test_should_warn_if_model_already_has_attribute_and_binding_is_enabled(
        self, campaign_machine_with_final_state, capsys
    ):
        class Model:
            state = "draft"

            def produce(self):
                return f"producing from {self.__class__.__name__!r}"

        model = Model()

        sm = campaign_machine_with_final_state(model)
        with pytest.warns(
            UserWarning, match="Attribute 'produce' already exists on <tests.test.*"
        ):
            sm.bind_events_to(model)

        assert model.produce() == "producing from 'Model'"
        assert sm.current_state_value == "draft"

        assert sm.produce() is None
        assert sm.current_state_value == "producing"

        # event trigger bound to the model
        model.deliver()
        assert sm.current_state_value == "closed"

    def test_should_raise_if_thereis_a_trap_state(self):
        with pytest.raises(
            exceptions.InvalidDefinition,
            match=r"have no outgoing transition: \['state_without_outgoing_transition'\]",
        ):

            class TrapStateMachine(StateChart):
                initial = State(initial=True)
                state_without_outgoing_transition = State()

                t = initial.to(state_without_outgoing_transition)

    def test_should_raise_if_no_path_to_a_final_state(self):
        with pytest.raises(
            exceptions.InvalidDefinition,
            match=r"have no path to a final state: \['producing'\]",
        ):

            class TrapStateMachine(StateChart):
                started = State(initial=True)
                closed = State(final=True)
                producing = State()

                start = started.to(producing)
                close = started.to(closed)
                add_job = producing.to.itself(internal=True)


def test_model_with_custom_bool_is_not_replaced(campaign_machine):
    class FalseyModel(MyModel):
        def __bool__(self):
            return False

    model = FalseyModel()
    machine = campaign_machine(model)

    assert machine.model is model
    assert model.state == "draft"

    machine.produce()
    assert model.state == "producing"


def test_abstract_sm_no_states():
    """A state machine class with no states is abstract."""

    class AbstractSM(StateChart):
        pass

    assert AbstractSM._abstract is True


def test_raise_sends_internal_event():
    """raise_ sends an internal event."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State(final=True)

        internal_event = s1.to(s2)

    sm = SM()
    sm.raise_("internal_event")
    assert sm.s2.is_active


def test_configuration_values_returns_ordered_set():
    """configuration_values returns OrderedSet."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

    sm = SM()
    vals = sm.configuration_values
    assert isinstance(vals, OrderedSet)


def test_states_getitem():
    """States supports index access."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

    assert SM.states[0].id == "s1"
    assert SM.states[1].id == "s2"


def test_multiple_initial_states_raises():
    """Multiple initial states raise InvalidDefinition."""
    with pytest.raises(exceptions.InvalidDefinition, match="one and only one initial state"):

        class BadSM(StateChart):
            s1 = State(initial=True)
            s2 = State(initial=True)

            go = s1.to(s2)


def test_configuration_values_returns_orderedset_when_compound_state():
    """configuration_values returns the OrderedSet directly when it is already one."""
    from statemachine import StateChart

    class SM(StateChart):
        class parent(State.Compound, name="parent"):
            child1 = State(initial=True)
            child2 = State(final=True)

            go = child1.to(child2)

        start = State(initial=True)
        end = State(final=True)

        enter = start.to(parent)
        finish = parent.to(end)

    sm = SM()
    sm.send("enter")
    vals = sm.configuration_values
    assert isinstance(vals, OrderedSet)


class TestEnabledEvents:
    def test_no_conditions_same_as_allowed_events(self, campaign_machine):
        """Without conditions, enabled_events should match allowed_events."""
        sm = campaign_machine()
        assert [e.id for e in sm.enabled_events()] == [e.id for e in sm.allowed_events]

    def test_passing_condition_returns_event(self):
        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="is_ready")

            def is_ready(self):
                return True

        sm = MyMachine()
        assert [e.id for e in sm.enabled_events()] == ["go"]

    def test_failing_condition_excludes_event(self):
        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="is_ready")

            def is_ready(self):
                return False

        sm = MyMachine()
        assert sm.enabled_events() == []

    def test_multiple_transitions_one_passes(self):
        """Same event with multiple transitions: included if at least one passes."""

        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)
            s2 = State(final=True)

            go = s0.to(s1, cond="cond_false") | s0.to(s2, cond="cond_true")

            def cond_false(self):
                return False

            def cond_true(self):
                return True

        sm = MyMachine()
        assert [e.id for e in sm.enabled_events()] == ["go"]

    def test_duplicate_event_across_transitions_deduplicated(self):
        """Same event on multiple passing transitions appears only once."""

        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)
            s2 = State(final=True)

            go = s0.to(s1, cond="cond_a") | s0.to(s2, cond="cond_b")

            def cond_a(self):
                return True

            def cond_b(self):
                return True

        sm = MyMachine()
        ids = [e.id for e in sm.enabled_events()]
        assert ids == ["go"]
        assert len(ids) == 1

    def test_final_state_returns_empty(self, campaign_machine):
        sm = campaign_machine()
        sm.produce()
        sm.deliver()
        assert sm.enabled_events() == []

    def test_kwargs_forwarded_to_conditions(self):
        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="check_value")

            def check_value(self, value=0):
                return value > 10

        sm = MyMachine()
        assert sm.enabled_events() == []
        assert [e.id for e in sm.enabled_events(value=20)] == ["go"]

    def test_condition_exception_treated_as_enabled(self):
        """If a condition raises, the event is treated as enabled (permissive)."""

        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, cond="bad_cond")

            def bad_cond(self):
                raise RuntimeError("boom")

        sm = MyMachine()
        assert [e.id for e in sm.enabled_events()] == ["go"]

    def test_mixed_enabled_and_disabled(self):
        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)
            s2 = State(final=True)

            go = s0.to(s1, cond="cond_true")
            stop = s0.to(s2, cond="cond_false")

            def cond_true(self):
                return True

            def cond_false(self):
                return False

        sm = MyMachine()
        assert [e.id for e in sm.enabled_events()] == ["go"]

    def test_unless_condition(self):
        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, unless="is_blocked")

            def is_blocked(self):
                return True

        sm = MyMachine()
        assert sm.enabled_events() == []

    def test_unless_condition_passes(self):
        class MyMachine(StateChart):
            s0 = State(initial=True)
            s1 = State(final=True)

            go = s0.to(s1, unless="is_blocked")

            def is_blocked(self):
                return False

        sm = MyMachine()
        assert [e.id for e in sm.enabled_events()] == ["go"]


class TestInvalidStateValueNonNone:
    """current_state raises InvalidStateValue when state value is non-None but invalid."""

    def test_invalid_non_none_state_value(self):
        import warnings

        class SM(StateChart):
            idle = State(initial=True)
            active = State(final=True)
            go = idle.to(active)

        sm = SM()
        # Bypass setter validation by writing directly to the model attribute
        setattr(sm.model, sm.state_field, "nonexistent_state")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(exceptions.InvalidStateValue):
                _ = sm.current_state


class TestInitKwargsPropagation:
    """Constructor kwargs are forwarded to initial state entry callbacks."""

    async def test_kwargs_available_in_on_enter_initial(self, sm_runner):
        class SM(StateChart):
            idle = State(initial=True)
            done = State(final=True)
            go = idle.to(done)

            def on_enter_idle(self, greeting=None, **kwargs):
                self.greeting = greeting

        sm = await sm_runner.start(SM, greeting="hello")
        assert sm.greeting == "hello"

    async def test_kwargs_flow_through_eventless_transitions(self, sm_runner):
        class Pipeline(StateChart):
            start = State(initial=True)
            processing = State()
            done = State(final=True)

            start.to(processing)
            processing.to(done)

            def on_enter_start(self, task_id=None, **kwargs):
                self.task_id = task_id

        sm = await sm_runner.start(Pipeline, task_id="abc-123")
        assert sm.task_id == "abc-123"
        assert "done" in sm.configuration_values

    async def test_no_kwargs_still_works(self, sm_runner):
        class SM(StateChart):
            idle = State(initial=True)
            done = State(final=True)
            go = idle.to(done)

            def on_enter_idle(self, **kwargs):
                self.entered = True

        sm = await sm_runner.start(SM)
        assert sm.entered is True

    async def test_multiple_kwargs(self, sm_runner):
        class SM(StateChart):
            idle = State(initial=True)
            done = State(final=True)
            go = idle.to(done)

            def on_enter_idle(self, host=None, port=None, **kwargs):
                self.host = host
                self.port = port

        sm = await sm_runner.start(SM, host="localhost", port=5432)
        assert sm.host == "localhost"
        assert sm.port == 5432

    async def test_kwargs_in_invoke_handler(self, sm_runner):
        """Init kwargs flow to invoke handlers via dependency injection."""

        class SM(StateChart):
            loading = State(initial=True)
            ready = State(final=True)
            done_invoke_loading = loading.to(ready)

            def on_invoke_loading(self, url=None, **kwargs):
                return f"fetched:{url}"

            def on_enter_ready(self, data=None, **kwargs):
                self.result = data

        sm = await sm_runner.start(SM, url="https://example.com")
        await sm_runner.sleep(0.2)
        await sm_runner.processing_loop(sm)
        assert "ready" in sm.configuration_values
        assert sm.result == "fetched:https://example.com"
