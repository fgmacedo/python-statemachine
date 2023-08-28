from typing import TYPE_CHECKING

from .callbacks import BoolCallbackMeta
from .callbacks import CallbackMetaList
from .event import same_event_cond_builder
from .events import Events
from .exceptions import InvalidDefinition

if TYPE_CHECKING:
    from .event_data import EventData


class Transition:
    """A transition holds reference to the source and target state.

    Args:
        source (State): The origin state of the transition.
        target (State): The target state of the transition.
        event (Optional[Union[str, List[str]]]): List of designators of events that trigger this
            transition. Can be either a list of strings, or a space-separated string list of event
            descriptors.
        internal (bool): Is the transition internal or external? Internal transitions
            don't execute the state entry/exit actions. Default ``False``.
        validators (Optional[Union[str, Callable, List[Callable]]]): The validation callbacks to
            be invoked before the transition is executed.
        cond (Optional[Union[str, Callable, List[Callable]]]): The condition callbacks to be
            invoked before the transition is executed that should evaluate to `True`.
        unless (Optional[Union[str, Callable, List[Callable]]]): The condition callbacks to be
            invoked if the `cond` is False before the transition is executed.
        on (Optional[Union[str, Callable, List[Callable]]]): The callbacks to be invoked
            when the transition is executed.
        before (Optional[Union[str, Callable, List[Callable]]]): The callbacks to be invoked
            before the transition is executed.
        after (Optional[Union[str, Callable, List[Callable]]]): The callbacks to be invoked
            after the transition is executed.
    """

    def __init__(
        self,
        source,
        target,
        event=None,
        internal=False,
        validators=None,
        cond=None,
        unless=None,
        on=None,
        before=None,
        after=None,
    ):

        self.source = source
        self.target = target
        self.internal = internal

        if internal and source is not target:
            raise InvalidDefinition("Internal transitions should be self-transitions.")

        self._events = Events().add(event)
        self.validators = CallbackMetaList().add(validators)
        self.before = CallbackMetaList().add(before)
        self.on = CallbackMetaList().add(on)
        self.after = CallbackMetaList().add(after)
        self.cond = (
            CallbackMetaList(factory=BoolCallbackMeta)
            .add(cond)
            .add(unless, expected_value=False)
        )

    def __repr__(self):
        return (
            f"{type(self).__name__}({self.source!r}, {self.target!r}, event={self.event!r}, "
            f"internal={self.internal!r})"
        )

    def _setup(self, register):
        register(self.validators)
        register(self.cond)
        register(self.before)
        register(self.on)
        register(self.after)

    def _add_observer(self, registry):
        before = self.before.add
        on = self.on.add
        after = self.after.add
        before(
            "before_transition", registry=registry, suppress_errors=True, prepend=True
        )
        on("on_transition", registry=registry, suppress_errors=True, prepend=True)

        for event in self._events:
            same_event_cond = same_event_cond_builder(event)
            before(
                f"before_{event}",
                registry=registry,
                suppress_errors=True,
                cond=same_event_cond,
            )
            on(
                f"on_{event}",
                registry=registry,
                suppress_errors=True,
                cond=same_event_cond,
            )
            after(
                f"after_{event}",
                registry=registry,
                suppress_errors=True,
                cond=same_event_cond,
            )

        after(
            "after_transition",
            registry=registry,
            suppress_errors=True,
        )

    def match(self, event):
        return self._events.match(event)

    @property
    def event(self):
        return str(self._events)

    @property
    def events(self):
        return self._events

    def add_event(self, value):
        self._events.add(value)

    def execute(self, event_data: "EventData"):
        machine = event_data.machine
        args, kwargs = event_data.args, event_data.extended_kwargs
        machine._callbacks_registry[self.validators].call(*args, **kwargs)
        if not machine._callbacks_registry[self.cond].all(*args, **kwargs):
            return False

        result = machine._activate(event_data)
        event_data.result = result
        return True
