# coding: utf-8
import warnings
from functools import wraps
from weakref import ref

from .callbacks import Callbacks, ConditionWrapper, methodcaller, resolver_factory


class Transition(object):
    """
    A transition holds reference to the source and destination state.
    """

    def __init__(
        self,
        source,
        destination,
        trigger=None,
        validators=None,
        conditions=None,
        unless=None,
        on_execute=None,
        before=None,
        after=None,
    ):
        self.source = source
        self.destination = destination
        self.trigger = trigger
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
        return "{}({!r}, {!r}, trigger={!r})".format(
            type(self).__name__, self.source, self.destination, self.trigger
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
                "before_{}".format(self.trigger),
                "on_{}".format(self.trigger),
            ],
            suppress_errors=True,
        )
        self.after.add(
            ["after_{}".format(self.trigger), "after_transition"],
            suppress_errors=True,
        )

    def _eval_conditions(self, event_data):
        return all(
            condition(*event_data.args, **event_data.extended_kwargs)
            for condition in self.conditions
        )

    @property
    def identifier(self):
        warnings.warn(
            "identifier is deprecated. Use `trigger` instead", DeprecationWarning
        )
        return self.trigger

    def execute(self, event_data):
        self.validators(*event_data.args, **event_data.extended_kwargs)
        if not self._eval_conditions(event_data):
            return False

        result = event_data.machine._activate(event_data)
        event_data.result = result
        return True
