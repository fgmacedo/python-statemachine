# coding: utf-8
from __future__ import absolute_import, unicode_literals


import pytest

from statemachine import Transition, State


def test_transition_representation(campaign_machine):
    s = repr([t for t in campaign_machine.transitions if t.identifier == 'produce'][0])
    print(s)
    assert s == (
        "Transition("
         "State('Draft', identifier='draft', value='draft', initial=True), "
         "(State('Being produced', identifier='producing', value='producing', initial=False),), identifier='produce')"
    )


def test_transition_should_accept_decorator_syntax(traffic_light_machine):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green


def test_transition_as_decorator_should_call_method_before_activating_state(traffic_light_machine):
    machine = traffic_light_machine()
    assert machine.current_state == machine.green
    assert machine.slowdown(1, 2, number=3, text='x') == ((1, 2), {'number': 3, 'text': 'x'})
    assert machine.current_state == machine.yellow


def test_transition_call_can_only_be_used_as_decorator():
    source, dest = State('Source'), State('Destination')
    transition = Transition(source, dest)

    with pytest.raises(ValueError):
        transition('not a callable')
