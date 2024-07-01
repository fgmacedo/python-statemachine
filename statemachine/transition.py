from .callbacks import CallbackGroup
from .callbacks import CallbackPriority
from .callbacks import CallbackSpecList
from .event import same_event_cond_builder
from .events import Events
from .exceptions import InvalidDefinition


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
        self._specs = CallbackSpecList()
        self.validators = self._specs.grouper(CallbackGroup.VALIDATOR).add(
            validators, priority=CallbackPriority.INLINE
        )
        self.before = self._specs.grouper(CallbackGroup.BEFORE).add(
            before, priority=CallbackPriority.INLINE
        )
        self.on = self._specs.grouper(CallbackGroup.ON).add(on, priority=CallbackPriority.INLINE)
        self.after = self._specs.grouper(CallbackGroup.AFTER).add(
            after, priority=CallbackPriority.INLINE
        )
        self.cond = (
            self._specs.grouper(CallbackGroup.COND)
            .add(cond, priority=CallbackPriority.INLINE, expected_value=True)
            .add(unless, priority=CallbackPriority.INLINE, expected_value=False)
        )

    def __repr__(self):
        return (
            f"{type(self).__name__}({self.source!r}, {self.target!r}, event={self.event!r}, "
            f"internal={self.internal!r})"
        )

    def __str__(self):
        return f"transition {self.event!s} from {self.source!s} to {self.target!s}"

    def _setup(self):
        before = self.before.add
        on = self.on.add
        after = self.after.add

        before("before_transition", priority=CallbackPriority.GENERIC, is_convention=True)
        on("on_transition", priority=CallbackPriority.GENERIC, is_convention=True)

        for event in self._events:
            same_event_cond = same_event_cond_builder(event)
            before(
                f"before_{event}",
                priority=CallbackPriority.NAMING,
                is_convention=True,
                cond=same_event_cond,
            )
            on(
                f"on_{event}",
                priority=CallbackPriority.NAMING,
                is_convention=True,
                cond=same_event_cond,
            )
            after(
                f"after_{event}",
                priority=CallbackPriority.NAMING,
                is_convention=True,
                cond=same_event_cond,
            )

        after(
            "after_transition",
            priority=CallbackPriority.AFTER,
            is_convention=True,
        )

    def match(self, event: str):
        return self._events.match(event)

    @property
    def event(self):
        return str(self._events)

    @property
    def events(self):
        return self._events

    def add_event(self, value):
        self._events.add(value)
