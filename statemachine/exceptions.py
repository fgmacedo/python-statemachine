from typing import TYPE_CHECKING

from .i18n import _

if TYPE_CHECKING:
    from .state import State


class StateMachineError(Exception):
    "Base exception for this project, all exceptions that can be raised inherit from this class."


class InvalidDefinition(StateMachineError):
    "The state machine has a definition error"


class InvalidStateValue(InvalidDefinition):
    "The current model state value is not mapped to a state definition."

    def __init__(self, value, msg=None):
        self.value = value
        if msg is None:
            msg = _("{!r} is not a valid state value.").format(value)
        super().__init__(msg)


class AttrNotFound(InvalidDefinition):
    "There's no method or property with the given name"


class TransitionNotAllowed(StateMachineError):
    "Raised when there's no transition that can run from the current :ref:`state`."

    def __init__(self, event: str, state: "State"):
        self.event = event
        self.state = state
        msg = _("Can't {} when in {}.").format(self.event, self.state.name)
        super().__init__(msg)
