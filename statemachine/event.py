from inspect import isawaitable
from typing import TYPE_CHECKING

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
    id: str
    name: str
    _sm: "StateMachine | None" = None
    _transitions: "TransitionList | None" = None

    def __new__(
        cls,
        positional_arg: "str | TransitionList | None" = None,
        id: "str | None" = None,
        name: "str | None" = None,
        sm: "StateMachine | None" = None,
    ):
        if isinstance(positional_arg, str):
            id = positional_arg
            transitions = None
        else:
            transitions = positional_arg

        id = str(id) if id is not None else ""

        instance = super().__new__(cls, id)
        instance.id = id
        instance.name = name if name is not None else str(id)
        if transitions:
            instance._transitions = transitions
        instance._sm = sm
        return instance

    def __repr__(self):
        return f"{type(self).__name__}({self.id!r})"

    def is_same_event(self, *_args, event: "str | None" = None, **_kwargs) -> bool:
        return self == event

    def __get__(self, instance, owner):
        """By implementing this method `Event` can be used as a property descriptor

        So when attached to a SM class, if the user tries to get the `Event` instance,
        we intercept here and return a `BoundEvent` instance, so the user can call
        it as a method with the correct SM instance.

        """
        if instance is None:
            return self
        return BoundEvent(id=self.id, name=self.name, sm=instance)

    def __call__(self, *args, **kwargs):
        """Send this event to the current state machine."""
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


class BoundEvent(Event):
    pass
