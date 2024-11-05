from inspect import isawaitable
from typing import TYPE_CHECKING
from typing import List
from uuid import uuid4

from statemachine.utils import run_async_from_sync

from .event_data import TriggerData

if TYPE_CHECKING:
    from .statemachine import StateMachine
    from .transition_list import TransitionList


_event_data_kwargs = {
    "event_data",
    "machine",
    "event",
    "model",
    "transition",
    "state",
    "source",
    "target",
}


class Event(str):
    """An event is triggers a signal that something has happened.

    They are send to a state machine and allow the state machine to react.

    An event starts a :ref:`Transition`, which can be thought of as a “cause” that initiates a
    change in the state of the system.

    See also :ref:`events`.
    """

    id: str
    """The event identifier."""

    name: str
    """The event name."""

    _sm: "StateMachine | None" = None
    """The state machine instance."""

    _transitions: "TransitionList | None" = None
    _has_real_id = False

    def __new__(
        cls,
        transitions: "str | TransitionList | None" = None,
        id: "str | None" = None,
        name: "str | None" = None,
        _sm: "StateMachine | None" = None,
    ):
        if isinstance(transitions, str):
            id = transitions
            transitions = None

        _has_real_id = id is not None
        id = str(id) if _has_real_id else f"__event__{uuid4().hex}"

        instance = super().__new__(cls, id)
        instance.id = id
        if name:
            instance.name = name
        elif _has_real_id:
            instance.name = str(id).replace("_", " ").capitalize()
        else:
            instance.name = ""
        if transitions:
            instance._transitions = transitions
        instance._has_real_id = _has_real_id
        instance._sm = _sm
        return instance

    def __repr__(self):
        return f"{type(self).__name__}({self.id!r})"

    def is_same_event(self, *_args, event: "str | None" = None, **_kwargs) -> bool:
        return self == event

    def __get__(self, instance, owner):
        """By implementing this method `Event` can be used as a property descriptor

        When attached to a SM class, if the user tries to get the `Event` instance,
        we intercept here and return a `BoundEvent` instance, so the user can call
        it as a method with the correct SM instance.

        """
        if instance is None:
            return self
        return BoundEvent(id=self.id, name=self.name, _sm=instance)

    def __call__(self, *args, **kwargs):
        """Send this event to the current state machine.

        Triggering an event on a state machine means invoking or sending a signal, initiating the
        process that may result in executing a transition.
        """
        # The `__call__` is declared here to help IDEs knowing that an `Event`
        # can be called as a method. But it is not meant to be called without
        # an SM instance. Such SM instance is provided by `__get__` method when
        # used as a property descriptor.

        machine = self._sm
        kwargs = {k: v for k, v in kwargs.items() if k not in _event_data_kwargs}
        trigger_data = TriggerData(
            machine=machine,
            event=self,
            args=args,
            kwargs=kwargs,
        )
        machine._put_nonblocking(trigger_data)
        result = machine._processing_loop()
        if not isawaitable(result):
            return result
        return run_async_from_sync(result)

    def split(  # type: ignore[override]
        self, sep: "str | None" = None, maxsplit: int = -1
    ) -> List["Event"]:
        result = super().split(sep, maxsplit)
        if len(result) == 1:
            return [self]
        return [Event(event) for event in result]


class BoundEvent(Event):
    pass
