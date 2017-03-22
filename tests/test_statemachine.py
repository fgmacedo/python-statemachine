# coding: utf-8

import pytest

from statemachine import StateMachine, State


class MyModel(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.__dict__)


@pytest.fixture
def campaign_machine(request):
    "Define a new class for each test"

    class CampaignMachine(StateMachine):
        draft = State('Draft', initial=True)
        producing = State('Being produced')
        closed = State('Closed')

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    return CampaignMachine


def test_machine_should_be_at_start_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert [s.value for s in campaign_machine.states] == ['closed', 'draft', 'producing']
    assert [t.key for t in campaign_machine.transitions] == ['add_job', 'deliver', 'produce']

    assert model.state == 'draft'
    assert machine.current_state == machine.draft


def test_machine_should_only_allow_only_one_initial_state():
    class CampaignMachine(StateMachine):
        draft = State('Draft', initial=True)
        producing = State('Being produced')
        closed = State('Closed', initial=True)  # Should raise an Exception when instantiated

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    with pytest.raises(ValueError):
        model = MyModel()
        CampaignMachine(model)


def test_transition_representation(campaign_machine):
    s = repr([t for t in campaign_machine.transitions if t.key == 'produce'][0])
    print(s)
    assert s == ("Transition("
                 "State('Draft', identifier='draft', value='draft', initial=True), "
                 "State('Being produced', identifier='producing', value='producing', initial=False), key='produce')")


def test_should_change_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == 'draft'
    assert machine.current_state == machine.draft

    machine.produce()

    assert model.state == 'producing'
    assert machine.current_state == machine.producing


def test_should_run_a_transition_that_keeps_the_state(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == 'draft'
    assert machine.current_state == machine.draft

    machine.add_job()
    assert model.state == 'draft'
    assert machine.current_state == machine.draft

    machine.produce()
    assert model.state == 'producing'
    assert machine.current_state == machine.producing

    machine.add_job()
    assert model.state == 'producing'
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


def test_call_to_transition_that_is_not_in_the_current_state_should_raise_exception(
        campaign_machine):

    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == 'draft'
    assert machine.current_state == machine.draft

    with pytest.raises(LookupError):
        machine.deliver()


def test_machine_should_list_allowed_transitions_in_the_current_state(campaign_machine):

    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == 'draft'
    assert [t.key for t in machine.allowed_transitions] == ['add_job', 'produce']

    machine.produce()
    assert model.state == 'producing'
    assert [t.key for t in machine.allowed_transitions] == ['add_job', 'deliver']

    deliver = machine.allowed_transitions[1]

    deliver()
    assert model.state == 'closed'
    assert machine.allowed_transitions == []


def test_machine_should_run_a_transition_by_his_key(campaign_machine):

    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == 'draft'

    machine.run('add_job')
    assert model.state == 'draft'
    assert machine.current_state == machine.draft

    machine.run('produce')
    assert model.state == 'producing'
    assert machine.current_state == machine.producing


def test_machine_should_raise_an_exception_if_a_transition_by_his_key_is_not_found(
        campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert model.state == 'draft'

    with pytest.raises(ValueError):
        machine.run('go_horse')


def test_machine_should_use_and_model_attr_other_than_state(campaign_machine):
    model = MyModel(status='producing')
    machine = campaign_machine(model, state_field='status')

    assert getattr(model, 'state', None) is None
    assert model.status == 'producing'
    assert machine.current_state == machine.producing

    machine.deliver()

    assert model.status == 'closed'
    assert machine.current_state == machine.closed


def test_should_allow_validate_data_for_transition(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    def custom_validator(*args, **kwargs):
        if 'weapon' not in kwargs:
            raise LookupError('Weapon not found.')

    campaign_machine.produce.validators = [custom_validator]

    with pytest.raises(LookupError):
        machine.produce()

    machine.produce(weapon='sword')

    assert model.state == 'producing'


def test_should_allow_plug_an_event_on_running_a_transition(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    def double(self, *args, **kwargs):
        return kwargs.get('value', 0) * 2

    campaign_machine.on_add_job = double

    assert machine.add_job() == 0
    assert machine.add_job(value=2) == 4


def test_should_check_if_is_in_status(campaign_machine):
    model = MyModel()
    machine = campaign_machine(model)

    assert machine.is_draft
    assert not machine.is_producing
    assert not machine.is_closed

    machine.produce()

    assert not machine.is_draft
    assert machine.is_producing
    assert not machine.is_closed

    machine.deliver()

    assert not machine.is_draft
    assert not machine.is_producing
    assert machine.is_closed


def test_defined_value_must_be_assigned_to_models():
    class CampaignMachineWithKeys(StateMachine):
        draft = State('Draft', initial=True, value=1)
        producing = State('Being produced', value=2)
        closed = State('Closed', value=3)

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    model = MyModel()
    machine = CampaignMachineWithKeys(model)

    assert model.state == 1
    machine.produce()
    assert model.state == 2
    machine.deliver()
    assert model.state == 3
