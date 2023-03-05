from .i18n import _


class StateMachineError(Exception):
    "Base exception for this project, all exceptions that can be raised inherit from this class."


class InvalidDefinition(StateMachineError):
    "The state machine has a definition error"


class InvalidStateValue(InvalidDefinition):
    "The current model state value is not mapped to a state definition."

    def __init__(self, value):
        self.value = value
        msg = _("{!r} is not a valid state value.").format(value)
        super().__init__(msg)


class AttrNotFound(InvalidDefinition):
    "There's no method or property with the given name"


class TransitionNotAllowed(StateMachineError):
    "Raised when there's no transition that can run from the current :ref:`state`."

    def __init__(self, event, state):
        self.event = event
        self.state = state
        msg = _("Can't {} when in {}.").format(self.event, self.state.name)
        super().__init__(msg)
