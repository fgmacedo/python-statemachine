# coding: utf-8
import warnings
from functools import wraps
from weakref import ref

from .callbacks import Callbacks, ConditionWrapper, methodcaller, resolver_factory
from .events import Events


class Transition(object):
    """
    A transition holds reference to the source and destination state.

    Args:
        source (State): The origin {ref}`State` of the transition.
        destination (State): The destination {ref}`State` of the transition.
        event (Optional[Union[str, List[str]]]): List of designators of events that trigger this
            transition.

            Can be either a list of strings, or a space-separated string list of event
            descriptors.
    """

    def __init__(
        self,
        source,
        destination,
        event=None,
        validators=None,
        conditions=None,
        unless=None,
        on_execute=None,
        before=None,
        after=None,
    ):

        self.source = source
        self.destination = destination
        self._events = Events().add(event)
        self.validators = Callbacks().add(validators)
        self.before = (
            Callbacks()
            .add("before_transition", suppress_errors=True)
            .add(before)
            .add(on_execute)
        )
        self.after = Callbacks().add(after)
        self.conditions = (
            Callbacks(factory=ConditionWrapper)
            .add(conditions)
            .add(unless, expected_value=False)
        )
        self.machine = None

    def __repr__(self):
        return "{}({!r}, {!r}, event={!r})".format(
            type(self).__name__, self.source, self.destination, self.event
        )

    def _get_promisse_to_machine(self, func):

        decorated = methodcaller(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return decorated(self.machine(), *args, **kwargs)

        return wrapper

    def _setup(self, machine):
        self.machine = ref(machine)
        resolver = resolver_factory(machine, machine.model)
        self.validators.setup(resolver)
        self.before.setup(resolver)
        self.after.setup(resolver)
        self.conditions.setup(resolver)

        self.before.add(
            [
                pattern.format(event)
                for pattern in ["before_{}", "on_{}"]
                for event in self._events
            ],
            suppress_errors=True,
        )
        self.after.add(
            [
                pattern.format(event)
                for pattern in ["after_{}"]
                for event in self._events
            ]
            + ["after_transition"],
            suppress_errors=True,
        )

    def _eval_conditions(self, event_data):
        return all(
            condition(*event_data.args, **event_data.extended_kwargs)
            for condition in self.conditions
        )

    def match(self, event):
        return self._events.match(event)

    @property
    def identifier(self):
        warnings.warn(
            "identifier is deprecated. Use `event` instead", DeprecationWarning
        )
        return self.event

    @property
    def event(self):
        return str(self._events)

    @property
    def events(self):
        return self._events

    def add_event(self, value):
        self._events.add(value)

    def execute(self, event_data):
        self.validators(*event_data.args, **event_data.extended_kwargs)
        if not self._eval_conditions(event_data):
            return False

        result = event_data.machine._activate(event_data)
        event_data.result = result
        return True
