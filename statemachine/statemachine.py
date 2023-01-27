# coding: utf-8
import sys
import warnings
from collections import OrderedDict
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from .dispatcher import ObjectConfig
from .dispatcher import resolver_factory
from .event import Event
from .event_data import EventData
from .exceptions import InvalidStateValue
from .exceptions import TransitionNotAllowed
from .model import Model
from .state import State
from .transition import Transition


class BaseStateMachine(object):

    TransitionNotAllowed = TransitionNotAllowed  # shortcut for handling exceptions

    _events = {}  # type: Dict[Any, Any]
    states = []  # type: List[State]
    states_map = {}  # type: Dict[Any, State]

    def __init__(self, model=None, state_field="state", start_value=None):
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value

        initial_transition = Transition(
            None, self._get_initial_state(), event="__initial__"
        )
        self._setup(initial_transition)
        self._activate_initial_state(initial_transition)

    def __repr__(self):
        return "{}(model={!r}, state_field={!r}, current_state={!r})".format(
            type(self).__name__,
            self.model,
            self.state_field,
            self.current_state.id if self.current_state else None,
        )

    def _get_initial_state(self):
        current_state_value = (
            self.start_value if self.start_value else self.initial_state.value
        )
        try:
            return self.states_map[current_state_value]
        except KeyError:
            raise InvalidStateValue(current_state_value)

    def _activate_initial_state(self, initial_transition):
        if self.current_state_value is None:
            # send an one-time event `__initial__` to enter the current state.
            # current_state = self.current_state
            initial_transition.before.clear()
            initial_transition.on.clear()
            initial_transition.after.clear()
            event_data = EventData(
                self,
                initial_transition.event,
                transition=initial_transition,
            )
            self._activate(event_data)

    def _get_protected_attrs(self):
        return (
            {
                "_abstract",
                "model",
                "state_field",
                "start_value",
                "initial_state",
                "final_states",
                "states",
                "_events",
                "states_map",
                "send",
            }
            | {s.id for s in self.states}
            | {e for e in self._events.keys()}
        )

    def _visit_states_and_transitions(self, visitor):
        for state in self.states:
            visitor(state)
            for transition in state.transitions:
                visitor(transition)

    def _setup(self, initial_transition):
        machine = ObjectConfig(self, skip_attrs=self._get_protected_attrs())
        model = ObjectConfig(self.model, skip_attrs={self.state_field})
        default_resolver = resolver_factory(machine, model)

        # clone states and transitions to avoid sharing callbacks references between instances
        states = []
        self.states_map = OrderedDict()
        for state in self.states:
            new_state = state.clone()
            new_state._setup(self, default_resolver)
            states.append(new_state)
            self.states_map[new_state.value] = new_state

        self.states = states

        for state in self.states:
            for transition in state.transitions:
                transition._setup(self, default_resolver)

        initial_transition._setup(self, default_resolver)
        self.add_observer(machine, model)

    def add_observer(self, *observers):
        resolvers = [resolver_factory(ObjectConfig.from_obj(o)) for o in observers]
        self._visit_states_and_transitions(lambda x: x._add_observer(*resolvers))
        return self

    def _repr_html_(self):
        return '<div class="statemachine">{}</div>'.format(self._repr_svg_())

    def _repr_svg_(self):
        return self._graph().create_svg().decode()

    def _graph(self):
        from .contrib.diagram import DotGraphMachine

        return DotGraphMachine(self).get_graph()

    @property
    def current_state_value(self):
        value = getattr(self.model, self.state_field, None)
        return value

    @current_state_value.setter
    def current_state_value(self, value):
        if value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self):
        # type: () -> Optional[State]
        return self.states_map.get(self.current_state_value, None)

    @current_state.setter
    def current_state(self, value):
        self.current_state_value = value.value

    @property
    def transitions(self):
        warnings.warn(
            "Property `transitions` is deprecated. Use `events` instead.",
            DeprecationWarning,
        )
        return self.events

    @property
    def events(self):
        return self.__class__.events

    @property
    def allowed_transitions(self):
        "get the callable proxy of the current allowed transitions"
        warnings.warn(
            "`allowed_transitions` is deprecated. Use `allowed_events` instead.",
            DeprecationWarning,
        )
        return [
            getattr(self, event)
            for event in self.current_state.transitions.unique_events
        ]

    @property
    def allowed_events(self):
        "get the callable proxy of the current allowed events"
        return [
            getattr(self, event)
            for event in self.current_state.transitions.unique_events
        ]

    def _process(self, trigger):
        """This method will also handle execution queue"""
        return trigger()

    def _activate(self, event_data):
        transition = event_data.transition
        source = event_data.state
        target = transition.target

        result = transition.before.call(*event_data.args, **event_data.extended_kwargs)
        if source is not None:
            source.exit.call(*event_data.args, **event_data.extended_kwargs)

        result += transition.on.call(*event_data.args, **event_data.extended_kwargs)

        self.current_state = target
        event_data.state = target

        target.enter.call(*event_data.args, **event_data.extended_kwargs)
        transition.after.call(*event_data.args, **event_data.extended_kwargs)

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    def run(self, event, *args, **kwargs):
        warnings.warn(
            "`run` is deprecated. Use `send` instead.",
            DeprecationWarning,
        )
        event = Event(event)
        return event(self, *args, **kwargs)

    def send(self, event, *args, **kwargs):
        event = Event(event)
        return event(self, *args, **kwargs)


# Python 2
if sys.version_info[0] == 2:  # pragma: no cover
    from .factory_2 import StateMachine  # noqa
else:
    from .factory_3 import StateMachine  # noqa
