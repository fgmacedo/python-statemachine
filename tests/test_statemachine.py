# coding: utf-8
import pytest

from statemachine import exceptions
from statemachine import State
from statemachine import StateMachine


class MyModel(object):
    "A class that can be used to hold arbitrary key/value pairs as attributes."

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.__dict__)


def test_machine_repr(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)
    assert (
        repr(machine) == "CampaignMachine(model=MyModel({'state': 'draft'}), "
        "state_field='state', current_state='draft')"
    )


def test_machine_should_be_at_start_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert [s.value for s in campaign_machine.states] == [
        "closed",
        "draft",
        "producing",
    ]
    assert [t.name for t in campaign_machine.events] == [
        "add_job",
        "deliver",
        "produce",
    ]  # noqa: E501

    assert model.state == "draft"
    assert machine.current_state == machine.draft


def test_machine_should_only_allow_only_one_initial_state():
    with pytest.raises(exceptions.InvalidDefinition):

        class CampaignMachine(StateMachine):
            "A workflow machine"
            draft = State("Draft", initial=True)
            producing = State("Being produced")
            closed = State(
                "Closed", initial=True
            )  # Should raise an Exception right after the class is defined

            add_job = draft.to(draft) | producing.to(producing)
            produce = draft.to(producing)
            deliver = producing.to(closed)


def test_machine_should_not_allow_transitions_from_final_state():
    with pytest.raises(exceptions.InvalidDefinition):

        class CampaignMachine(StateMachine):
            "A workflow machine"
            draft = State("Draft", initial=True)
            producing = State("Being produced")
            closed = State("Closed", final=True)

            add_job = draft.to(draft) | producing.to(producing) | closed.to(draft)
            produce = draft.to(producing)
            deliver = producing.to(closed)


def test_should_change_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == "draft"
    assert machine.current_state == machine.draft

    machine.produce()

    assert model.state == "producing"
    assert machine.current_state == machine.producing


def test_should_run_a_transition_that_keeps_the_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == "draft"
    assert machine.current_state == machine.draft

    machine.add_job()
    assert model.state == "draft"
    assert machine.current_state == machine.draft

    machine.produce()
    assert model.state == "producing"
    assert machine.current_state == machine.producing

    machine.add_job()
    assert model.state == "producing"
    assert machine.current_state == machine.producing


def test_should_change_state_with_multiple_machine_instances(campaign_machine):
    model1 = MyModel()
    model2 = MyModel()
    machine1 = campaign_machine(model1)
    machine2 = campaign_machine(model2)

    assert machine1.current_state == campaign_machine.draft
    assert machine2.current_state == campaign_machine.draft

    p1 = machine1.produce
    p2 = machine2.produce

    p2()
    assert machine1.current_state == campaign_machine.draft
    assert machine2.current_state == campaign_machine.producing

    p1()
    assert machine1.current_state == campaign_machine.producing
    assert machine2.current_state == campaign_machine.producing


@pytest.mark.parametrize(
    "current_state, transition",
    [
        ("draft", "deliver"),
        ("closed", "add_job"),
    ],
)
def test_call_to_transition_that_is_not_in_the_current_state_should_raise_exception(
    campaign_machine, current_state, transition
):

    model = MyModel(state=current_state)
    machine = campaign_machine(model)

    assert machine.current_state.value == current_state

    with pytest.raises(exceptions.TransitionNotAllowed):
        machine.send(transition)


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
    assert machine.current_state == machine.draft

    machine.send("produce")
    assert model.state == "producing"
    assert machine.current_state == machine.producing


def test_machine_should_raise_an_exception_if_a_transition_by_his_key_is_not_found(
    campaign_machine,
):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == "draft"

    with pytest.raises(exceptions.TransitionNotAllowed):
        machine.send("go_horse")


def test_machine_should_use_and_model_attr_other_than_state(campaign_machine):
    model = MyModel(status="producing")
    machine = campaign_machine(model, state_field="status")

    assert getattr(model, "state", None) is None
    assert model.status == "producing"
    assert machine.current_state == machine.producing

    machine.deliver()

    assert model.status == "closed"
    assert machine.current_state == machine.closed


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
    "model, machine_name, start_value",
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
    "model, machine_name, start_value",
    [
        (None, "campaign_machine", "tapioca"),
        (None, "campaign_machine_with_values", 99),
        (MyModel(), "campaign_machine", "tapioca"),
        (MyModel(), "campaign_machine_with_values", 99),
    ],
)
def test_state_machine_with_a_invalid_start_value(
    request, model, machine_name, start_value
):
    machine_cls = request.getfixturevalue(machine_name)
    with pytest.raises(exceptions.InvalidStateValue):
        machine_cls(model, start_value=start_value)


def test_should_not_create_instance_of_machine_without_states():

    with pytest.raises(exceptions.InvalidDefinition):

        class EmptyMachine(StateMachine):
            "An empty machine"
            pass


def test_should_not_create_instance_of_machine_without_transitions():

    with pytest.raises(exceptions.InvalidDefinition):

        class NoTransitionsMachine(StateMachine):
            "A machine without transitions"
            initial = State("initial", initial=True)


def test_should_not_create_disconnected_machine():

    with pytest.raises(exceptions.InvalidDefinition) as e:

        class BrokenTrafficLightMachine(StateMachine):
            "A broken traffic light machine"
            green = State("Green", initial=True)
            yellow = State("Yellow")
            blue = State("Blue")  # This state is unreachable

            cycle = green.to(yellow) | yellow.to(green)

        assert "Blue" in e.message
        assert "Green" not in e.message


def test_should_not_create_big_disconnected_machine():
    with pytest.raises(exceptions.InvalidDefinition) as e:

        class BrokenTrafficLightMachine(StateMachine):
            "A broken traffic light machine"
            green = State("Green", initial=True)
            yellow = State("Yellow")
            magenta = State("Magenta")  # This state is unreachable
            red = State("Red")
            cyan = State("Cyan")
            blue = State("Blue")  # This state is also unreachable

            cycle = green.to(yellow)
            diverge = green.to(cyan) | cyan.to(red)
            validate = yellow.to(green)

        assert "Magenta" in e.message
        assert "Blue" in e.message
        assert "Cyan" not in e.message


def test_state_value_is_correct():
    STATE_NEW = 0
    STATE_DRAFT = 1

    class ValueTestModel(StateMachine):
        new = State(STATE_NEW, value=STATE_NEW, initial=True)
        draft = State(STATE_DRAFT, value=STATE_DRAFT)

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

    assert (
        "State overriding is not allowed. Trying to add 'something else' to draft"
        in str(e)
    )
