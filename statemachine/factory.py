from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from uuid import uuid4

from . import registry
from .event import Event
from .event import trigger_event_factory
from .exceptions import InvalidDefinition
from .graph import visit_connected_states
from .i18n import _
from .state import State
from .states import States
from .transition import Transition
from .transition_list import TransitionList


class StateMachineMetaclass(type):
    def __init__(cls, name: str, bases: Tuple[type], attrs: Dict[str, Any]):
        super().__init__(name, bases, attrs)
        registry.register(cls)
        cls.name = cls.__name__
        cls.states: States = States()
        cls.states_map: Dict[Any, State] = {}
        """Map of ``state.value`` to the corresponding :ref:`state`."""

        cls._abstract = True
        cls._events: Dict[str, Event] = {}

        cls.add_inherited(bases)
        cls.add_from_attributes(attrs)

        try:
            cls.initial_state: State = next(s for s in cls.states if s.initial)
        except StopIteration:
            cls.initial_state = None  # Abstract SM still don't have states

        cls.final_states: List[State] = [state for state in cls.states if state.final]

        cls._check()

    if TYPE_CHECKING:
        """Makes mypy happy with dynamic created attributes"""

        def __getattr__(self, attribute: str) -> Any:
            ...

    def _check(cls):
        has_states = bool(cls.states)
        has_events = bool(cls._events)

        cls._abstract = not has_states and not has_events

        # do not validate the base abstract classes
        if cls._abstract:
            return

        if not has_states:
            raise InvalidDefinition(_("There are no states."))

        if not has_events:
            raise InvalidDefinition(_("There are no events."))

        cls._check_initial_state()
        cls._check_final_states()
        cls._check_disconnected_state()

    def _check_initial_state(cls):
        initials = [s for s in cls.states if s.initial]
        if len(initials) != 1:
            raise InvalidDefinition(
                _(
                    "There should be one and only one initial state. "
                    "Your currently have these: {!r}"
                ).format([s.id for s in initials])
            )

    def _check_final_states(cls):
        final_state_with_invalid_transitions = [
            state for state in cls.final_states if state.transitions
        ]

        if final_state_with_invalid_transitions:
            raise InvalidDefinition(
                _(
                    "Cannot declare transitions from final state. Invalid state(s): {}"
                ).format([s.id for s in final_state_with_invalid_transitions])
            )

    def _disconnected_states(cls, starting_state):
        visitable_states = set(visit_connected_states(starting_state))
        return set(cls.states) - visitable_states

    def _check_disconnected_state(cls):
        disconnected_states = cls._disconnected_states(cls.initial_state)
        if disconnected_states:
            raise InvalidDefinition(
                _(
                    "There are unreachable states. "
                    "The statemachine graph should have a single component. "
                    "Disconnected states: {}"
                ).format([s.id for s in disconnected_states])
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
            if isinstance(value, States):
                cls._add_states_from_dict(value)
            if isinstance(value, State):
                cls.add_state(key, value)
            elif isinstance(value, (Transition, TransitionList)):
                cls.add_event(key, value)
            elif getattr(value, "_callbacks_to_update", None):
                cls._add_unbounded_callback(key, value)

    def _add_states_from_dict(cls, states):
        for state_id, state in states.items():
            cls.add_state(state_id, state)

    def _add_unbounded_callback(cls, attr_name, func):
        if func._is_event:
            # if func is an event, the `attr_name` will be replaced by an event trigger,
            # so we'll also give the ``func`` a new unique name to be used by the callback
            # machinery.
            cls.add_event(attr_name, func._transitions)
            attr_name = f"_{attr_name}_{uuid4().hex}"
            setattr(cls, attr_name, func)

        for ref in func._callbacks_to_update:
            ref(attr_name)

    def add_state(cls, id, state: State):
        state._set_id(id)
        cls.states.append(state)
        cls.states_map[state.value] = state
        if not hasattr(cls, id):
            setattr(cls, id, state)

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
    def events(self):
        return list(self._events.values())
