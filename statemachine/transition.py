# coding: utf-8
import warnings

from .callbacks import Callbacks, ConditionWrapper

from .events import Events


class Transition(object):
    """
    A transition holds reference to the source and target state.

    Args:
        source (State): The origin :ref:`State` of the transition.
        target (State): The target :ref:`State` of the transition.
        event (Optional[Union[str, List[str]]]): List of designators of events that trigger this
            transition.

            Can be either a list of strings, or a space-separated string list of event
            descriptors.
    """

    def __init__(
        self,
        source,
        target,
        event=None,
        validators=None,
        cond=None,
        unless=None,
        on=None,
        before=None,
        after=None,
    ):

        self.source = source
        self.target = target
        self._events = Events().add(event)
        self.validators = Callbacks().add(validators)
        self.before = (
            Callbacks()
            .add("before_transition", suppress_errors=True)
            .add(before)
        )
        self.on = (
            Callbacks()
            .add("on_transition", suppress_errors=True)
            .add(on)
        )
        self.after = Callbacks().add(after)
        self.cond = (
            Callbacks(factory=ConditionWrapper)
            .add(cond)
            .add(unless, expected_value=False)
        )

    def __repr__(self):
        return "{}({!r}, {!r}, event={!r})".format(
            type(self).__name__, self.source, self.target, self.event
        )

    def _setup(self, resolver):
        self.validators.setup(resolver)
        self.cond.setup(resolver)
        self.before.setup(resolver)
        self.on.setup(resolver)
        self.after.setup(resolver)

        self.before.add(
            [
                pattern.format(event)
                for pattern in ["before_{}"]
                for event in self._events
            ],
            suppress_errors=True,
        )
        self.on.add(
            [
                pattern.format(event)
                for pattern in ["on_{}"]
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

    def _eval_cond(self, event_data):
        return all(
            condition(*event_data.args, **event_data.extended_kwargs)
            for condition in self.cond
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
        self.validators.call(*event_data.args, **event_data.extended_kwargs)
        if not self._eval_cond(event_data):
            return False

        result = event_data.machine._activate(event_data)
        event_data.result = result
        return True
