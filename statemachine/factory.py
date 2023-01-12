import warnings
from collections import OrderedDict
from uuid import uuid4

from . import registry
from .event import Event
from .event import trigger_event_factory
from .exceptions import InvalidDefinition
from .graph import visit_connected_states
from .state import State
from .transition import Transition
from .transition_list import TransitionList
from .utils import check_state_factory
from .utils import qualname
from .utils import ugettext as _


class StateMachineMetaclass(type):
    def __init__(cls, name, bases, attrs):
        super(StateMachineMetaclass, cls).__init__(name, bases, attrs)
        registry.register(cls)
        cls._abstract = True
        cls.name = cls.__name__
        cls.states = []
        cls._events = OrderedDict()
        cls.states_map = {}
        cls.add_inherited(bases)
        cls.add_from_attributes(attrs)

        for state in cls.states:
            setattr(cls, "is_{}".format(state.id), check_state_factory(state))

        cls._set_special_states()
        cls._check()

    def _set_special_states(cls):
        if not cls.states:
            return
        initials = [s for s in cls.states if s.initial]
        if len(initials) != 1:
            raise InvalidDefinition(
                _(
                    "There should be one and only one initial state. "
                    "Your currently have these: {!r}".format(initials)
                )
            )
        cls.initial_state = initials[0]
        cls.final_states = [state for state in cls.states if state.final]

    def _disconnected_states(cls, starting_state):
        visitable_states = set(visit_connected_states(starting_state))
        return set(cls.states) - visitable_states

    def _check(cls):

        # do not validate the base class
        name = qualname(cls)
        if name in (
            "statemachine.factory_2.StateMachine",
            "statemachine.factory_3.StateMachine",
        ):
            return

        cls._abstract = False

        if not cls.states:
            raise InvalidDefinition(_("There are no states."))

        if not cls._events:
            raise InvalidDefinition(_("There are no events."))

        disconnected_states = cls._disconnected_states(cls.initial_state)
        if disconnected_states:
            raise InvalidDefinition(
                _(
                    "There are unreachable states. "
                    "The statemachine graph should have a single component. "
                    "Disconnected states: [{}]".format(disconnected_states)
                )
            )

        final_state_with_invalid_transitions = [
            state for state in cls.final_states if state.transitions
        ]

        if final_state_with_invalid_transitions:
            raise InvalidDefinition(
                _(
                    "Cannot declare transitions from final state. Invalid state(s): {}".format(
                        [s.id for s in final_state_with_invalid_transitions]
                    )
                )
            )

    def add_inherited(cls, bases):
        for base in bases:
            for state in getattr(base, "states", []):
                cls.add_state(state.id, state)

            events = getattr(base, "_events", {})
            for event in events.values():
                cls.add_event(event.name)

    def add_from_attributes(cls, attrs):
        for key, value in sorted(attrs.items(), key=lambda pair: pair[0]):
            if isinstance(value, State):
                cls.add_state(key, value)
            elif isinstance(value, (Transition, TransitionList)):
                cls.add_event(key, value)
            elif getattr(value, "_callbacks_to_update", None):
                cls._add_unbounded_callback(key, value)

    def _add_unbounded_callback(cls, attr_name, func):
        if func._is_event:
            # if func is an event, the `attr_name` will be replaced by an event trigger,
            # so we'll also give the ``func`` a new unique name to be used by the callback
            # machinery.
            cls.add_event(attr_name, func._transitions)
            attr_name = "_{}_{}".format(attr_name, uuid4().hex)
            setattr(cls, attr_name, func)

        for ref in func._callbacks_to_update:
            ref(attr_name)

    def add_state(cls, id, state):
        state._set_id(id)
        cls.states.append(state)
        cls.states_map[state.value] = state

        # also register all events associated directly with transitions
        for event in state.transitions.unique_events:
            cls.add_event(event)

    def add_event(cls, event, transitions=None):
        if transitions is not None:
            transitions.add_event(event)

        if event not in cls._events:
            event_instance = Event(event)
            cls._events[event] = event_instance
            event_trigger = trigger_event_factory(event)
            setattr(cls, event, event_trigger)

        return cls._events[event]

    @property
    def transitions(self):
        warnings.warn(
            "Class level property `transitions` is deprecated. Use `events` instead.",
            DeprecationWarning,
        )
        return self.events

    @property
    def events(self):
        return list(self._events.values())
