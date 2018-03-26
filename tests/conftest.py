# coding: utf-8

import pytest
from datetime import datetime


@pytest.fixture
def current_time():
    return datetime.now()


@pytest.fixture
def campaign_machine():
    "Define a new class for each test"
    from statemachine import State, StateMachine

    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State('Draft', initial=True)
        producing = State('Being produced')
        closed = State('Closed')

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    return CampaignMachine


@pytest.fixture
def campaign_machine_with_values():
    "Define a new class for each test"
    from statemachine import State, StateMachine

    class CampaignMachineWithKeys(StateMachine):
        "A workflow machine"
        draft = State('Draft', initial=True, value=1)
        producing = State('Being produced', value=2)
        closed = State('Closed', value=3)

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)
        deliver = producing.to(closed)

    return CampaignMachineWithKeys


@pytest.fixture
def traffic_light_machine():
    from statemachine import StateMachine, State

    class TrafficLightMachine(StateMachine):
        "A traffic light machine"
        green = State('Green', initial=True)
        yellow = State('Yellow')
        red = State('Red')

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        @green.to(yellow)
        def slowdown(self, *args, **kwargs):
            return args, kwargs

        @yellow.to(red)
        def stop(self, *args, **kwargs):
            return args, kwargs

        @red.to(green)
        def go(self, *args, **kwargs):
            return args, kwargs

        def on_cicle(self, *args, **kwargs):
            return args, kwargs

    return TrafficLightMachine


@pytest.fixture
def approval_machine(current_time):
    from statemachine import StateMachine, State

    class ApprovalMachine(StateMachine):
        "A workflow machine"
        requested = State('Requested', initial=True)
        accepted = State('Accepted')
        rejected = State('Rejected')

        completed = State('Completed')

        @requested.to(accepted, rejected)
        def validate(self, *args, **kwargs):
            if self.model.is_ok():
                self.model.accepted_at = current_time
                return self.model, self.accepted
            else:
                self.model.rejected_at = current_time
                return self.model, self.rejected

        @accepted.to(completed)
        def complete(self):
            self.model.completed_at = current_time

        @requested.to(requested)
        def update(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self.model, k, v)
            return self.model

        @rejected.to(requested)
        def retry(self):
            self.model.rejected_at = None
            return self.model

    return ApprovalMachine
