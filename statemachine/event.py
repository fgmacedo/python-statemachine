from typing import TYPE_CHECKING
from typing import List
from typing import cast
from uuid import uuid4

from .callbacks import CallbackGroup
from .event_data import TriggerData
from .exceptions import InvalidDefinition
from .i18n import _
from .transition_mixin import AddCallbacksMixin

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


class Event(AddCallbacksMixin, str):
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

    delay: float = 0
    """The delay in milliseconds before the event is triggered. Default is 0."""

    internal: bool = False
    """Indicates if the events should be placed on the internal event queue."""

    _sm: "StateMachine | None" = None
    """The state machine instance."""

    _transitions: "TransitionList | None" = None
    _has_real_id = False

    def __new__(
        cls,
        transitions: "str | TransitionList | None" = None,
        id: "str | None" = None,
        name: "str | None" = None,
        delay: float = 0,
        internal: bool = False,
        _sm: "StateMachine | None" = None,
    ):
        if isinstance(transitions, str):
            id = transitions
            transitions = None

        _has_real_id = id is not None
        id = str(id) if _has_real_id else f"__event__{uuid4().hex}"

        instance = super().__new__(cls, id)
        instance.id = id
        instance.delay = delay
        instance.internal = internal
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
        return (
            f"{type(self).__name__}({self.id!r}, delay={self.delay!r}, internal={self.internal!r})"
        )

    def is_same_event(self, *_args, event: "str | None" = None, **_kwargs) -> bool:
        return self == event

    def _add_callback(self, callback, grouper: CallbackGroup, is_event=False, **kwargs):
        if self._transitions is None:
            raise InvalidDefinition(
                _("Cannot add callback '{}' to an event with no transitions.").format(callback)
            )
        return self._transitions._add_callback(
            callback=callback,
            grouper=grouper,
            is_event=is_event,
            **kwargs,
        )

    def __get__(self, instance, owner):
        """By implementing this method `Event` can be used as a property descriptor

        When attached to a SM class, if the user tries to get the `Event` instance,
        we intercept here and return a `BoundEvent` instance, so the user can call
        it as a method with the correct SM instance.

        """
        if instance is None:
            return self
        return BoundEvent(id=self.id, name=self.name, delay=self.delay, _sm=instance)

    def put(self, *args, send_id: "str | None" = None, **kwargs):
        # The `__call__` is declared here to help IDEs knowing that an `Event`
        # can be called as a method. But it is not meant to be called without
        # an SM instance. Such SM instance is provided by `__get__` method when
        # used as a property descriptor.
        assert self._sm is not None
        trigger_data = self.build_trigger(*args, machine=self._sm, send_id=send_id, **kwargs)
        self._sm._put_nonblocking(trigger_data, internal=self.internal)
        return trigger_data

    def build_trigger(
        self, *args, machine: "StateMachine", send_id: "str | None" = None, **kwargs
    ):
        if machine is None:
            raise RuntimeError(_("Event {} cannot be called without a SM instance").format(self))

        kwargs = {k: v for k, v in kwargs.items() if k not in _event_data_kwargs}
        trigger_data = TriggerData(
            machine=machine,
            event=self,
            send_id=send_id,
            args=args,
            kwargs=kwargs,
        )

        return trigger_data

    def __call__(self, *args, **kwargs):
        """Send this event to the current state machine.

        Triggering an event on a state machine means invoking or sending a signal, initiating the
        process that may result in executing a transition.
        """
        # The `__call__` is declared here to help IDEs knowing that an `Event`
        # can be called as a method. But it is not meant to be called without
        # an SM instance. Such SM instance is provided by `__get__` method when
        # used as a property descriptor.
        self.put(*args, **kwargs)
        return self._sm._processing_loop()

    def split(  # type: ignore[override]
        self, sep: "str | None" = None, maxsplit: int = -1
    ) -> List["Event"]:
        result = super().split(sep, maxsplit)
        if len(result) == 1:
            return [self]
        return [Event(event) for event in result]

    def match(self, event: str) -> bool:
        if self == "*":
            return True

        # Normalize descriptor by removing trailing '.*' or '.'
        # to handle cases like 'error', 'error.', 'error.*'
        descriptor = cast(str, self)
        if descriptor.endswith(".*"):
            descriptor = descriptor[:-2]
        elif descriptor.endswith("."):
            descriptor = descriptor[:-1]

        # Check prefix match:
        # The descriptor must be a prefix of the event.
        # Split both descriptor and event into tokens
        descriptor_tokens = descriptor.split(".") if descriptor else []
        event_tokens = event.split(".") if event else []

        if len(descriptor_tokens) > len(event_tokens):
            return False

        for d_token, e_token in zip(descriptor_tokens, event_tokens):  # noqa: B905
            if d_token != e_token:
                return False

        return True


class BoundEvent(Event):
    pass
