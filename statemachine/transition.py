from functools import partial

from .callbacks import Callbacks
from .callbacks import ConditionWrapper
from .event_data import EventData
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
        self.validators = Callbacks().add(validators)
        self.before = Callbacks().add(before)
        self.on = Callbacks().add(on)
        self.after = Callbacks().add(after)
        self.cond = (
            Callbacks(factory=ConditionWrapper)
            .add(cond)
            .add(unless, expected_value=False)
        )

    def __repr__(self):
        return (
            f"{type(self).__name__}({self.source!r}, {self.target!r}, event={self.event!r}, "
            f"internal={self.internal!r})"
        )

    def _setup(self, resolver):
        self.validators.setup(resolver)
        self.cond.setup(resolver)
        self.before.setup(resolver)
        self.on.setup(resolver)
        self.after.setup(resolver)

    def _add_observer(self, *resolvers):
        for r in resolvers:
            before = partial(self.before.add, resolver=r, suppress_errors=True)
            on = partial(self.on.add, resolver=r, suppress_errors=True)
            after = partial(self.after.add, resolver=r, suppress_errors=True)

            before("before_transition", prepend=True)
            on("on_transition", prepend=True)

            for event in self._events:
                before("before_{}".format(event))
                on("on_{}".format(event))
                after("after_{}".format(event))

            after("after_transition")

    def _eval_cond(self, event_data):
        return all(
            condition(*event_data.args, **event_data.extended_kwargs)
            for condition in self.cond
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

    def execute(self, event_data: EventData):
        self.validators.call(*event_data.args, **event_data.extended_kwargs)
        if not self._eval_cond(event_data):
            return False

        result = event_data.machine._activate(event_data)
        event_data.result = result
        return True
