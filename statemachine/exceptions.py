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


class MultipleTransitionCallbacksFound(InvalidDefinition):
    """
    You have defined multiple callbacks ``on_execute`` for the same transition.
    """
    def __init__(self, transition):
        self.transition = transition
        msg = _('Multiple callbacks found, you must choose between a callback in the transition'
                'or a bouded method in the state machine class.')
        super(MultipleTransitionCallbacksFound, self).__init__(msg)
