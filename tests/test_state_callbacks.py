# coding: utf-8
from __future__ import absolute_import, unicode_literals

import mock
import pytest


@pytest.fixture()
def event_mock():
    return mock.MagicMock()


@pytest.fixture()
def traffic_light_machine(event_mock):
    from statemachine import StateMachine, State

    class TrafficLightMachineStateEvents(StateMachine):
        "A traffic light machine"
        green = State('Green', initial=True)
        yellow = State('Yellow')
        red = State('Red')

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        def on_enter_state(self, state):
            event_mock.on_enter_state(state)

        def on_exit_state(self, state):
            event_mock.on_exit_state(state)

        def on_enter_green(self):
            event_mock.on_enter_green(self)

        def on_exit_green(self):
            event_mock.on_exit_green(self)

        def on_enter_yellow(self):
            event_mock.on_enter_yellow(self)

        def on_exit_yellow(self):
            event_mock.on_exit_yellow(self)

        def on_enter_red(self):
            event_mock.on_enter_red(self)

        def on_exit_red(self):
            event_mock.on_exit_red(self)

    return TrafficLightMachineStateEvents


class TestStateCallbacks(object):

    def test_should_call_on_enter_generic_state(self, event_mock, traffic_light_machine):
        machine = traffic_light_machine()
        machine.cycle()
        event_mock.on_enter_state.assert_called_once_with(machine.yellow)

    def test_should_call_on_exit_generic_state(self, event_mock, traffic_light_machine):
        machine = traffic_light_machine()
        machine.cycle()
        event_mock.on_exit_state.assert_called_once_with(machine.green)

    def test_should_call_on_enter_of_specific_state(self, event_mock, traffic_light_machine):
        machine = traffic_light_machine()
        machine.cycle()
        event_mock.on_enter_yellow.assert_called_once_with(machine)

    def test_should_call_on_exit_of_specific_state(self, event_mock, traffic_light_machine):
        machine = traffic_light_machine()
        machine.cycle()
        event_mock.on_exit_green.assert_called_once_with(machine)

    def test_should_be_on_the_previous_state_when_exiting(self, event_mock, traffic_light_machine):
        machine = traffic_light_machine()

        def assert_is_green_from_state(s):
            assert s.value == 'green'

        def assert_is_green(m):
            assert m.is_green

        event_mock.on_exit_state.side_effect = assert_is_green_from_state
        event_mock.on_exit_green.side_effect = assert_is_green

        machine.cycle()

    def test_should_be_on_the_next_state_when_entering(self, event_mock, traffic_light_machine):
        machine = traffic_light_machine()

        def assert_is_yellow_from_state(s):
            assert s.value == 'yellow'

        def assert_is_yellow(m):
            assert m.is_yellow

        event_mock.on_enter_state.side_effect = assert_is_yellow_from_state
        event_mock.on_enter_yellow.side_effect = assert_is_yellow

        machine.cycle()
