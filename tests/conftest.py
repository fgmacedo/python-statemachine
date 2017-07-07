# coding: utf-8

import pytest


@pytest.fixture
def campaign_machine():
    "Define a new class for each test"
    from statemachine import State, StateMachine

    class CampaignMachine(StateMachine):
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
        green = State('Green', initial=True)
        yellow = State('Yellow')
        red = State('Red')

        @green.to(yellow)
        def slowdown(self, *args, **kwargs):
            return args, kwargs

        @yellow.to(red)
        def stop(self, *args, **kwargs):
            return args, kwargs

        @red.to(green)
        def go(self, *args, **kwargs):
            return args, kwargs

    return TrafficLightMachine
