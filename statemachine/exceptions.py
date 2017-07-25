# coding: utf-8
from __future__ import absolute_import, unicode_literals

from .utils import ugettext as _


class StateMachineError(Exception):
    "Base exception for this project, all exceptions that can be raised inherit from this class."


class InvalidDefinition(StateMachineError):
    "The state machine has a definition error"


class InvalidStateValue(InvalidDefinition):
    "The current model state value is not mapped to a state definition."

    def __init__(self, value):
        self.value = value
        msg = _("{!r} is not a valid state value.").format(value)
        super(InvalidStateValue, self).__init__(msg)


class InvalidTransitionIdentifier(InvalidDefinition):
    "There's no transition with the given identifier."

    def __init__(self, identifier):
        self.identifier = identifier
        msg = _('{!r} is not a valid transition identifier').format(identifier)
        super(InvalidTransitionIdentifier, self).__init__(msg)


class InvalidDestinationState(InvalidDefinition):
    """
    In the case of multiple destination states, you've returned a state that is not in the
    possible destinations for the current transition.
    """
    def __init__(self, transition, destination):
        self.transition = transition
        self.destination = destination
        msg = _('{destination.name} is not a possible destination state for '
                '{transition.identifier} transition.').format(
            transition=transition,
            destination=destination,

        )
        super(InvalidDestinationState, self).__init__(msg)


class TransitionNotAllowed(StateMachineError):
    "The transition can't run from the current state."

    def __init__(self, transition, state):
        self.transition = transition
        self.state = state
        msg = _("Can't {} when in {}.").format(
            self.transition.identifier,
            self.state.name
        )
        super(TransitionNotAllowed, self).__init__(msg)


class MultipleStatesFound(StateMachineError):
    """
    You have mapped a transition from one state to multiple states. In this case, there's no way
    to determine what is the desired destination state, so you must inform it when the transition
    is called.

    You can inform the transition on the `on_execute` callback.
    """
    def __init__(self, transition):
        self.transition = transition
        msg = _('Multiple destinations, you must return the desired state as: '
                '`return <State>` or `return <result>, <State>`.')
        super(MultipleStatesFound, self).__init__(msg)


class MultipleTransitionCallbacksFound(InvalidDefinition):
    """
    You have defined multiple callbacks ``on_execute`` for the same transition.
    """
    def __init__(self, transition):
        self.transition = transition
        msg = _('Multiple callbacks found, you must choose between a callback in the transition'
                'or a bouded method in the state machine class.')
        super(MultipleTransitionCallbacksFound, self).__init__(msg)
