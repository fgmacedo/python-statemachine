# coding: utf-8
from statemachine import StateMachine, Transition, State
from typing import Type


def _process_transition(transition):
    # type: (Transition) -> str

    result = ''
    for destination in transition.destinations:
        result += '{}->{}[label="{}"];'.format(
            transition.source.identifier, destination.identifier, transition.identifier
        )

    return result


def _process_state(state):
    # type: (State) -> str

    if state.initial:
        return '{}[color=blue];'.format(state.identifier)
    else:
        return '{};'.format(state.identifier)


def dot_data_from_machine(machine_class_type):
    # type: (Type[StateMachine]) -> str
    result = 'labelloc="t"; label="{}";'.format(machine_class_type.__name__)

    for state in machine_class_type.states:
        result += _process_state(state)
        for transition in state.transitions:
            result += _process_transition(transition)

    return 'digraph {} {{{}}}'.format(machine_class_type.__name__, result)
