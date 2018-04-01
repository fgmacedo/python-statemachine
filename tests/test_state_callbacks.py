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
            event_mock.on_enter_green()

        def on_exit_green(self):
            event_mock.on_exit_green()

        def on_enter_yellow(self):
            event_mock.on_enter_yellow()

        def on_exit_yellow(self):
            event_mock.on_exit_yellow()

        def on_enter_red(self):
            event_mock.on_enter_red()

        def on_exit_red(self):
            event_mock.on_exit_red()

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
        event_mock.on_enter_yellow.assert_called_once_with()

    def test_should_call_on_exit_of_specific_state(self, event_mock, traffic_light_machine):
        machine = traffic_light_machine()
        machine.cycle()
        event_mock.on_exit_green.assert_called_once_with()
